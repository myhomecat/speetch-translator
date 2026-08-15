from pydantic import BaseModel
from typing import Optional, Literal
from enum import Enum


class MessageType(str, Enum):
    JOIN = "join"
    LEAVE = "leave"
    AUDIO_DATA = "audio_data"
    TRANSCRIPT = "transcript"
    REALTIME_TRANSCRIPT = "realtime_transcript"  # 실시간 자막 (말하는 중)
    ERROR = "error"
    ROOM_INFO = "room_info"
    MODE_CHANGE = "mode_change"
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"


class BaseMessage(BaseModel):
    type: MessageType


class JoinMessage(BaseMessage):
    type: Literal[MessageType.JOIN] = MessageType.JOIN
    user_name: str
    translation_mode: str = "auto"


class LeaveMessage(BaseMessage):
    type: Literal[MessageType.LEAVE] = MessageType.LEAVE


class ModeChangeMessage(BaseMessage):
    type: Literal[MessageType.MODE_CHANGE] = MessageType.MODE_CHANGE
    translation_mode: str


class AudioDataMessage(BaseMessage):
    type: Literal[MessageType.AUDIO_DATA] = MessageType.AUDIO_DATA
    user_id: str
    user_name: str


class TranscriptMessage(BaseMessage):
    type: Literal[MessageType.TRANSCRIPT] = MessageType.TRANSCRIPT
    user_id: str
    user_name: str
    original_text: str
    original_language: str
    translated_text: Optional[str] = None
    translated_language: Optional[str] = None
    speaker: Optional[int] = None  # 화자 번호 (diarization, 솔로 모드)


class ErrorMessage(BaseMessage):
    type: Literal[MessageType.ERROR] = MessageType.ERROR
    message: str
    code: Optional[str] = None


class UserInfo(BaseModel):
    id: str
    name: str
    translation_mode: str


class RoomInfoMessage(BaseMessage):
    type: Literal[MessageType.ROOM_INFO] = MessageType.ROOM_INFO
    room_id: str
    user_id: str
    users: list[UserInfo]


class UserJoinedMessage(BaseMessage):
    type: Literal[MessageType.USER_JOINED] = MessageType.USER_JOINED
    user: UserInfo


class UserLeftMessage(BaseMessage):
    type: Literal[MessageType.USER_LEFT] = MessageType.USER_LEFT
    user_id: str
    user_name: str


class RealtimeTranscriptMessage(BaseMessage):
    """실시간 자막 메시지 (말하는 중에 표시)"""
    type: Literal[MessageType.REALTIME_TRANSCRIPT] = MessageType.REALTIME_TRANSCRIPT
    user_id: str
    user_name: str
    text: str
    is_final: bool  # True면 문장 완료, False면 말하는 중
    translated_text: Optional[str] = None  # final일 때만 번역 포함
    source_language: Optional[str] = None  # 감지된 원본 언어
    target_language: Optional[str] = None  # 번역 대상 언어
    speaker: Optional[int] = None  # 화자 번호 (diarization, 솔로 모드)
