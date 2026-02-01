"""
Google Cloud Text-to-Speech Session

번역된 텍스트를 음성으로 변환합니다.
- 입력: 번역된 텍스트 (한국어/일본어)
- 출력: 음성 바이트 (PCM 또는 MP3)
"""
import asyncio
import logging
from typing import Optional
from google.cloud import texttospeech_v1 as texttospeech
from ..config import get_settings
from ..models.room import TranslationMode

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TTSSession:
    """Google Cloud TTS 세션"""

    def __init__(
        self,
        user_id: str,
        translation_mode: TranslationMode = TranslationMode.AUTO,
    ):
        """
        Args:
            user_id: 사용자 ID
            translation_mode: 번역 모드 (출력 언어 결정)
        """
        self.user_id = user_id
        self.translation_mode = translation_mode
        self._settings = get_settings()
        self._client: Optional[texttospeech.TextToSpeechAsyncClient] = None

    async def connect(self):
        """TTS 클라이언트 초기화"""
        try:
            self._client = texttospeech.TextToSpeechAsyncClient()
            logger.info(f"[TTS] Session initialized for user {self.user_id}")
        except Exception as e:
            logger.error(f"[TTS] Failed to initialize: {e}")
            raise

    async def disconnect(self):
        """세션 종료"""
        self._client = None
        logger.info(f"[TTS] Session disconnected for user {self.user_id}")

    def _get_voice_config(self) -> tuple[str, str]:
        """번역 모드에 따른 음성 설정 반환"""
        if self.translation_mode == TranslationMode.KO_TO_JA:
            # 한국어 → 일본어: 일본어 TTS
            return "ja-JP", "ja-JP-Neural2-B"  # 여성 음성
        elif self.translation_mode == TranslationMode.JA_TO_KO:
            # 일본어 → 한국어: 한국어 TTS
            return "ko-KR", "ko-KR-Neural2-A"  # 여성 음성
        else:
            # AUTO: 기본값 일본어 (한국어 입력 가정)
            return "ja-JP", "ja-JP-Neural2-B"

    async def synthesize(self, text: str, target_language: str = None) -> bytes:
        """
        텍스트를 음성으로 변환

        Args:
            text: 변환할 텍스트
            target_language: 대상 언어 (ko, ja) - None이면 translation_mode 사용

        Returns:
            음성 바이트 (Linear16 PCM, 24kHz)
        """
        if not self._client:
            await self.connect()

        if not text.strip():
            return b""

        # 언어 설정
        if target_language:
            if target_language == "ko":
                language_code, voice_name = "ko-KR", "ko-KR-Neural2-A"
            elif target_language == "ja":
                language_code, voice_name = "ja-JP", "ja-JP-Neural2-B"
            else:
                language_code, voice_name = self._get_voice_config()
        else:
            language_code, voice_name = self._get_voice_config()

        try:
            # 요청 생성
            synthesis_input = texttospeech.SynthesisInput(text=text)

            voice = texttospeech.VoiceSelectionParams(
                language_code=language_code,
                name=voice_name,
            )

            # Linear16 PCM 출력 (24kHz)
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                sample_rate_hertz=self._settings.output_sample_rate,
            )

            # TTS 요청
            response = await self._client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config,
            )

            logger.info(f"[TTS] Synthesized {len(response.audio_content)} bytes for '{text[:30]}...'")
            return response.audio_content

        except Exception as e:
            logger.error(f"[TTS] Synthesis failed: {e}")
            return b""

    def change_language(self, mode: TranslationMode):
        """번역 모드 변경"""
        self.translation_mode = mode
        logger.info(f"[TTS] Language mode changed to {mode} for user {self.user_id}")


class TTSSessionManager:
    """TTS 세션 관리자"""

    def __init__(self):
        # room_id -> user_id -> TTSSession
        self._sessions: dict[str, dict[str, TTSSession]] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        room_id: str,
        user_id: str,
        translation_mode: TranslationMode,
    ) -> TTSSession:
        """새 TTS 세션 생성"""
        async with self._lock:
            if room_id not in self._sessions:
                self._sessions[room_id] = {}

            session = TTSSession(
                user_id=user_id,
                translation_mode=translation_mode,
            )
            self._sessions[room_id][user_id] = session
            await session.connect()
            return session

    async def get_session(self, room_id: str, user_id: str) -> Optional[TTSSession]:
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
tts_session_manager = TTSSessionManager()
