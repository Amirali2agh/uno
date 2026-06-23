import pytest
import asyncio
import redis.asyncio as redis_async
from fastapi.testclient import TestClient
from app.main import app
from app.services.game_service import GameService
from app.utils.redis_keys import get_game_state_key
from app.config import settings

def test_room_websocket_flow():
    """
    Test the complete WebSocket flow inside a game room.
    Uses isolated Redis clients for setup/teardown to prevent Event Loop crashes.
    """
    game_id = "ws-room-test-123"
    player_ids = ["p1", "p2"]
    
    # 1. Setup: Use a completely independent Redis client
    async def setup():
        r = redis_async.from_url(settings.REDIS_URL, decode_responses=True)
        game_service = GameService(r)
        await game_service.create_game(game_id, player_ids)
        await r.aclose() # Close the temporary client
        
    asyncio.run(setup())

    # 2. Run TestClient inside a 'with' block to trigger FastAPI lifespan (startup/shutdown)
    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/room/{game_id}?player_id=p1") as ws:
            # First message: Player connected status
            msg_status = ws.receive_json()
            assert msg_status["type"] == "player_status"
            assert msg_status["player_id"] == "p1"
            
            # Second message: Initial game state
            msg_state = ws.receive_json()
            assert msg_state["type"] == "state_update"
            assert msg_state["state"]["game_id"] == game_id
            
            # Action: Draw a card
            ws.send_json({"action": "draw_card"})
            
            # Response: Updated game state
            msg_after_draw = ws.receive_json()
            assert msg_after_draw["type"] == "state_update"
            # Turn should have successfully moved to p2 (index 1)
            assert msg_after_draw["state"]["current_turn_index"] == 1

    # 3. Teardown: Use another independent Redis client
    async def teardown():
        r = redis_async.from_url(settings.REDIS_URL, decode_responses=True)
        await r.delete(get_game_state_key(game_id))
        await r.aclose() # Close the temporary client
        
    asyncio.run(teardown())
