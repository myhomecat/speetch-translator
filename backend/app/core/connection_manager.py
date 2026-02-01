from typing import Optional
from fastapi import WebSocket
import asyncio
import json
from ..models.messages import BaseMessage


class ConnectionManager:
    def __init__(self):
        # room_id -> user_id -> WebSocket
        self._connections: dict[str, dict[str, WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        room_id: str,
        user_id: str
    ):
        await websocket.accept()
        async with self._lock:
            if room_id not in self._connections:
                self._connections[room_id] = {}
            self._connections[room_id][user_id] = websocket

    async def disconnect(self, room_id: str, user_id: str):
        async with self._lock:
            if room_id in self._connections:
                self._connections[room_id].pop(user_id, None)
                if not self._connections[room_id]:
                    del self._connections[room_id]

    async def get_connection(
        self,
        room_id: str,
        user_id: str
    ) -> Optional[WebSocket]:
        if room_id in self._connections:
            return self._connections[room_id].get(user_id)
        return None

    async def send_json(
        self,
        websocket: WebSocket,
        message: BaseMessage | dict
    ):
        if isinstance(message, BaseMessage):
            data = message.model_dump()
        else:
            data = message
        await websocket.send_json(data)

    async def send_bytes(self, websocket: WebSocket, data: bytes):
        await websocket.send_bytes(data)

    async def broadcast_json(
        self,
        room_id: str,
        message: BaseMessage | dict,
        exclude_user_id: Optional[str] = None
    ):
        if room_id not in self._connections:
            return

        if isinstance(message, BaseMessage):
            data = message.model_dump()
        else:
            data = message

        tasks = []
        for user_id, ws in self._connections[room_id].items():
            if user_id != exclude_user_id:
                tasks.append(ws.send_json(data))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_bytes(
        self,
        room_id: str,
        data: bytes,
        exclude_user_id: Optional[str] = None
    ):
        if room_id not in self._connections:
            return

        tasks = []
        for user_id, ws in self._connections[room_id].items():
            if user_id != exclude_user_id:
                tasks.append(ws.send_bytes(data))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def send_to_user(
        self,
        room_id: str,
        user_id: str,
        message: BaseMessage | dict
    ) -> bool:
        ws = await self.get_connection(room_id, user_id)
        if ws:
            await self.send_json(ws, message)
            return True
        return False

    async def send_bytes_to_user(
        self,
        room_id: str,
        user_id: str,
        data: bytes
    ) -> bool:
        ws = await self.get_connection(room_id, user_id)
        if ws:
            await self.send_bytes(ws, data)
            return True
        return False

    def get_room_connections(self, room_id: str) -> dict[str, WebSocket]:
        return self._connections.get(room_id, {})

    def get_room_user_count(self, room_id: str) -> int:
        return len(self._connections.get(room_id, {}))


# Singleton instance
connection_manager = ConnectionManager()
