"""
AssemblyAI Realtime STT Session Manager
실시간 음성 인식을 위한 AssemblyAI 세션 관리
"""
import asyncio
from typing import Callable, Optional
from ..config import get_settings

# AssemblyAI SDK uses synchronous WebSocket, we'll use their async approach
import assemblyai as aai


class AssemblyAISession:
    """사용자별 AssemblyAI 실시간 세션"""

    def __init__(
        self,
        user_id: str,
        on_transcript: Callable[[str, bool], None],  # (text, is_final)
        on_error: Optional[Callable[[str], None]] = None,
    ):
        self.user_id = user_id
        self._on_transcript = on_transcript
        self._on_error = on_error
        self._transcriber: Optional[aai.RealtimeTranscriber] = None
        self._is_connected = False
        self._loop = asyncio.get_event_loop()

    async def connect(self):
        """AssemblyAI 실시간 세션 연결"""
        settings = get_settings()

        if not settings.assemblyai_api_key:
            raise ValueError("ASSEMBLYAI_API_KEY is not configured")

        aai.settings.api_key = settings.assemblyai_api_key

        def on_data(transcript: aai.RealtimeTranscript):
            if not transcript.text:
                return

            is_final = isinstance(transcript, aai.RealtimeFinalTranscript)

            # 비동기 콜백을 이벤트 루프에서 실행
            asyncio.run_coroutine_threadsafe(
                self._on_transcript(transcript.text, is_final),
                self._loop
            )

        def on_error(error: aai.RealtimeError):
            if self._on_error:
                asyncio.run_coroutine_threadsafe(
                    self._on_error(f"AssemblyAI error: {error}"),
                    self._loop
                )

        def on_open(session_opened: aai.RealtimeSessionOpened):
            print(f"[AssemblyAI] Session opened for user {self.user_id}")
            self._is_connected = True

        def on_close():
            print(f"[AssemblyAI] Session closed for user {self.user_id}")
            self._is_connected = False

        self._transcriber = aai.RealtimeTranscriber(
            sample_rate=16000,
            on_data=on_data,
            on_error=on_error,
            on_open=on_open,
            on_close=on_close,
            encoding=aai.AudioEncoding.pcm_s16le,
        )

        # 연결 (별도 스레드에서 실행)
        await asyncio.to_thread(self._transcriber.connect)

    async def send_audio(self, audio_data: bytes):
        """오디오 데이터 전송"""
        if self._transcriber and self._is_connected:
            await asyncio.to_thread(self._transcriber.stream, audio_data)

    async def disconnect(self):
        """세션 종료"""
        if self._transcriber:
            try:
                await asyncio.to_thread(self._transcriber.close)
            except Exception as e:
                print(f"[AssemblyAI] Error closing session: {e}")
            finally:
                self._transcriber = None
                self._is_connected = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected


class AssemblyAISessionManager:
    """방/사용자별 AssemblyAI 세션 관리"""

    def __init__(self):
        # room_id -> user_id -> AssemblyAISession
        self._sessions: dict[str, dict[str, AssemblyAISession]] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        room_id: str,
        user_id: str,
        on_transcript: Callable[[str, bool], None],
        on_error: Optional[Callable[[str], None]] = None,
    ) -> AssemblyAISession:
        """새 AssemblyAI 세션 생성"""
        async with self._lock:
            # 기존 세션 정리
            if room_id in self._sessions and user_id in self._sessions[room_id]:
                await self._sessions[room_id][user_id].disconnect()

            session = AssemblyAISession(
                user_id=user_id,
                on_transcript=on_transcript,
                on_error=on_error,
            )

            await session.connect()

            if room_id not in self._sessions:
                self._sessions[room_id] = {}
            self._sessions[room_id][user_id] = session

            return session

    async def get_session(
        self,
        room_id: str,
        user_id: str
    ) -> Optional[AssemblyAISession]:
        """세션 조회"""
        if room_id in self._sessions:
            return self._sessions[room_id].get(user_id)
        return None

    async def remove_session(self, room_id: str, user_id: str):
        """세션 제거"""
        async with self._lock:
            if room_id in self._sessions and user_id in self._sessions[room_id]:
                session = self._sessions[room_id].pop(user_id)
                await session.disconnect()

                if not self._sessions[room_id]:
                    del self._sessions[room_id]

    async def remove_room_sessions(self, room_id: str):
        """방의 모든 세션 제거"""
        async with self._lock:
            if room_id in self._sessions:
                for session in self._sessions[room_id].values():
                    await session.disconnect()
                del self._sessions[room_id]


# Singleton instance
assemblyai_session_manager = AssemblyAISessionManager()
