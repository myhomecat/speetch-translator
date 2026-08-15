"""
로컬 STT 세션 (Soniox 대체, 완전 오프라인)

2026-08 M4 벤치마크 결과에 기반한 하이브리드 구성:
- 한국어 임시자막: sherpa-onnx 스트리밍 zipformer (~160ms, 품질 낮음 → 임시 표시용)
- 한국어 최종자막: faster-whisper (정확, 발화 종료 후 정정)
- 일본어: sherpa-onnx ReazonSpeech zipformer (누적 재디코딩 24~84ms, 정확도 최고)
- 언어 판별(AUTO 모드): faster-whisper 언어 감지 (발화 1.5초 시점 1회)

번역은 세션 밖(websocket 콜백)에서 LibreTranslate로 수행한다.
"""
import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Callable, Awaitable

import numpy as np

from ..config import get_settings
from ..models.room import TranslationMode

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000

# 무거운 모델은 프로세스당 1회만 로드 (전 세션 공유)
_executor = ThreadPoolExecutor(max_workers=2)
_ko_online_recognizer = None
_ja_offline_recognizer = None
_whisper_model = None
_load_lock = asyncio.Lock()


def _load_ko_online():
    global _ko_online_recognizer
    if _ko_online_recognizer is None:
        import sherpa_onnx
        d = get_settings().local_stt_ko_model_dir
        _ko_online_recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=f"{d}/tokens.txt",
            encoder=f"{d}/encoder-epoch-99-avg-1.int8.onnx",
            decoder=f"{d}/decoder-epoch-99-avg-1.onnx",
            joiner=f"{d}/joiner-epoch-99-avg-1.int8.onnx",
            num_threads=2,
            enable_endpoint_detection=False,
        )
        logger.info("[LocalSTT] ko online recognizer loaded")
    return _ko_online_recognizer


def _load_ja_offline():
    global _ja_offline_recognizer
    if _ja_offline_recognizer is None:
        import sherpa_onnx
        d = get_settings().local_stt_ja_model_dir
        _ja_offline_recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            tokens=f"{d}/tokens.txt",
            encoder=f"{d}/encoder-epoch-99-avg-1.int8.onnx",
            decoder=f"{d}/decoder-epoch-99-avg-1.onnx",
            joiner=f"{d}/joiner-epoch-99-avg-1.int8.onnx",
            num_threads=2,
        )
        logger.info("[LocalSTT] ja offline recognizer loaded")
    return _ja_offline_recognizer


def _load_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        model_name = get_settings().local_ko_final_model
        _whisper_model = WhisperModel(model_name, device="cpu", compute_type="int8")
        logger.info(f"[LocalSTT] faster-whisper '{model_name}' loaded")
    return _whisper_model


async def preload_local_models():
    """서버 기동 시 모델 프리로드 (stt_engine=local일 때 main에서 호출)"""
    async with _load_lock:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(_executor, _load_ko_online)
        await loop.run_in_executor(_executor, _load_ja_offline)
        await loop.run_in_executor(_executor, _load_whisper)


def _decode_ja(samples: np.ndarray) -> str:
    rec = _load_ja_offline()
    stream = rec.create_stream()
    stream.accept_waveform(SAMPLE_RATE, samples)
    rec.decode_stream(stream)
    return stream.result.text.strip()


def _detect_language(samples: np.ndarray) -> str:
    """faster-whisper로 ko/ja 판별"""
    model = _load_whisper()
    _, info = model.transcribe(samples, language=None, beam_size=1)
    lang = info.language
    return "ja" if lang == "ja" else "ko"


def _decode_ko_whisper(samples: np.ndarray) -> str:
    model = _load_whisper()
    segments, _ = model.transcribe(samples, language="ko", beam_size=1)
    return "".join(seg.text for seg in segments).strip()


