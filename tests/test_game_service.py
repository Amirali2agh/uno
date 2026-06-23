import pytest
from app.redis_client import get_redis
from app.services.game_service import GameService, Card
from app.utils.redis_keys import get_game_state_key

@pytest.mark.asyncio
async def test_game_initialization():
    redis = await get_redis()
    game_service = GameService(redis)
    game_state = await game_service.create_game("game-1", ["p1", "p2"])
    assert game_state.game_id == "game-1"
    assert len(game_state.players[0].hand) == 7

@pytest.mark.asyncio
async def test_draw_card_logic():
    redis = await get_redis()
    game_service = GameService(redis)
    game_id = "game-draw-test"
    state = await game_service.create_game(game_id, ["p1", "p2"])
    success = await game_service.draw_card(game_id, "p1")
    assert success is True

@pytest.mark.asyncio
async def test_play_card_logic():
    redis = await get_redis()
    game_service = GameService(redis)
    game_id = "game-play-test"
    state = await game_service.create_game(game_id, ["p1", "p2"])
    state.discard_pile = [Card(color="red", value="5")]
    state.active_color = "red"
    state.players[0].hand = [Card(color="red", value="skip")]
    await game_service.save_game_state(state)
    success = await game_service.play_card(game_id, "p1", 0)
    assert success is True
