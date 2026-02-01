from typing import Optional
import asyncio
from datetime import datetime, timedelta
from ..models.room import Room, User, TranslationMode
from ..config import get_settings


class RoomManager:
    def __init__(self):
        self._rooms: dict[str, Room] = {}
        self._lock = asyncio.Lock()
        self._settings = get_settings()

    async def create_room(self, room_id: str) -> Room:
        async with self._lock:
            if room_id not in self._rooms:
                self._rooms[room_id] = Room(
                    id=room_id,
                    max_users=self._settings.max_users_per_room
                )
            return self._rooms[room_id]

    async def get_room(self, room_id: str) -> Optional[Room]:
        return self._rooms.get(room_id)

    async def get_or_create_room(self, room_id: str) -> Room:
        room = await self.get_room(room_id)
        if room is None:
            room = await self.create_room(room_id)
        return room

    async def delete_room(self, room_id: str) -> bool:
        async with self._lock:
            if room_id in self._rooms:
                del self._rooms[room_id]
                return True
            return False

    async def add_user_to_room(
        self,
        room_id: str,
        user_name: str,
        translation_mode: TranslationMode = TranslationMode.AUTO
    ) -> tuple[Optional[Room], Optional[User], Optional[str]]:
        """
        Add a user to a room.
        Returns: (room, user, error_message)
        """
        room = await self.get_or_create_room(room_id)

        async with self._lock:
            if room.is_full:
                return None, None, "Room is full"

            user = User(
                name=user_name,
                translation_mode=translation_mode
            )

            if room.add_user(user):
                return room, user, None
            return None, None, "Failed to add user to room"

    async def remove_user_from_room(
        self,
        room_id: str,
        user_id: str
    ) -> tuple[Optional[Room], Optional[User]]:
        """
        Remove a user from a room.
        Returns: (room, removed_user)
        """
        room = await self.get_room(room_id)
        if room is None:
            return None, None

        async with self._lock:
            user = room.remove_user(user_id)

            # Delete room if empty
            if room.user_count == 0:
                del self._rooms[room_id]
                return None, user

            return room, user

    async def update_user_mode(
        self,
        room_id: str,
        user_id: str,
        mode: TranslationMode
    ) -> Optional[User]:
        room = await self.get_room(room_id)
        if room is None:
            return None

        user = room.get_user(user_id)
        if user:
            user.translation_mode = mode
        return user

    async def get_all_rooms(self) -> list[Room]:
        return list(self._rooms.values())

    async def cleanup_empty_rooms(self):
        async with self._lock:
            empty_rooms = [
                room_id for room_id, room in self._rooms.items()
                if room.user_count == 0
            ]
            for room_id in empty_rooms:
                del self._rooms[room_id]


# Singleton instance
room_manager = RoomManager()
