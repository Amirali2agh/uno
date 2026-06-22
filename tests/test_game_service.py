import pytest
import pytest_asyncio
from app.redis_client import redis_client, get_redis
from app.services.game_service import GameService, Card
from app.utils.redis_keys import get_game_state_key

@pytest_asyncio.fixture(autouse=True)
async def cleanup_redis():
    """Reset Redis connections to prevent Event Loop issues."""
    await redis_client.aclose()
    yield
    await redis_client.aclose()

@pytest.mark.asyncio
async def test_game_initialization():
    redis = await get_redis()
    game_service = GameService(redis)
    game_state = await game_service.create_game("game-1", ["p1", "p2"])
    
    assert game_state.game_id == "game-1"
    assert len(game_state.players[0].hand) == 7
    assert game_state.active_color != ""
    assert game_state.active_color != "black"

@pytest.mark.asyncio
async def test_draw_card_logic():
    """Test if drawing a card works and changes the turn."""
    redis = await get_redis()
    game_service = GameService(redis)
    game_id = "game-draw-test"
    
    state = await game_service.create_game(game_id, ["p1", "p2"])
    assert state.current_turn_index == 0
    
    # p2 tries to draw out of turn (should fail)
    success = await game_service.draw_card(game_id, "p2")
    assert success is False
    
    # p1 draws a card (should succeed)
    success = await game_service.draw_card(game_id, "p1")
    assert success is True
    
    # Verify state updated in Redis
    updated_state = await game_service.get_game_state(game_id)
    assert len(updated_state.players[0].hand) == 8 # Hand increased
    assert updated_state.current_turn_index == 1   # Turn moved to p2

@pytest.mark.asyncio
async def test_play_card_logic():
    """Test playing a valid card and applying rules."""
    redis = await get_redis()
    game_service = GameService(redis)
    game_id = "game-play-test"
    
    state = await game_service.create_game(game_id, ["p1", "p2"])
    
    # Force the top card and player's hand for predictable testing
    state.discard_pile = [Card(color="red", value="5")]
    state.active_color = "red"
    state.players[0].hand = [
        Card(color="blue", value="9"), # Invalid
        Card(color="red", value="skip") # Valid (matches color)
    ]
    await game_service.save_game_state(state)
    
    # 1. Try playing invalid card (index 0: blue 9 on red 5)
    success = await game_service.play_card(game_id, "p1", 0)
    assert success is False
    
    # 2. Try playing valid card (index 1: red skip on red 5)
    success = await game_service.play_card(game_id, "p1", 1)
    assert success is True
    
    # 3. Verify effects
    updated_state = await game_service.get_game_state(game_id)
    assert len(updated_state.players[0].hand) == 1
    assert updated_state.discard_pile[-1].value == "skip"
    
    # Since it's a skip in a 2-player game, turn should return to p1 (index 0)
    assert updated_state.current_turn_index == 0