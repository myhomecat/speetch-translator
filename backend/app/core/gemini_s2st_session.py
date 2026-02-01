"""
Gemini Live API Session (Native Audio with Translation)

Uses gemini-live-2.5-flash-native-audio model for real-time speech translation.
- 입력: 음성 (한국어/일본어)
- 출력: 번역된 음성 + 텍스트 자막 (원본 + 번역)

인증: Vertex AI ADC (Application Default Credentials) 사용
"""
import asyncio
import logging
from typing import Optional, Callable, Awaitable
from google import genai
from google.genai import types
from ..config import get_settings
from ..models.room import TranslationMode

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# 번역 시스템 프롬프트
TRANSLATION_PROMPTS = {
    TranslationMode.AUTO: """You are a real-time interpreter.
When you hear Korean, translate it to Japanese and speak it.
When you hear Japanese, translate it to Korean and speak it.
Only output the translation, do not repeat the original.
Speak naturally and maintain the original tone and emotion.""",

    TranslationMode.KO_TO_JA: """You are a Korean to Japanese interpreter.
Translate everything you hear from Korean to Japanese.
Only output the Japanese translation, do not repeat the Korean.
Speak naturally and maintain the original tone and emotion.""",

    TranslationMode.JA_TO_KO: """You are a Japanese to Korean interpreter.
Translate everything you hear from Japanese to Korean.
Only output the Korean translation, do not repeat the Japanese.
Speak naturally and maintain the original tone and emotion.""",
}

# 출력 언어 코드 매핑 (TTS용)
OUTPUT_LANGUAGE_CODES = {
    TranslationMode.AUTO: "ja",  # 기본값: 일본어 TTS
    TranslationMode.KO_TO_JA: "ja",  # 일본어 TTS
    TranslationMode.JA_TO_KO: "ko",  # 한국어 TTS
}


