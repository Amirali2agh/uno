import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from redis.asyncio import Redis

from app.redis_client import get_redis
from app.managers.queue_manager import queue_manager
from app.services.queue_service import QueueService
from app.services.game_service import GameService

router = APIRouter()

@router.websocket("/ws/queue/{player_count}")
async def queue_endpoint(websocket: WebSocket, player_count: int, player_id: str, redis: Redis = Depends(get_redis)):
    if player_count not in [2, 4]:
        await websocket.close(code=1003, reason="Invalid player count")
        return

    queue_service = QueueService(redis)
    game_service = GameService(redis)

    await queue_manager.connect(player_id, websocket)

    try:
        await queue_service.join_queue(player_id, player_count)
        matched_players = await queue_service.try_match(player_count)

        if matched_players:
            game_id = str(uuid.uuid4())
            await game_service.create_game(game_id, matched_players)

            for pid in matched_players:
                await queue_manager.send_match_found(pid, game_id)
                queue_manager.disconnect(pid)

        while True:
            data = await websocket.receive_text()
            if data == "cancel":
                break

    except WebSocketDisconnect:
        pass
    finally:
        await queue_service.leave_queue(player_id, player_count)
        queue_manager.disconnect(player_id)