class LocalSTTSession:
    """VAD + 언어별 하이브리드 디코딩 세션

    on_transcript(text, is_final, language):
    - is_final=False: 임시자막 (ko: sherpa 스트리밍 / ja: 누적 재디코딩)
    - is_final=True: 최종자막 (ko: whisper 정정 / ja: sherpa 최종)
    """

    # VAD/타이밍 파라미터
    SPEECH_RMS = 0.010          # 발화 시작 판정 RMS
    SILENCE_SEC = 0.9           # 발화 종료 판정 침묵 길이
    LID_AT_SEC = 1.5            # 언어 판별 시점 (발화 누적 길이)
    JA_REDECODE_SEC = 0.7       # ja 부분자막 재디코딩 주기

    def __init__(
        self,
        user_id: str,
        translation_mode: TranslationMode = TranslationMode.AUTO,
        on_transcript: Optional[Callable[[str, bool, Optional[str]], Awaitable[None]]] = None,
        on_error: Optional[Callable[[str], Awaitable[None]]] = None,
    ):
        self.user_id = user_id
        self.translation_mode = translation_mode
        self.on_transcript = on_transcript
        self.on_error = on_error
        self.is_connected = True  # websocket.py의 세션 인터페이스와 호환

        self._utterance = np.zeros(0, dtype=np.float32)  # 현재 발화 버퍼
        self._in_speech = False
        self._silence_samples = 0
        self._language: Optional[str] = self._locked_language()
        self._generation = 0  # 발화 세대 (리셋 후 도착한 늦은 LID 결과 무시용)
        self._lid_task: Optional[asyncio.Task] = None
        self._ko_stream = None
        self._last_partial = ""
        self._last_ja_decode_len = 0
        self._finalizing = False

    def _locked_language(self) -> Optional[str]:
        if self.translation_mode == TranslationMode.KO_TO_JA:
            return "ko"
        if self.translation_mode == TranslationMode.JA_TO_KO:
            return "ja"
        return None  # AUTO: 발화 중 LID로 판별

    async def connect(self):
        async with _load_lock:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(_executor, _load_ko_online)
            await loop.run_in_executor(_executor, _load_ja_offline)
            await loop.run_in_executor(_executor, _load_whisper)

    async def disconnect(self):
        self.is_connected = False
        if self._lid_task:
            self._lid_task.cancel()

    async def send_audio(self, audio_data: bytes):
        """s16le 16kHz mono PCM 청크 수신"""
        if not self.is_connected or self._finalizing:
            return
        samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        if samples.size == 0:
            return

        rms = float(np.sqrt(np.mean(samples ** 2)))

        if not self._in_speech:
            if rms < self.SPEECH_RMS:
                return  # 침묵 구간은 무시
            self._in_speech = True
            self._silence_samples = 0
            logger.debug(f"[LocalSTT] speech start (rms={rms:.4f})")

        self._utterance = np.concatenate([self._utterance, samples])

        # 침묵 누적 → 발화 종료 판정
        if rms < self.SPEECH_RMS:
            self._silence_samples += samples.size
            if self._silence_samples >= int(self.SILENCE_SEC * SAMPLE_RATE):
                await self._finalize_utterance()
                return
        else:
            self._silence_samples = 0

        # AUTO 모드: 발화가 LID_AT_SEC를 넘으면 백그라운드로 언어 판별 1회
        if (
            self._language is None
            and self._lid_task is None
            and self._utterance.size >= int(self.LID_AT_SEC * SAMPLE_RATE)
        ):
            snippet = self._utterance.copy()
            self._lid_task = asyncio.create_task(self._run_lid(snippet, self._generation))

        await self._emit_partial(samples)

    async def _run_lid(self, snippet: np.ndarray, generation: int):
        try:
            loop = asyncio.get_running_loop()
            lang = await loop.run_in_executor(_executor, _detect_language, snippet)
            if self._language is None and generation == self._generation:
                self._language = lang
                logger.info(f"[LocalSTT] language detected: {lang}")
        except Exception as e:
            logger.warning(f"[LocalSTT] LID failed, defaulting to ko: {e}")
            if self._language is None and generation == self._generation:
                self._language = "ko"

    async def _emit_partial(self, new_samples: np.ndarray):
        """임시자막 방출: ko는 스트리밍, ja는 주기적 누적 재디코딩"""
        lang = self._language

        if lang == "ja":
            # 재디코딩 주기 도달 시에만
            if (
                self._utterance.size - self._last_ja_decode_len
                >= int(self.JA_REDECODE_SEC * SAMPLE_RATE)
            ):
                self._last_ja_decode_len = self._utterance.size
                loop = asyncio.get_running_loop()
                text = await loop.run_in_executor(
                    _executor, _decode_ja, self._utterance.copy()
                )
                if text and text != self._last_partial:
                    self._last_partial = text
                    if self.on_transcript:
                        await self.on_transcript(text, False, "ja")
            return

        # ko 또는 미판별: sherpa ko 스트리밍 (LID 전 임시 피드백 겸용)
        rec = _load_ko_online()
        if self._ko_stream is None:
            self._ko_stream = rec.create_stream()
        self._ko_stream.accept_waveform(SAMPLE_RATE, new_samples)
        while rec.is_ready(self._ko_stream):
            rec.decode_stream(self._ko_stream)
        text = rec.get_result(self._ko_stream)
        if text and text != self._last_partial:
            self._last_partial = text
            if self.on_transcript:
                await self.on_transcript(text, False, lang or "ko")

    async def _finalize_utterance(self):
        """발화 종료: 언어 확정 → 최종 디코딩 → final 자막 방출"""
        if self._finalizing or self._utterance.size < int(0.3 * SAMPLE_RATE):
            self._reset_utterance()
            return
        self._finalizing = True
        try:
            utterance = self._utterance.copy()
            loop = asyncio.get_running_loop()

            # LID가 아직이면 지금 판별 (진행 중이면 완료 대기)
            if self._language is None:
                if self._lid_task:
                    try:
                        await self._lid_task
                    except asyncio.CancelledError:
                        pass
                if self._language is None:
                    self._language = await loop.run_in_executor(
                        _executor, _detect_language, utterance
                    )
            lang = self._language

            t0 = time.perf_counter()
            if lang == "ja":
                final_text = await loop.run_in_executor(_executor, _decode_ja, utterance)
            else:
                final_text = await loop.run_in_executor(
                    _executor, _decode_ko_whisper, utterance
                )
            logger.info(
                f"[LocalSTT] final ({lang}, {utterance.size / SAMPLE_RATE:.1f}s "
                f"-> {time.perf_counter() - t0:.2f}s): {final_text[:60]}"
            )

            if final_text and self.on_transcript:
                await self.on_transcript(final_text, True, lang)
        except Exception as e:
            logger.error(f"[LocalSTT] finalize error: {e}")
            if self.on_error:
                await self.on_error(f"Local STT error: {e}")
        finally:
            self._reset_utterance()
            self._finalizing = False

    def _reset_utterance(self):
        self._generation += 1
        self._utterance = np.zeros(0, dtype=np.float32)
        self._in_speech = False
        self._silence_samples = 0
        self._language = self._locked_language()
        if self._lid_task:
            self._lid_task.cancel()
            self._lid_task = None
        self._ko_stream = None
        self._last_partial = ""
        self._last_ja_decode_len = 0

    async def end_turn(self):
        """클라이언트 침묵 감지/마이크 종료 신호 → 강제 발화 종료"""
        if self._in_speech and self._utterance.size > 0:
            await self._finalize_utterance()

    async def reset(self):
        self._reset_utterance()

    def change_language(self, mode: TranslationMode):
        self.translation_mode = mode
        self._language = self._locked_language()


class LocalSTTSessionManager:
    """room_id -> user_id -> LocalSTTSession (soniox_session_manager와 동일 인터페이스)"""

    def __init__(self):
        self._sessions: dict[str, dict[str, LocalSTTSession]] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        room_id: str,
        user_id: str,
        translation_mode: TranslationMode,
        on_transcript=None,
        on_error=None,
    ) -> LocalSTTSession:
        async with self._lock:
            if room_id not in self._sessions:
                self._sessions[room_id] = {}
            session = LocalSTTSession(
                user_id=user_id,
                translation_mode=translation_mode,
                on_transcript=on_transcript,
                on_error=on_error,
            )
            self._sessions[room_id][user_id] = session
        await session.connect()
        return session

    async def remove_session(self, room_id: str, user_id: str):
        async with self._lock:
            if room_id in self._sessions:
                session = self._sessions[room_id].pop(user_id, None)
                if session:
                    await session.disconnect()
                if not self._sessions[room_id]:
                    del self._sessions[room_id]


# 싱글톤 인스턴스
local_stt_session_manager = LocalSTTSessionManager()