class GeminiS2STSession:
    """Gemini S2ST 세션 - 실시간 음성 번역"""

    def __init__(
        self,
        user_id: str,
        translation_mode: TranslationMode = TranslationMode.AUTO,
        on_audio: Optional[Callable[[bytes], Awaitable[None]]] = None,
        on_transcript: Optional[Callable[[str, bool, Optional[str]], Awaitable[None]]] = None,
        on_error: Optional[Callable[[str], Awaitable[None]]] = None,
    ):
        """
        Args:
            user_id: 사용자 ID
            translation_mode: 번역 모드 (auto, ko_to_ja, ja_to_ko)
            on_audio: 번역된 오디오 콜백 (audio_bytes)
            on_transcript: 자막 콜백 (text, is_final, translated_text)
            on_error: 에러 콜백
        """
        self.user_id = user_id
        self.translation_mode = translation_mode
        self.on_audio = on_audio
        self.on_transcript = on_transcript
        self.on_error = on_error

        self._settings = get_settings()
        self._client: Optional[genai.Client] = None
        self._session = None
        self._session_context = None
        self._is_connected = False
        self._is_closing = False
        self._receive_task: Optional[asyncio.Task] = None
        self._reconnect_lock = asyncio.Lock()

        # 현재 입력 텍스트 버퍼 (partial → final 처리용)
        self._current_input_text = ""
        self._current_output_text = ""

    def _get_config(self) -> types.LiveConnectConfig:
        """Native Audio 모델용 설정 생성"""
        output_lang = OUTPUT_LANGUAGE_CODES.get(self.translation_mode, "ja")
        system_prompt = TRANSLATION_PROMPTS.get(self.translation_mode, TRANSLATION_PROMPTS[TranslationMode.AUTO])

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            # 시스템 프롬프트로 번역 지시
            system_instruction=types.Content(
                parts=[types.Part(text=system_prompt)]
            ),
            # TTS 출력 언어 설정
            speech_config=types.SpeechConfig(
                language_code=output_lang
            ),
            # 입출력 자막 활성화
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )

    def _create_client(self) -> genai.Client:
        """Vertex AI 클라이언트 생성 (ADC 사용)"""
        # Application Default Credentials (ADC) 사용
        # gcloud auth application-default login 으로 인증 필요
        logger.info("[S2ST] Using Vertex AI with Application Default Credentials")
        return genai.Client(
            vertexai=True,
            project="gen-lang-client-0315513596",
            location="us-central1"
        )

    async def connect(self):
        """Gemini S2ST 세션 연결"""
        if self._is_connected:
            return

        try:
            self._client = self._create_client()

            config = self._get_config()

            # S2ST 모델로 연결
            self._session_context = self._client.aio.live.connect(
                model=self._settings.gemini_s2st_model,
                config=config
            )
            self._session = await self._session_context.__aenter__()
            self._is_connected = True
            self._receive_task = asyncio.create_task(self._receive_loop())
            logger.info(f"[S2ST] Session connected for user {self.user_id}")

        except Exception as e:
            logger.error(f"[S2ST] Connection failed: {e}")
            if self.on_error:
                await self.on_error(f"S2ST connection failed: {str(e)}")
            raise

    async def disconnect(self):
        """세션 종료"""
        self._is_closing = True
        self._is_connected = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._session_context:
            try:
                await self._session_context.__aexit__(None, None, None)
            except Exception:
                pass
            self._session_context = None
            self._session = None

        logger.info(f"[S2ST] Session disconnected for user {self.user_id}")

    async def _cleanup_session(self):
        """재연결을 위한 세션 정리"""
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._session_context:
            try:
                await self._session_context.__aexit__(None, None, None)
            except Exception:
                pass
            self._session_context = None
            self._session = None
        self._is_connected = False

    async def reconnect(self) -> bool:
        """세션 재연결"""
        async with self._reconnect_lock:
            if self._is_closing:
                return False

            logger.info(f"[S2ST] Reconnecting session for user {self.user_id}...")
            await self._cleanup_session()

            try:
                self._client = self._create_client()
                config = self._get_config()

                self._session_context = self._client.aio.live.connect(
                    model=self._settings.gemini_s2st_model,
                    config=config
                )
                self._session = await self._session_context.__aenter__()
                self._is_connected = True
                self._receive_task = asyncio.create_task(self._receive_loop())
                logger.info(f"[S2ST] Session reconnected for user {self.user_id}")
                return True

            except Exception as e:
                logger.error(f"[S2ST] Reconnection failed: {e}")
                return False

    async def send_audio(self, audio_data: bytes):
        """오디오 데이터 전송"""
        if self._is_closing:
            return

        if not self._is_connected or not self._session:
            if not await self.reconnect():
                return

        try:
            logger.info(f"[S2ST] Sending audio: {len(audio_data)} bytes")
            await self._session.send(
                input=types.LiveClientRealtimeInput(
                    media_chunks=[
                        types.Blob(
                            mime_type="audio/pcm;rate=16000",
                            data=audio_data
                        )
                    ]
                )
            )
            logger.info(f"[S2ST] Audio sent successfully")
        except Exception as e:
            error_str = str(e)
            if "1011" in error_str or "timeout" in error_str.lower() or "closed" in error_str.lower():
                logger.warning("[S2ST] Connection lost, attempting reconnect...")
                self._is_connected = False
                if await self.reconnect():
                    try:
                        await self._session.send(
                            input=types.LiveClientRealtimeInput(
                                media_chunks=[
                                    types.Blob(
                                        mime_type="audio/pcm;rate=16000",
                                        data=audio_data
                                    )
                                ]
                            )
                        )
                    except Exception as retry_error:
                        if self.on_error:
                            await self.on_error(f"Failed to send after reconnect: {str(retry_error)}")
            else:
                if self.on_error:
                    await self.on_error(f"Failed to send audio: {error_str}")

    async def end_turn(self):
        """오디오 입력 종료 신호 전송 - Gemini가 응답하도록"""
        if self._is_closing or not self._is_connected or not self._session:
            return

        try:
            logger.info(f"[S2ST] Sending end-of-turn signal for user {self.user_id}")
            # Send turn complete signal to Gemini using LiveClientContent
            await self._session.send(
                input=types.LiveClientContent(
                    turn_complete=True
                )
            )
            logger.info(f"[S2ST] End-of-turn signal sent successfully")
        except Exception as e:
            logger.error(f"[S2ST] Failed to send end-of-turn signal: {e}")

    async def reset(self):
        """세션 리셋 (새 녹음 턴)"""
        self._current_input_text = ""
        self._current_output_text = ""
        logger.info(f"[S2ST] Session reset for user {self.user_id}")

    def change_language(self, mode: TranslationMode):
        """번역 모드 변경 (다음 연결 시 적용)"""
        self.translation_mode = mode
        logger.info(f"[S2ST] Language mode changed to {mode} for user {self.user_id}")

    async def _receive_loop(self):
        """응답 수신 루프"""
        if not self._session:
            return

        logger.info("[S2ST] Receive loop started")
        try:
            async for response in self._session.receive():
                if not self._is_connected or self._is_closing:
                    break

                # Log response structure
                logger.info(f"[S2ST] Received response: data={bool(response.data)}, server_content={bool(response.server_content)}")

                # 오디오 데이터 처리
                if response.data:
                    logger.info(f"[S2ST] Received audio: {len(response.data)} bytes")
                    if self.on_audio:
                        await self.on_audio(response.data)

                # 서버 컨텐츠 처리 (자막)
                if response.server_content:
                    content = response.server_content

                    # 입력 자막 (원본 음성 인식)
                    if hasattr(content, 'input_transcription') and content.input_transcription:
                        if content.input_transcription.text:
                            text = content.input_transcription.text
                            self._current_input_text = text
                            logger.info(f"[S2ST] Input: '{text}'")

                            if self.on_transcript:
                                # is_final은 turn_complete로 판단 (None 방지를 위해 bool 변환)
                                is_final = bool(getattr(content, 'turn_complete', False))
                                await self.on_transcript(text, is_final, self._current_output_text if is_final else None)

                    # 출력 자막 (번역된 음성) - 실시간 표시
                    if hasattr(content, 'output_transcription') and content.output_transcription:
                        if content.output_transcription.text:
                            text = content.output_transcription.text
                            self._current_output_text = text
                            logger.info(f"[S2ST] Output: '{text}'")
                            # 번역 결과를 실시간으로 전송 (input이 없어도)
                            print(f"[S2ST] Calling on_transcript callback: {self.on_transcript is not None}")
                            logger.info(f"[S2ST] Calling on_transcript callback: {self.on_transcript is not None}")
                            if self.on_transcript:
                                try:
                                    print(f"[S2ST] About to call on_transcript with: text='', is_final=False, translated_text='{text}'")
                                    await self.on_transcript(
                                        "",  # input은 비어있음 (Gemini Native Audio는 input_transcription 미지원)
                                        False,  # 아직 완료되지 않음
                                        text  # 번역된 텍스트
                                    )
                                    print(f"[S2ST] on_transcript callback completed successfully")
                                    logger.info(f"[S2ST] on_transcript callback completed")
                                except Exception as e:
                                    print(f"[S2ST] on_transcript callback error: {e}")
                                    import traceback
                                    traceback.print_exc()
                                    logger.error(f"[S2ST] on_transcript callback error: {e}")

                    # 턴 완료 시 최종 결과 전송
                    if getattr(content, 'turn_complete', False):
                        logger.info(f"[S2ST] Turn complete - input: '{self._current_input_text}', output: '{self._current_output_text}'")
                        # input이 없어도 output이 있으면 전송
                        if self.on_transcript and (self._current_input_text or self._current_output_text):
                            await self.on_transcript(
                                self._current_input_text or "(음성 입력)",
                                True,
                                self._current_output_text
                            )
                        # 버퍼 초기화
                        self._current_input_text = ""
                        self._current_output_text = ""

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._is_connected = False
            error_str = str(e)
            if "timeout" not in error_str.lower() and "1011" not in error_str:
                if self.on_error and not self._is_closing:
                    await self.on_error(f"Receive error: {error_str}")
            logger.error(f"[S2ST] Receive loop ended: {error_str}")

    @property
    def is_connected(self) -> bool:
        return self._is_connected


