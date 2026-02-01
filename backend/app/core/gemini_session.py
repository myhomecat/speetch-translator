import asyncio
import base64
import logging
from typing import Optional, Callable, Awaitable
from google import genai
from google.genai import types
from ..config import get_settings
from ..models.room import TranslationMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


SYSTEM_INSTRUCTIONS = {
    TranslationMode.AUTO: """You are a real-time speech translator.
When you hear Korean, translate and speak in Japanese.
When you hear Japanese, translate and speak in Korean.
Preserve the speaker's tone, emotion, and speaking style.
Respond naturally and fluently in the target language.
Do not add any explanations - just translate and speak.""",

    TranslationMode.KO_TO_JA: """You are a real-time Korean to Japanese speech translator.
Listen to Korean speech and translate it to Japanese.
Preserve the speaker's tone, emotion, and speaking style.
Respond naturally and fluently in Japanese.
Do not add any explanations - just translate and speak in Japanese.""",

    TranslationMode.JA_TO_KO: """You are a real-time Japanese to Korean speech translator.
Listen to Japanese speech and translate it to Korean.
Preserve the speaker's tone, emotion, and speaking style.
Respond naturally and fluently in Korean.
Do not add any explanations - just translate and speak in Korean."""
}


class GeminiSession:
    def __init__(
        self,
        user_id: str,
        translation_mode: TranslationMode = TranslationMode.AUTO,
        on_audio: Optional[Callable[[bytes], Awaitable[None]]] = None,
        on_transcript: Optional[Callable[[str, str, str, str], Awaitable[None]]] = None,
        on_error: Optional[Callable[[str], Awaitable[None]]] = None,
    ):
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

    async def connect(self):
        if self._is_connected:
            return

        self._client = genai.Client(api_key=self._settings.gemini_api_key)

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(
                parts=[types.Part(text=SYSTEM_INSTRUCTIONS[self.translation_mode])]
            ),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Aoede"
                    )
                )
            ),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=False,
                    start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
                    end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                    silence_duration_ms=2000,
                    prefix_padding_ms=500,
                )
            ),
        )

        # aio.live.connect returns an async context manager
        self._session_context = self._client.aio.live.connect(
            model=self._settings.gemini_model,
            config=config
        )
        self._session = await self._session_context.__aenter__()
        self._is_connected = True
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def disconnect(self):
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

    async def _cleanup_session(self):
        """Clean up session without setting _is_closing flag (for reconnection)"""
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

    async def reconnect(self):
        """Reconnect to Gemini session"""
        async with self._reconnect_lock:
            if self._is_closing:
                return False

            print(f"Reconnecting Gemini session for user {self.user_id}...")
            await self._cleanup_session()

            try:
                self._client = genai.Client(api_key=self._settings.gemini_api_key)

                config = types.LiveConnectConfig(
                    response_modalities=["AUDIO"],
                    system_instruction=types.Content(
                        parts=[types.Part(text=SYSTEM_INSTRUCTIONS[self.translation_mode])]
                    ),
                    input_audio_transcription=types.AudioTranscriptionConfig(),
                    output_audio_transcription=types.AudioTranscriptionConfig(),
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name="Aoede"
                            )
                        )
                    ),
                    realtime_input_config=types.RealtimeInputConfig(
                        automatic_activity_detection=types.AutomaticActivityDetection(
                            disabled=False,
                            start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
                            end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                            silence_duration_ms=2000,
                            prefix_padding_ms=500,
                        )
                    ),
                )

                self._session_context = self._client.aio.live.connect(
                    model=self._settings.gemini_model,
                    config=config
                )
                self._session = await self._session_context.__aenter__()
                self._is_connected = True
                print(f"Gemini session reconnected for user {self.user_id}, starting receive loop...")
                self._receive_task = asyncio.create_task(self._receive_loop())
                print(f"Receive loop task created: {self._receive_task}")
                return True
            except Exception as e:
                print(f"Failed to reconnect Gemini session: {e}")
                return False

    async def send_audio(self, audio_data: bytes):
        if self._is_closing:
            return

        # Try to reconnect if not connected
        if not self._is_connected or not self._session:
            if not await self.reconnect():
                return

        try:
            print(f"[Gemini] Sending {len(audio_data)} bytes to Gemini...")
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
        except Exception as e:
            error_str = str(e)
            # Check if it's a connection error that requires reconnection
            if "1011" in error_str or "timeout" in error_str.lower() or "closed" in error_str.lower():
                print(f"Connection lost, attempting to reconnect...")
                self._is_connected = False
                # Try to reconnect and resend
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
                        return  # Success after reconnect
                    except Exception as retry_error:
                        if self.on_error:
                            await self.on_error(f"Failed to send audio after reconnect: {str(retry_error)}")
            else:
                if self.on_error:
                    await self.on_error(f"Failed to send audio: {error_str}")

    async def end_audio_stream(self):
        """Send audio stream end signal to trigger Gemini response"""
        if self._is_closing or not self._is_connected or not self._session:
            return

        try:
            print("[Gemini] Sending audio stream end signal...")
            await self._session.send(
                input=types.LiveClientRealtimeInput(
                    audio_stream_end=True
                )
            )
        except Exception as e:
            print(f"[Gemini] Error sending audio stream end: {e}")

    async def _receive_loop(self):
        if not self._session:
            print("[Gemini] Receive loop: no session")
            return

        print("[Gemini] Receive loop started")
        try:
            async for response in self._session.receive():
                if not self._is_connected or self._is_closing:
                    print("[Gemini] Receive loop: breaking due to disconnect")
                    break

                # Debug: print full response structure
                print(f"[Gemini] Response received: data={response.data is not None}, server_content={response.server_content is not None}")

                # Handle audio response (raw data) - this is the primary audio source
                if response.data:
                    print(f"[Gemini] Received audio: {len(response.data)} bytes")
                    if self.on_audio:
                        await self.on_audio(response.data)

                # Handle server content (transcriptions only, audio already handled above)
                if response.server_content:
                    content = response.server_content
                    print(f"[Gemini] server_content: input_trans={hasattr(content, 'input_transcription') and content.input_transcription is not None}, output_trans={hasattr(content, 'output_transcription') and content.output_transcription is not None}, turn_complete={getattr(content, 'turn_complete', None)}")

                    # Handle input transcription (what user said)
                    if hasattr(content, 'input_transcription') and content.input_transcription:
                        if self.on_transcript and content.input_transcription.text:
                            original_lang = self._get_original_language()
                            print(f"[Gemini] Input transcription: '{content.input_transcription.text}'")
                            await self.on_transcript(
                                content.input_transcription.text,
                                original_lang,
                                "",  # translated text
                                ""   # translated language
                            )

                    # Handle output transcription (translated speech)
                    if hasattr(content, 'output_transcription') and content.output_transcription:
                        if self.on_transcript and content.output_transcription.text:
                            translated_lang = self._get_translated_language()
                            await self.on_transcript(
                                "",  # original text
                                "",  # original language
                                content.output_transcription.text,
                                translated_lang
                            )

        except asyncio.CancelledError:
            pass
        except Exception as e:
            # Mark as disconnected so next send_audio will trigger reconnect
            self._is_connected = False
            error_str = str(e)
            # Don't report timeout errors as they're expected when idle
            if "timeout" not in error_str.lower() and "1011" not in error_str:
                if self.on_error and not self._is_closing:
                    await self.on_error(f"Receive error: {error_str}")
            print(f"Receive loop ended: {error_str}")

    def _get_original_language(self) -> str:
        if self.translation_mode == TranslationMode.KO_TO_JA:
            return "ko"
        elif self.translation_mode == TranslationMode.JA_TO_KO:
            return "ja"
        return "auto"

    def _get_translated_language(self) -> str:
        if self.translation_mode == TranslationMode.KO_TO_JA:
            return "ja"
        elif self.translation_mode == TranslationMode.JA_TO_KO:
            return "ko"
        return "auto"

    @property
    def is_connected(self) -> bool:
        return self._is_connected


