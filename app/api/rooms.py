import json
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.redis_client import redis_client

router = APIRouter(prefix="/api")

ROOM_META_PREFIX = "uno:room"


class CreateRoomRequest(BaseModel):
    room_id: str = ""
    player1_id: str = ""
    player1_name: str = ""
    player1_avatar: str = ""
    player2_id: str = ""
    player2_name: str = ""
    player2_avatar: str = ""


class RoomJoinResponse(BaseModel):
    room_id: str
    player1_id: str
    player1_name: str
    player1_avatar: str
    player2_id: str
    player2_name: str
    player2_avatar: str
    status: str


def _room_meta_key(room_id: str) -> str:
    return f"{ROOM_META_PREFIX}:{room_id}:meta"


@router.post("/rooms", response_model=RoomJoinResponse)
async def create_room(req: CreateRoomRequest):
    room_id = req.room_id or str(uuid.uuid4())[:8]
    room_data = {
        "room_id": room_id,
        "players": [req.player1_id, req.player2_id] if req.player2_id else [req.player1_id],
        "players_meta": {
            "1": {"id": req.player1_id, "name": req.player1_name, "avatar": req.player1_avatar},
            "2": {"id": req.player2_id, "name": req.player2_name, "avatar": req.player2_avatar},
        },
        "status": "playing" if req.player2_id else "waiting",
    }
    await redis_client.set(_room_meta_key(room_id), json.dumps(room_data))
    return RoomJoinResponse(
        room_id=room_id,
        player1_id=req.player1_id,
        player1_name=req.player1_name or "بازیکن ۱",
        player1_avatar=req.player1_avatar,
        player2_id=req.player2_id,
        player2_name=req.player2_name or "",
        player2_avatar=req.player2_avatar,
        status=room_data["status"],
    )


@router.get("/rooms/{room_id}", response_model=RoomJoinResponse)
async def get_room(room_id: str):
    data = await redis_client.get(_room_meta_key(room_id))
    if not data:
        raise HTTPException(status_code=404, detail="Room not found")
    room = json.loads(data)
    meta = room.get("players_meta", {})
    p1 = meta.get("1", {})
    p2 = meta.get("2", {})
    return RoomJoinResponse(
        room_id=room_id,
        player1_id=p1.get("id", ""),
        player1_name=p1.get("name", "بازیکن ۱"),
        player1_avatar=p1.get("avatar", ""),
        player2_id=p2.get("id", ""),
        player2_name=p2.get("name", ""),
        player2_avatar=p2.get("avatar", ""),
        status=room.get("status", "waiting"),
    )


@router.post("/rooms/{room_id}/join")
async def join_room(room_id: str, player_id: str, player_name: str = "", player_avatar: str = ""):
    data = await redis_client.get(_room_meta_key(room_id))
    if not data:
        raise HTTPException(status_code=404, detail="Room not found")
    room = json.loads(data)
    meta = room.get("players_meta", {})
    for num, mp in meta.items():
        if mp.get("id") == player_id:
            return {"room_id": room_id, "player_num": int(num), "status": room.get("status")}
    p2 = meta.get("2", {})
    if not p2.get("id"):
        meta["2"] = {"id": player_id, "name": player_name, "avatar": player_avatar}
        room["players"] = [meta["1"]["id"], player_id]
        room["status"] = "playing"
        await redis_client.set(_room_meta_key(room_id), json.dumps(room))
        return {"room_id": room_id, "player_num": 2, "status": "playing"}
    raise HTTPException(status_code=400, detail="Room is full")