class GeminiS2STSessionManager:
    """S2ST 세션 관리자"""

    def __init__(self):
        # room_id -> user_id -> GeminiS2STSession
        self._sessions: dict[str, dict[str, GeminiS2STSession]] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        room_id: str,
        user_id: str,
        translation_mode: TranslationMode,
        on_audio: Optional[Callable[[bytes], Awaitable[None]]] = None,
        on_transcript: Optional[Callable[[str, bool, Optional[str]], Awaitable[None]]] = None,
        on_error: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> GeminiS2STSession:
        """새 S2ST 세션 생성"""
        async with self._lock:
            if room_id not in self._sessions:
                self._sessions[room_id] = {}

            session = GeminiS2STSession(
                user_id=user_id,
                translation_mode=translation_mode,
                on_audio=on_audio,
                on_transcript=on_transcript,
                on_error=on_error,
            )
            self._sessions[room_id][user_id] = session
            await session.connect()
            return session

    async def get_session(self, room_id: str, user_id: str) -> Optional[GeminiS2STSession]:
        """세션 조회"""
        if room_id in self._sessions:
            return self._sessions[room_id].get(user_id)
        return None

    async def remove_session(self, room_id: str, user_id: str):
        """세션 제거"""
        async with self._lock:
            if room_id in self._sessions:
                session = self._sessions[room_id].pop(user_id, None)
                if session:
                    await session.disconnect()
                if not self._sessions[room_id]:
                    del self._sessions[room_id]

    async def remove_all_sessions(self, room_id: str):
        """방의 모든 세션 제거"""
        async with self._lock:
            if room_id in self._sessions:
                for session in self._sessions[room_id].values():
                    await session.disconnect()
                del self._sessions[room_id]


# 싱글톤 인스턴스
gemini_s2st_session_manager = GeminiS2STSessionManager()
