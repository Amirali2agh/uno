import pytest
import pytest_asyncio
from app.redis_client import redis_client, get_redis
from app.services.game_service import GameService
from app.utils.redis_keys import get_game_state_key

@pytest_asyncio.fixture(autouse=True)
async def cleanup_redis():
    """Reset Redis connections to prevent Event Loop issues."""
    await redis_client.aclose()
    yield
    await redis_client.aclose()

@pytest.mark.asyncio
async def test_game_initialization():
    """
    Test if a game is correctly created, cards are dealt properly (7 per player),
    and the state is saved to Redis.
    """
    redis = await get_redis()
    game_service = GameService(redis)
    
    game_id = "test-game-123"
    player_ids = ["player_1", "player_2"]
    
    # 1. Create a new game
    game_state = await game_service.create_game(game_id, player_ids)
    
    # Assertions for game logic
    assert game_state.game_id == game_id
    assert len(game_state.players) == 2
    assert game_state.players[0].player_id == "player_1"
    
    # Each player must start with exactly 7 cards
    assert len(game_state.players[0].hand) == 7
    assert len(game_state.players[1].hand) == 7
    
    # The discard pile must have exactly 1 card to start
    assert len(game_state.discard_pile) == 1
    # First card cannot be wild
    assert game_state.discard_pile[0].color != 'black'
    
    # A standard deck is 108 cards. 14 dealt + 1 discarded = 93 left in draw pile
    assert len(game_state.draw_pile) == 93

@pytest.mark.asyncio
async def test_game_state_persistence():
    """
    Test if the game state can be retrieved from Redis perfectly intact.
    """
    redis = await get_redis()
    game_service = GameService(redis)
    
    game_id = "test-persist-456"
    
    # Create and save game
    await game_service.create_game(game_id, ["pA", "pB", "pC", "pD"])
    
    # Retrieve game from Redis using a fresh request
    retrieved_state = await game_service.get_game_state(game_id)
    
    assert retrieved_state is not None
    assert retrieved_state.game_id == game_id
    assert len(retrieved_state.players) == 4
    
    # Cleanup
    await redis.delete(get_game_state_key(game_id))