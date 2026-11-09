from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from redis.asyncio import Redis

from app.config import settings
from app.managers.queue_manager import queue_manager
from app.managers.room_manager import room_manager
from app.redis_client import get_redis
from app.utils.redis_keys import get_queue_key

# Create a router for admin endpoints
router = APIRouter(prefix="/admin", tags=["Admin"])


async def require_admin_token(
    x_admin_token: Annotated[Optional[str], Header(alias="X-Admin-Token")] = None,
) -> None:
    """Guard the admin surface with the shared secret from settings.

    With no ``ADMIN_TOKEN`` configured the endpoints are disabled (503) instead of
    being open to the internet.
    """
    if not settings.ADMIN_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API is disabled: set ADMIN_TOKEN to enable it.",
        )
    if x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token.",
        )


@router.get("/stats", dependencies=[Depends(require_admin_token)])
async def get_server_stats(redis: Redis = Depends(get_redis)):
    """
    Returns real-time statistics about the game server.

    Queue lengths come from Redis and are therefore global; connection and room
    counters live in this process only.
    """
    # 1. Get matchmaking queue lengths from Redis
    q2_length = await redis.llen(get_queue_key(2))
    q4_length = await redis.llen(get_queue_key(4))

    # 2. Get active WebSocket connections from memory managers
    active_queue_connections = len(queue_manager.active_connections)
    active_rooms = len(room_manager.rooms)

    # Calculate total players currently in active game rooms
    players_in_rooms = sum(len(room_players) for room_players in room_manager.rooms.values())

    return {
        "status": "healthy",
        "matchmaking": {
            "queue_2p_length": q2_length,
            "queue_4p_length": q4_length,
            "active_ws_connections": active_queue_connections,
        },
        "game_rooms": {
            "active_rooms": active_rooms,
            "total_players_in_game": players_in_rooms,
        },
        # Values above are per process unless stated otherwise.
        "scope": {
            "queue_2p_length": "global",
            "queue_4p_length": "global",
            "active_ws_connections": f"process:{queue_manager.process_id}",
            "active_rooms": f"process:{room_manager.process_id}",
            "total_players_in_game": f"process:{room_manager.process_id}",
        },
    }
