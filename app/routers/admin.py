from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from app.redis_client import get_redis
from app.managers.queue_manager import queue_manager
from app.managers.room_manager import room_manager
from app.utils.redis_keys import get_queue_key

# Create a router for admin endpoints
router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/stats")
async def get_server_stats(redis: Redis = Depends(get_redis)):
    """
    Returns real-time statistics about the game server.
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
            "active_ws_connections": active_queue_connections
        },
        "game_rooms": {
            "active_rooms": active_rooms,
            "total_players_in_game": players_in_rooms
        }
    }
