"""
Faster-Whisper 기반 실시간 STT 세션
Local Agreement 알고리즘 + 문맥 유지로 높은 정확도 구현

참고: https://velog.io/@jayginwoolee/Whisper-streaming
"""

import asyncio
import logging
import numpy as np
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Callable, Awaitable, List
from faster_whisper import WhisperModel
from ..models.room import TranslationMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Thread pool for Whisper (CPU-intensive)
_executor = ThreadPoolExecutor(max_workers=2)

# Whisper model (singleton, loaded once)
_whisper_model: Optional[WhisperModel] = None
_model_lock = asyncio.Lock()


def _get_model() -> WhisperModel:
    """Get or create Whisper model (thread-safe singleton)"""
    global _whisper_model
    if _whisper_model is None:
        logger.info("[Whisper] Loading model 'small' (this may take a moment)...")
        _whisper_model = WhisperModel(
            "small",
            device="cpu",
            compute_type="int8"
        )
        logger.info("[Whisper] Model loaded successfully")
    return _whisper_model


def preload_whisper_model():
    """Preload Whisper model at startup"""
    try:
        _get_model()
    except Exception as e:
        logger.error(f"[Whisper] Failed to preload model: {e}")


class WhisperSession:
    """
    Faster-Whisper STT session with Local Agreement algorithm

    Local Agreement (n=2):
    - 연속 2개 버퍼에서 동일한 토큰이 생성되어야 확정
    - 미확정 토큰은 partial로 표시, 확정 토큰은 final로 전송

    문맥 유지:
    - 이전 확정된 텍스트를 프롬프트로 사용하여 일관성 유지
    """

    SAMPLE_RATE = 16000
    BYTES_PER_SAMPLE = 2  # 16-bit PCM

    # 버퍼링 설정
    CHUNK_DURATION = 0.5  # 0.5초 단위로 처리
    MIN_AUDIO_LENGTH = 0.5  # 최소 0.5초
    MAX_AUDIO_LENGTH = 15.0  # 최대 15초
    SILENCE_THRESHOLD = 300  # 침묵 감지 임계값
    SILENCE_DURATION = 0.5  # 0.5초 침묵 시 강제 확정

    # 문맥 유지 설정
    MAX_PROMPT_WORDS = 200  # 프롬프트로 사용할 최대 단어 수

    # 문장 종결 부호
    SENTENCE_END_MARKERS = {'.', '?', '!', '。', '？', '！'}

    def __init__(
        self,
        user_id: str,
        translation_mode: TranslationMode = TranslationMode.AUTO,
        on_transcript: Optional[Callable[[str, bool], Awaitable[None]]] = None,
        on_error: Optional[Callable[[str], Awaitable[None]]] = None,
    ):
        self.user_id = user_id
        self.translation_mode = translation_mode
        self.on_transcript = on_transcript
        self.on_error = on_error

        self._audio_buffer = bytearray()
        self._is_connected = False
        self._loop = asyncio.get_event_loop()
        self._processing = False
        self._process_task: Optional[asyncio.Task] = None

        # Local Agreement 상태
        self._prev_tokens: List[str] = []  # 이전 버퍼의 토큰들
        self._confirmed_text = ""  # 확정된 전체 텍스트
        self._pending_text = ""  # 미확정 텍스트 (partial)
        self._last_sent_confirmed = ""  # 마지막으로 전송한 확정 텍스트

        # 침묵 감지
        self._silence_samples = 0
        self._has_speech = False

        # 언어 설정
        self._language = self._get_source_language()

    def _get_source_language(self) -> str:
        """Get source language for Whisper"""
        if self.translation_mode == TranslationMode.KO_TO_JA:
            return "ko"
        elif self.translation_mode == TranslationMode.JA_TO_KO:
            return "ja"
        return "ko"  # 기본값: 한국어 (자동 감지 정확도 낮음)

    async def connect(self):
        """Initialize Whisper session"""
        if self._is_connected:
            return

        try:
            await self._loop.run_in_executor(_executor, _get_model)
            self._is_connected = True
            self._process_task = asyncio.create_task(self._periodic_process())
            logger.info(f"[Whisper] Session created for user {self.user_id}, lang={self._language}")
        except Exception as e:
            logger.error(f"[Whisper] Failed to create session: {e}")
            if self.on_error:
                await self.on_error(f"Whisper initialization error: {str(e)}")
            raise

    async def disconnect(self):
        """Clean up Whisper session"""
        self._is_connected = False

        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
            self._process_task = None

        # 남은 텍스트 최종 전송
        if self._pending_text or len(self._audio_buffer) > 0:
            await self._force_finalize()

        self._audio_buffer.clear()
        logger.info(f"[Whisper] Session disconnected for user {self.user_id}")

    async def send_audio(self, audio_data: bytes):
        """Add audio data to buffer"""
        if not self._is_connected:
            return

        self._audio_buffer.extend(audio_data)

        # 침묵 감지 (simple energy-based VAD)
        samples = np.frombuffer(audio_data, dtype=np.int16)
        energy = np.abs(samples).mean()

        if energy < self.SILENCE_THRESHOLD:
            self._silence_samples += len(samples)
        else:
            self._silence_samples = 0
            self._has_speech = True

        # 버퍼 길이 계산
        buffer_duration = len(self._audio_buffer) / (self.SAMPLE_RATE * self.BYTES_PER_SAMPLE)
        silence_duration = self._silence_samples / self.SAMPLE_RATE

        # 강제 처리 조건
        if buffer_duration >= self.MAX_AUDIO_LENGTH:
            await self._process_buffer()
            await self._force_finalize()
        elif self._has_speech and silence_duration >= self.SILENCE_DURATION:
            await self._process_buffer()
            await self._force_finalize()

    async def _periodic_process(self):
        """Periodically process buffer for streaming results"""
        while self._is_connected:
            try:
                await asyncio.sleep(self.CHUNK_DURATION)

                buffer_duration = len(self._audio_buffer) / (self.SAMPLE_RATE * self.BYTES_PER_SAMPLE)

                if buffer_duration >= self.MIN_AUDIO_LENGTH and not self._processing:
                    await self._process_buffer()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Whisper] Periodic process error: {e}")

    async def _process_buffer(self):
        """Process current audio buffer with Local Agreement"""
        if self._processing or len(self._audio_buffer) == 0:
            return

        self._processing = True
        process_start = time.time()

        try:
            # 오디오 데이터 복사 (버퍼 유지)
            audio_bytes = bytes(self._audio_buffer)
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

            # 이전 확정 텍스트를 프롬프트로 사용 (문맥 유지)
            prompt = self._get_context_prompt()

            # Transcribe
            tokens = await self._loop.run_in_executor(
                _executor,
                self._transcribe_sync,
                audio_np,
                prompt
            )

            if tokens:
                await self._apply_local_agreement(tokens)
                elapsed = time.time() - process_start
                buffer_duration = len(audio_bytes) / (self.SAMPLE_RATE * self.BYTES_PER_SAMPLE)
                logger.info(f"[Whisper] 처리시간: {elapsed:.2f}초, 버퍼: {buffer_duration:.2f}초, 토큰: {len(tokens)}")

        except Exception as e:
            logger.error(f"[Whisper] Processing error: {e}")
            if self.on_error:
                await self.on_error(f"Whisper processing error: {str(e)}")
        finally:
            self._processing = False

    def _get_context_prompt(self) -> Optional[str]:
        """Get context prompt from confirmed text"""
        if not self._confirmed_text:
            return None

        words = self._confirmed_text.split()
        if len(words) > self.MAX_PROMPT_WORDS:
            words = words[-self.MAX_PROMPT_WORDS:]

        return " ".join(words)

    def _transcribe_sync(self, audio_np: np.ndarray, prompt: Optional[str] = None) -> List[str]:
        """Synchronous transcription returning tokens"""
        model = _get_model()

        segments, info = model.transcribe(
            audio_np,
            language=self._language,
            beam_size=5,
            vad_filter=False,  # VAD 비활성화 - 모든 오디오 처리
            initial_prompt=prompt
        )

        # 토큰 단위로 분할 (단어 단위)
        tokens = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                tokens.extend(text.split())

        return tokens

    async def _apply_local_agreement(self, current_tokens: List[str]):
        """
        Local Agreement (n=2) 알고리즘 적용

        연속 2개 버퍼에서 동일한 토큰이 생성되면 확정
        """
        if not current_tokens:
            return

        # 이전 토큰과 비교하여 일치하는 부분 찾기
        confirmed_count = 0
        for i, (prev, curr) in enumerate(zip(self._prev_tokens, current_tokens)):
            if prev == curr:
                confirmed_count = i + 1
            else:
                break

        # 확정된 토큰들과 미확정 토큰들
        confirmed_tokens = current_tokens[:confirmed_count]
        pending_tokens = current_tokens[confirmed_count:]

        # 확정 텍스트는 현재 버퍼의 확정 토큰으로 설정 (중복 방지)
        self._confirmed_text = " ".join(confirmed_tokens) if confirmed_tokens else ""
        self._pending_text = " ".join(pending_tokens) if pending_tokens else ""

        # 전체 텍스트 구성
        full_text = f"{self._confirmed_text} {self._pending_text}".strip()

        # 문장 종결 부호 확인 - 확정 텍스트에 종결 부호가 있으면 final 전송
        if self._confirmed_text and self._is_sentence_complete(self._confirmed_text):
            await self._send_final()
        elif full_text:
            # Partial 전송
            if self.on_transcript:
                logger.debug(f"[Whisper] Partial: {full_text}")
                await self.on_transcript(full_text, False)

        # 현재 토큰을 이전 토큰으로 저장
        self._prev_tokens = current_tokens.copy()

    def _is_sentence_complete(self, text: str) -> bool:
        """문장이 완료되었는지 확인"""
        if not text:
            return False
        return text[-1] in self.SENTENCE_END_MARKERS

    async def _send_final(self):
        """확정된 문장 전송"""
        if not self._confirmed_text or self._confirmed_text == self._last_sent_confirmed:
            return

        if self.on_transcript:
            logger.info(f"[Whisper] Final: {self._confirmed_text}")
            await self.on_transcript(self._confirmed_text, True)

        self._last_sent_confirmed = self._confirmed_text

        # 버퍼 정리 (확정된 부분에 해당하는 오디오 제거)
        # 간단히 전체 버퍼의 앞부분을 제거
        buffer_duration = len(self._audio_buffer) / (self.SAMPLE_RATE * self.BYTES_PER_SAMPLE)
        if buffer_duration > 2.0:
            # 2초 이상이면 앞 1초 제거
            remove_bytes = int(self.SAMPLE_RATE * self.BYTES_PER_SAMPLE * 1.0)
            self._audio_buffer = self._audio_buffer[remove_bytes:]

    async def _force_finalize(self):
        """강제로 현재까지의 텍스트를 확정"""
        # Pending 텍스트도 확정
        if self._pending_text:
            if self._confirmed_text:
                self._confirmed_text = f"{self._confirmed_text} {self._pending_text}".strip()
            else:
                self._confirmed_text = self._pending_text
            self._pending_text = ""

        # 최종 전송
        if self._confirmed_text and self._confirmed_text != self._last_sent_confirmed:
            if self.on_transcript:
                logger.info(f"[Whisper] Final (forced): {self._confirmed_text}")
                await self.on_transcript(self._confirmed_text, True)
            self._last_sent_confirmed = self._confirmed_text

        # 상태 리셋
        self._audio_buffer.clear()
        self._prev_tokens = []
        self._silence_samples = 0
        self._has_speech = False
        # confirmed_text는 문맥 유지를 위해 보존

    async def reset(self):
        """Reset session for new utterance"""
        await self._force_finalize()

        # 완전 리셋
        self._confirmed_text = ""
        self._pending_text = ""
        self._last_sent_confirmed = ""
        self._prev_tokens = []

        logger.info(f"[Whisper] Session reset for user {self.user_id}")

    def change_language(self, new_mode: TranslationMode):
        """Change the source language"""
        self.translation_mode = new_mode
        self._language = self._get_source_language()
        logger.info(f"[Whisper] Language changed to {self._language} for user {self.user_id}")

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def source_language(self) -> Optional[str]:
        return self._language