class GeminiSessionManager:
    def __init__(self):
        # room_id -> user_id -> GeminiSession
        self._sessions: dict[str, dict[str, GeminiSession]] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        room_id: str,
        user_id: str,
        translation_mode: TranslationMode,
        on_audio: Optional[Callable[[bytes], Awaitable[None]]] = None,
        on_transcript: Optional[Callable[[str, str, str, str], Awaitable[None]]] = None,
        on_error: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> GeminiSession:
        async with self._lock:
            if room_id not in self._sessions:
                self._sessions[room_id] = {}

            session = GeminiSession(
                user_id=user_id,
                translation_mode=translation_mode,
                on_audio=on_audio,
                on_transcript=on_transcript,
                on_error=on_error,
            )
            self._sessions[room_id][user_id] = session
            await session.connect()
            return session

    async def get_session(
        self,
        room_id: str,
        user_id: str
    ) -> Optional[GeminiSession]:
        if room_id in self._sessions:
            return self._sessions[room_id].get(user_id)
        return None

    async def remove_session(self, room_id: str, user_id: str):
        async with self._lock:
            if room_id in self._sessions:
                session = self._sessions[room_id].pop(user_id, None)
                if session:
                    await session.disconnect()
                if not self._sessions[room_id]:
                    del self._sessions[room_id]

    async def remove_all_sessions(self, room_id: str):
        async with self._lock:
            if room_id in self._sessions:
                for session in self._sessions[room_id].values():
                    await session.disconnect()
                del self._sessions[room_id]


# Singleton instance
gemini_session_manager = GeminiSessionManager()
