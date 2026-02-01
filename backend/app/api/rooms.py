from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid

from ..core.room_manager import room_manager
from ..models.messages import UserInfo

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


class CreateRoomResponse(BaseModel):
    room_id: str
    url: str


class RoomInfoResponse(BaseModel):
    room_id: str
    user_count: int
    max_users: int
    is_full: bool
    users: list[UserInfo]


@router.post("/create", response_model=CreateRoomResponse)
async def create_room(room_id: Optional[str] = None):
    """Create a new room or get existing room"""
    if room_id is None:
        room_id = str(uuid.uuid4())[:8]

    room = await room_manager.get_or_create_room(room_id)

    return CreateRoomResponse(
        room_id=room.id,
        url=f"/room/{room.id}"
    )


@router.get("/{room_id}", response_model=RoomInfoResponse)
async def get_room_info(room_id: str):
    """Get room information"""
    room = await room_manager.get_room(room_id)

    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    users = [
        UserInfo(id=u.id, name=u.name, translation_mode=u.translation_mode.value)
        for u in room.users.values()
    ]

    return RoomInfoResponse(
        room_id=room.id,
        user_count=room.user_count,
        max_users=room.max_users,
        is_full=room.is_full,
        users=users
    )


@router.get("/{room_id}/exists")
async def check_room_exists(room_id: str):
    """Check if room exists and has available slots"""
    room = await room_manager.get_room(room_id)

    if room is None:
        return {"exists": False, "available": True}

    return {
        "exists": True,
        "available": not room.is_full,
        "user_count": room.user_count,
        "max_users": room.max_users
    }
