"""
Soniox Real-time STT + Translation Session

Soniox WebSocket API를 사용하여 실시간 음성 인식 및 번역을 수행합니다.
- 입력: 음성 (한국어/일본어)
- 출력: 번역된 텍스트 (실시간 스트리밍)

TTS는 별도의 Google Cloud TTS를 사용합니다.
"""
import asyncio
import json
import logging
from typing import Optional, Callable, Awaitable
from websockets.asyncio.client import connect
from ..config import get_settings
from ..models.room import TranslationMode

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Soniox WebSocket 엔드포인트
SONIOX_WS_URL = "wss://stt-rt.soniox.com/transcribe-websocket"


class SonioxSession:
    """Soniox 실시간 STT + 번역 세션"""

    def __init__(
        self,
        user_id: str,
        translation_mode: TranslationMode = TranslationMode.AUTO,
        on_transcript: Optional[Callable[[str, bool, Optional[str]], Awaitable[None]]] = None,
        on_error: Optional[Callable[[str], Awaitable[None]]] = None,
    ):
        """
        Args:
            user_id: 사용자 ID
            translation_mode: 번역 모드 (auto, ko_to_ja, ja_to_ko)
            on_transcript: 자막 콜백 (text, is_final, translated_text, speaker)
            on_error: 에러 콜백
        """
        self.user_id = user_id
        self.translation_mode = translation_mode
        self.on_transcript = on_transcript
        self.on_error = on_error

        self._settings = get_settings()
        self._ws = None
        self._is_connected = False
        self._is_closing = False
        self._receive_task: Optional[asyncio.Task] = None
        self._reconnect_lock = asyncio.Lock()

        # 확정된 텍스트 버퍼 (is_final=True인 토큰만)
        self._confirmed_text = ""
        self._confirmed_translation = ""
        # 임시 텍스트 버퍼 (is_final=False인 토큰, 덮어쓰기됨)
        self._pending_text = ""
        self._pending_translation = ""
        # 현재 화자 번호 (diarization 활성 시 토큰의 speaker 필드)
        self._current_speaker: Optional[int] = None

    def _get_config(self) -> dict:
        """Soniox WebSocket 설정 생성"""
        # 번역 모드에 따른 설정
        if self.translation_mode == TranslationMode.KO_TO_JA:
            # 한국어 → 일본어
            translation_config = {
                "type": "one_way",
                "target_language": "ja"
            }
            language_hints = ["ko"]
        elif self.translation_mode == TranslationMode.JA_TO_KO:
            # 일본어 → 한국어
            translation_config = {
                "type": "one_way",
                "target_language": "ko"
            }
            language_hints = ["ja"]
        else:
            # AUTO: 양방향 번역
            translation_config = {
                "type": "two_way",
                "language_a": "ko",
                "language_b": "ja"
            }
            language_hints = ["ko", "ja"]

        config = {
            "api_key": self._settings.soniox_api_key,
            "model": self._settings.soniox_model,
            "audio_format": "s16le",  # 16-bit signed little-endian PCM
            "sample_rate": self._settings.input_sample_rate,
            "num_channels": 1,
            "language_hints": language_hints,
            "translation": translation_config,
            "enable_endpoint_detection": True,
        }
        if self._settings.enable_speaker_diarization:
            config["enable_speaker_diarization"] = True
        return config

    async def connect(self):
        """Soniox WebSocket 연결"""
        if self._is_connected:
            return

        try:
            logger.info(f"[Soniox] Connecting for user {self.user_id}...")
            # ping_interval=None로 클라이언트 측 ping 비활성화 (Soniox 서버가 관리)
            self._ws = await connect(SONIOX_WS_URL, ping_interval=None, ping_timeout=None)

            # 설정 전송
            config = self._get_config()
            await self._ws.send(json.dumps(config))
            logger.info(f"[Soniox] Config sent: {config}")

            # 첫 응답 확인 (연결 성공 여부)
            response = await self._ws.recv()
            response_data = json.loads(response)
            logger.info(f"[Soniox] Initial response: {response_data}")

            if "error" in response_data:
                raise Exception(f"Soniox connection error: {response_data['error']}")

            self._is_connected = True
            self._receive_task = asyncio.create_task(self._receive_loop())
            logger.info(f"[Soniox] Session connected for user {self.user_id}")

        except Exception as e:
            logger.error(f"[Soniox] Connection failed: {e}")
            if self.on_error:
                await self.on_error(f"Soniox connection failed: {str(e)}")
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

        if self._ws:
            try:
                # 빈 프레임 전송하여 정상 종료
                await self._ws.send(b"")
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        logger.info(f"[Soniox] Session disconnected for user {self.user_id}")

    async def reconnect(self) -> bool:
        """세션 재연결"""
        async with self._reconnect_lock:
            if self._is_closing:
                return False

            logger.info(f"[Soniox] Reconnecting session for user {self.user_id}...")

            # 기존 연결 정리
            if self._receive_task:
                self._receive_task.cancel()
                try:
                    await self._receive_task
                except asyncio.CancelledError:
                    pass
                self._receive_task = None

            if self._ws:
                try:
                    await self._ws.close()
                except Exception:
                    pass
                self._ws = None

            self._is_connected = False

            try:
                await self.connect()
                return True
            except Exception as e:
                logger.error(f"[Soniox] Reconnection failed: {e}")
                return False

    async def send_audio(self, audio_data: bytes):
        """오디오 데이터 전송"""
        if self._is_closing:
            return

        if not self._is_connected or not self._ws:
            if not await self.reconnect():
                return

        try:
            await self._ws.send(audio_data)
            logger.debug(f"[Soniox] Sent audio: {len(audio_data)} bytes")
        except Exception as e:
            error_str = str(e)
            logger.warning(f"[Soniox] Send error: {error_str}")
            self._is_connected = False
            if await self.reconnect():
                try:
                    await self._ws.send(audio_data)
                except Exception as retry_error:
                    if self.on_error:
                        await self.on_error(f"Failed to send after reconnect: {str(retry_error)}")

    async def _flush_buffers(self):
        """버퍼에 남은 텍스트를 is_final=True로 전송"""
        full_text = self._confirmed_text + self._pending_text
        full_translation = self._confirmed_translation + self._pending_translation

        if self.on_transcript and (full_text or full_translation):
            logger.info(f"[Soniox] Flushing buffers: text='{full_text[:50]}...', translation='{full_translation[:50]}...'")
            await self.on_transcript(full_text, True, full_translation, self._current_speaker)

        # 버퍼 초기화
        self._confirmed_text = ""
        self._confirmed_translation = ""
        self._pending_text = ""
        self._pending_translation = ""

    async def end_turn(self):
        """오디오 입력 종료 신호 (Soniox는 자동 endpoint detection 사용)"""
        logger.info(f"[Soniox] End turn signal for user {self.user_id}")
        await self._flush_buffers()

    async def reset(self):
        """세션 리셋"""
        self._confirmed_text = ""
        self._confirmed_translation = ""
        self._pending_text = ""
        self._pending_translation = ""
        self._current_speaker = None
        logger.info(f"[Soniox] Session reset for user {self.user_id}")

    def change_language(self, mode: TranslationMode):
        """번역 모드 변경 (재연결 필요)"""
        self.translation_mode = mode
        logger.info(f"[Soniox] Language mode changed to {mode} for user {self.user_id}")
        # 모드 변경 시 재연결 필요
        asyncio.create_task(self.reconnect())

    async def _receive_loop(self):
        """응답 수신 루프"""
        if not self._ws:
            return

        logger.info("[Soniox] Receive loop started")
        try:
            async for message in self._ws:
                if not self._is_connected or self._is_closing:
                    break

                try:
                    data = json.loads(message)
                    await self._process_response(data)
                except json.JSONDecodeError:
                    logger.warning(f"[Soniox] Non-JSON message received")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._is_connected = False
            error_str = str(e)
            logger.error(f"[Soniox] Receive loop ended: {error_str}")
            if self.on_error and not self._is_closing:
                await self.on_error(f"Receive error: {error_str}")
        finally:
            # 연결 종료 시 남은 텍스트를 final로 전송
            await self._flush_buffers()

    async def _process_response(self, data: dict):
        """Soniox 응답 처리"""
        # 토큰 처리
        if "tokens" in data:
            tokens = data["tokens"]
            for token in tokens:
                text = token.get("text", "")
                is_final = token.get("is_final", False)
                translation_status = token.get("translation_status", "none")
                language = token.get("language", "")
                speaker = token.get("speaker")

                # 화자 전환 감지: 버퍼에 이전 화자의 발화가 남아 있으면
                # 먼저 final로 내보내고 새 화자의 문장을 시작한다
                if (
                    speaker is not None
                    and self._current_speaker is not None
                    and speaker != self._current_speaker
                    and (self._confirmed_text or self._pending_text)
                ):
                    logger.info(
                        f"[Soniox] Speaker change {self._current_speaker} -> {speaker}, flushing"
                    )
                    await self._flush_buffers()
                if speaker is not None:
                    self._current_speaker = speaker

                # 원본 텍스트 (translation_status가 "original"인 경우)
                if translation_status == "original":
                    if text:
                        if is_final:
                            # 확정된 텍스트: confirmed에 누적, pending 초기화
                            self._confirmed_text += text
                            self._pending_text = ""
                        else:
                            # 임시 텍스트: pending에 대체 (이전 임시 결과를 덮어씀)
                            self._pending_text = text

                        # 전체 텍스트 = 확정 + 임시
                        full_text = self._confirmed_text + self._pending_text
                        if self.on_transcript:
                            await self.on_transcript(full_text, False, None, self._current_speaker)
                        logger.debug(f"[Soniox] Original: '{text}' (final={is_final}) -> full: '{full_text}'")

                # 번역 텍스트 (translation_status가 "translation"인 경우)
                elif translation_status == "translation":
                    if text:
                        if is_final:
                            # 확정된 번역: confirmed에 누적, pending 초기화
                            self._confirmed_translation += text
                            self._pending_translation = ""
                        else:
                            # 임시 번역: pending에 대체 (이전 임시 결과를 덮어씀)
                            self._pending_translation = text

                        # 전체 번역 = 확정 + 임시
                        full_translation = self._confirmed_translation + self._pending_translation
                        if self.on_transcript:
                            await self.on_transcript("", False, full_translation, self._current_speaker)
                        logger.debug(f"[Soniox] Translation: '{text}' (final={is_final}) -> full: '{full_translation}'")

        # 세그먼트 완료
        if data.get("segment_end"):
            # 전체 텍스트 = 확정 + 임시
            full_text = self._confirmed_text + self._pending_text
            full_translation = self._confirmed_translation + self._pending_translation
            logger.info(f"[Soniox] Segment end - text: '{full_text}', translation: '{full_translation}'")
            # 세그먼트 완료 시 최종 결과 전송
            if self.on_transcript and (full_text or full_translation):
                await self.on_transcript(
                    full_text,
                    True,
                    full_translation,
                    self._current_speaker
                )
            # 버퍼 초기화
            self._confirmed_text = ""
            self._confirmed_translation = ""
            self._pending_text = ""
            self._pending_translation = ""

        # 에러 처리
        if "error" in data:
            error_msg = data["error"]
            logger.error(f"[Soniox] Error: {error_msg}")
            if self.on_error:
                await self.on_error(error_msg)

    @property
    def is_connected(self) -> bool:
        return self._is_connected


class SonioxSessionManager:
    """Soniox 세션 관리자"""

    def __init__(self):
        # room_id -> user_id -> SonioxSession
        self._sessions: dict[str, dict[str, SonioxSession]] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        room_id: str,
        user_id: str,
        translation_mode: TranslationMode,
        on_transcript: Optional[Callable[[str, bool, Optional[str]], Awaitable[None]]] = None,
        on_error: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> SonioxSession:
        """새 Soniox 세션 생성"""
        async with self._lock:
            if room_id not in self._sessions:
                self._sessions[room_id] = {}

            session = SonioxSession(
                user_id=user_id,
                translation_mode=translation_mode,
                on_transcript=on_transcript,
                on_error=on_error,
            )
            self._sessions[room_id][user_id] = session
            await session.connect()
            return session

    async def get_session(self, room_id: str, user_id: str) -> Optional[SonioxSession]:
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
soniox_session_manager = SonioxSessionManager()
