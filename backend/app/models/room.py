from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime
import uuid


class TranslationMode(str, Enum):
    AUTO = "auto"
    KO_TO_JA = "ko_to_ja"
    JA_TO_KO = "ja_to_ko"


class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    translation_mode: TranslationMode = TranslationMode.AUTO
    joined_at: datetime = Field(default_factory=datetime.now)
    is_speaking: bool = False


class Room(BaseModel):
    id: str
    users: dict[str, User] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    max_users: int = 3

    @property
    def user_count(self) -> int:
        return len(self.users)

    @property
    def is_full(self) -> bool:
        return self.user_count >= self.max_users

    def add_user(self, user: User) -> bool:
        if self.is_full:
            return False
        self.users[user.id] = user
        return True

    def remove_user(self, user_id: str) -> Optional[User]:
        return self.users.pop(user_id, None)

    def get_user(self, user_id: str) -> Optional[User]:
        return self.users.get(user_id)

    def get_other_users(self, exclude_user_id: str) -> list[User]:
        return [u for uid, u in self.users.items() if uid != exclude_user_id]
