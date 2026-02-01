import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Callable, Awaitable
from pathlib import Path
from vosk import Model, KaldiRecognizer
from ..models.room import TranslationMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Thread pool for Vosk (synchronous API)
_executor = ThreadPoolExecutor(max_workers=4)

# Model paths
MODELS_DIR = Path(__file__).parent.parent.parent / "models"
MODEL_PATHS = {
    "ko": MODELS_DIR / "vosk-model-small-ko-0.22",
    "ja": MODELS_DIR / "vosk-model-small-ja-0.22",
}

# Cached models (loaded once, reused)
_loaded_models: dict[str, Model] = {}


def _load_model(lang: str) -> Model:
    """Load Vosk model for the specified language (cached)"""
    if lang not in _loaded_models:
        model_path = MODEL_PATHS.get(lang)
        if not model_path or not model_path.exists():
            raise ValueError(f"Model not found for language: {lang} at {model_path}")
        logger.info(f"Loading Vosk model for {lang} from {model_path}")
        _loaded_models[lang] = Model(str(model_path))
        logger.info(f"Vosk model for {lang} loaded successfully")
    return _loaded_models[lang]


def preload_models():
    """Preload all models at startup"""
    for lang in MODEL_PATHS.keys():
        try:
            _load_model(lang)
        except Exception as e:
            logger.error(f"Failed to preload model for {lang}: {e}")


class VoskSession:
    """Vosk STT session for a single user"""

    SAMPLE_RATE = 16000  # Must match client audio format

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

        self._recognizer: Optional[KaldiRecognizer] = None
        self._is_connected = False
        self._loop = asyncio.get_event_loop()

        # Determine which language to recognize based on mode
        self._source_lang = self._get_source_language()

    def _get_source_language(self) -> str:
        """Get source language based on translation mode"""
        if self.translation_mode == TranslationMode.KO_TO_JA:
            return "ko"
        elif self.translation_mode == TranslationMode.JA_TO_KO:
            return "ja"
        else:
            # AUTO mode: default to Korean, but could be enhanced
            # to detect language dynamically
            return "ko"

    async def connect(self):
        """Initialize Vosk recognizer"""
        if self._is_connected:
            return

        try:
            model = _load_model(self._source_lang)
            self._recognizer = KaldiRecognizer(model, self.SAMPLE_RATE)
            self._recognizer.SetWords(True)  # Enable word-level timing
            self._is_connected = True
            logger.info(f"[Vosk] Session created for user {self.user_id}, lang={self._source_lang}")
        except Exception as e:
            logger.error(f"[Vosk] Failed to create session: {e}")
            if self.on_error:
                await self.on_error(f"Vosk initialization error: {str(e)}")
            raise

    async def disconnect(self):
        """Clean up Vosk session"""
        self._is_connected = False
        if self._recognizer:
            # Get final result before closing
            try:
                final_result = await self._loop.run_in_executor(
                    _executor, self._recognizer.FinalResult
                )
                result_data = json.loads(final_result)
                if result_data.get("text"):
                    if self.on_transcript:
                        await self.on_transcript(result_data["text"], True)
            except Exception as e:
                logger.error(f"[Vosk] Error getting final result: {e}")
            self._recognizer = None
        logger.info(f"[Vosk] Session disconnected for user {self.user_id}")

    async def send_audio(self, audio_data: bytes):
        """Process audio data through Vosk"""
        if not self._is_connected or not self._recognizer:
            return

        try:
            # Run synchronous Vosk API in thread pool
            is_final = await self._loop.run_in_executor(
                _executor,
                self._recognizer.AcceptWaveform,
                audio_data
            )

            if is_final:
                # Complete utterance detected
                result = await self._loop.run_in_executor(
                    _executor, self._recognizer.Result
                )
                result_data = json.loads(result)
                text = result_data.get("text", "")
                if text and self.on_transcript:
                    logger.info(f"[Vosk] Final: {text}")
                    await self.on_transcript(text, True)
            else:
                # Partial result (still speaking)
                partial = await self._loop.run_in_executor(
                    _executor, self._recognizer.PartialResult
                )
                partial_data = json.loads(partial)
                text = partial_data.get("partial", "")
                if text and self.on_transcript:
                    logger.debug(f"[Vosk] Partial: {text}")
                    await self.on_transcript(text, False)

        except Exception as e:
            logger.error(f"[Vosk] Error processing audio: {e}")
            if self.on_error:
                await self.on_error(f"Vosk processing error: {str(e)}")

    async def reset(self):
        """Reset the recognizer for a new utterance"""
        if self._recognizer:
            try:
                # Get any remaining result
                final_result = await self._loop.run_in_executor(
                    _executor, self._recognizer.FinalResult
                )
                result_data = json.loads(final_result)
                if result_data.get("text") and self.on_transcript:
                    await self.on_transcript(result_data["text"], True)

                # Recreate recognizer
                model = _load_model(self._source_lang)
                self._recognizer = KaldiRecognizer(model, self.SAMPLE_RATE)
                self._recognizer.SetWords(True)
                logger.info(f"[Vosk] Session reset for user {self.user_id}")
            except Exception as e:
                logger.error(f"[Vosk] Error resetting session: {e}")

    def change_language(self, new_mode: TranslationMode):
        """Change the source language based on new translation mode"""
        self.translation_mode = new_mode
        new_lang = self._get_source_language()

        if new_lang != self._source_lang:
            self._source_lang = new_lang
            try:
                model = _load_model(self._source_lang)
                self._recognizer = KaldiRecognizer(model, self.SAMPLE_RATE)
                self._recognizer.SetWords(True)
                logger.info(f"[Vosk] Language changed to {new_lang} for user {self.user_id}")
            except Exception as e:
                logger.error(f"[Vosk] Error changing language: {e}")

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def source_language(self) -> str:
        return self._source_lang


class VoskSessionManager:
    """Manager for Vosk sessions"""

    def __init__(self):
        # room_id -> user_id -> VoskSession
        self._sessions: dict[str, dict[str, VoskSession]] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        room_id: str,
        user_id: str,
        translation_mode: TranslationMode,
        on_transcript: Optional[Callable[[str, bool], Awaitable[None]]] = None,
        on_error: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> VoskSession:
        """Create a new Vosk session"""
        async with self._lock:
            if room_id not in self._sessions:
                self._sessions[room_id] = {}

            # Remove existing session if any
            if user_id in self._sessions[room_id]:
                old_session = self._sessions[room_id][user_id]
                await old_session.disconnect()

            session = VoskSession(
                user_id=user_id,
                translation_mode=translation_mode,
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
    ) -> Optional[VoskSession]:
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
vosk_session_manager = VoskSessionManager()
