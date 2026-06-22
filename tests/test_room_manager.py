import pytest
import pytest_asyncio
import asyncio
from app.redis_client import redis_client, get_redis
from app.managers.room_manager import RoomManager
from app.services.game_service import GameService
from app.utils.redis_keys import get_game_state_key

class MockWebSocket:
    def __init__(self):
        self.is_accepted = False
        self.sent_messages = []

    async def accept(self):
        self.is_accepted = True

    async def send_json(self, data: dict):
        self.sent_messages.append(data)

@pytest_asyncio.fixture(autouse=True)
async def cleanup_redis():
    """Reset Redis connections to prevent loop errors."""
    await redis_client.aclose()
    yield
    await redis_client.aclose()

@pytest.mark.asyncio
async def test_room_broadcast():
    redis = await get_redis()
    manager = RoomManager(timeout_seconds=1)
    
    ws1 = MockWebSocket()
    ws2 = MockWebSocket()
    
    await manager.connect("game-1", "p1", ws1, redis)
    await manager.connect("game-1", "p2", ws2, redis)
    
    await manager.broadcast("game-1", {"type": "test_msg"})
    
    assert len(ws1.sent_messages) == 1
    assert len(ws2.sent_messages) == 1

@pytest.mark.asyncio
async def test_disconnect_timeout():
    """Test that a player disconnect triggers game-over after 1s timeout."""
    redis = await get_redis()
    game_service = GameService(redis)
    
    # Create room manager with 1s timeout
    manager = RoomManager(timeout_seconds=1)
    
    game_id = "timeout-game-id"
    await game_service.create_game(game_id, ["p1", "p2"])
    
    ws1 = MockWebSocket()
    ws2 = MockWebSocket()
    await manager.connect(game_id, "p1", ws1, redis)
    await manager.connect(game_id, "p2", ws2, redis)
    
    # Disconnect p1
    await manager.disconnect(game_id, "p1", redis)
    
    # Wait for slightly more than 1 second (e.g., 1.2s)
    await asyncio.sleep(1.2)
    
    # Verify that the game status is now finished
    state = await game_service.get_game_state(game_id)
    assert state.status == "finished"
    assert "p1 disconnected" in state.winner
    
    await redis.delete(get_game_state_key(game_id))