class WhisperSessionManager:
    """Manager for Whisper sessions"""

    def __init__(self):
        self._sessions: dict[str, dict[str, WhisperSession]] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        room_id: str,
        user_id: str,
        translation_mode: TranslationMode,
        on_transcript: Optional[Callable[[str, bool], Awaitable[None]]] = None,
        on_error: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> WhisperSession:
        """Create a new Whisper session"""
        async with self._lock:
            if room_id not in self._sessions:
                self._sessions[room_id] = {}

            if user_id in self._sessions[room_id]:
                old_session = self._sessions[room_id][user_id]
                await old_session.disconnect()

            session = WhisperSession(
                user_id=user_id,
                translation_mode=translation_mode,
                on_transcript=on_transcript,
                on_error=on_error,
            )
            self._sessions[room_id][user_id] = session
            await session.connect()
            return session

    async def get_session(self, room_id: str, user_id: str) -> Optional[WhisperSession]:
        """Get an existing session"""
        if room_id in self._sessions:
            return self._sessions[room_id].get(user_id)
        return None

    async def remove_session(self, room_id: str, user_id: str):
        """Remove and disconnect a session"""
        async with self._lock:
            if room_id in self._sessions:
                session = self._sessions[room_id].pop(user_id, None)
                if session:
                    await session.disconnect()
                if not self._sessions[room_id]:
                    del self._sessions[room_id]

    async def remove_all_sessions(self, room_id: str):
        """Remove all sessions for a room"""
        async with self._lock:
            if room_id in self._sessions:
                for session in self._sessions[room_id].values():
                    await session.disconnect()
                del self._sessions[room_id]


# Singleton instance
whisper_session_manager = WhisperSessionManager()
