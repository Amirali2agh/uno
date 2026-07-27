import pytest
from app.redis_client import get_redis
from app.services.game_service import GameService, Card
from app.utils.redis_keys import get_game_state_key

@pytest.mark.asyncio
async def test_game_initialization():
    redis = await get_redis()
    game_service = GameService(redis)
    game_state = await game_service.create_game("game-1", [{"player_id": "p1"}, {"player_id": "p2"}])
    assert game_state.game_id == "game-1"
    assert len(game_state.players[0].hand) == 7
    assert game_state.players[0].player_name == ""
    assert game_state.players[0].player_avatar == ""

@pytest.mark.asyncio
async def test_draw_card_logic():
    redis = await get_redis()
    game_service = GameService(redis)
    game_id = "game-draw-test"
    state = await game_service.create_game(game_id, [{"player_id": "p1"}, {"player_id": "p2"}])
    success = await game_service.draw_card(game_id, "p1")
    assert success is True

@pytest.mark.asyncio
async def test_play_card_logic():
    redis = await get_redis()
    game_service = GameService(redis)
    game_id = "game-play-test"
    state = await game_service.create_game(game_id, [{"player_id": "p1"}, {"player_id": "p2"}])
    state.discard_pile = [Card(color="red", value="5")]
    state.active_color = "red"
    state.players[0].hand = [Card(color="red", value="skip")]
    await game_service.save_game_state(state)
    success = await game_service.play_card(game_id, "p1", 0)
    assert success is True

@pytest.mark.asyncio
async def test_create_game_with_names():
    """Test that player_name and player_avatar are stored correctly."""
    redis = await get_redis()
    game_service = GameService(redis)
    players = [
        {"player_id": "p1", "player_name": "Ali", "player_avatar": "/avatars/1.jpg"},
        {"player_id": "p2", "player_name": "Reza", "player_avatar": ""},
    ]
    game_state = await game_service.create_game("game-names", players)
    assert game_state.players[0].player_name == "Ali"
    assert game_state.players[0].player_avatar == "/avatars/1.jpg"
    assert game_state.players[1].player_name == "Reza"
    assert game_state.players[1].player_avatar == ""
