import pytest

from app.services.game_service import Card


@pytest.mark.asyncio
async def test_game_initialization(start_game):
    game_state = await start_game("game-1", [{"player_id": "p1"}, {"player_id": "p2"}])

    assert game_state.game_id == "game-1"
    assert len(game_state.players[0].hand) == 7
    assert game_state.players[0].player_name == ""
    assert game_state.players[0].player_avatar == ""


@pytest.mark.asyncio
async def test_draw_card_logic(game_service, start_game):
    game_id = "game-draw-test"
    await start_game(game_id, [{"player_id": "p1"}, {"player_id": "p2"}])

    success = await game_service.draw_card(game_id, "p1")

    assert success.ok is True


@pytest.mark.asyncio
async def test_play_card_logic(game_service, start_game):
    game_id = "game-play-test"
    state = await start_game(game_id, [{"player_id": "p1"}, {"player_id": "p2"}])
    state.discard_pile = [Card(color="red", value="5")]
    state.active_color = "red"
    state.players[0].hand = [Card(color="red", value="skip")]
    await game_service.save_game_state(state)

    success = await game_service.play_card(game_id, "p1", 0)

    assert success.ok is True


@pytest.mark.asyncio
async def test_create_game_with_names(game_service):
    """Player name and avatar are carried into the game state."""
    players = [
        {"player_id": "p1", "player_name": "Ali", "player_avatar": "/avatars/1.jpg"},
        {"player_id": "p2", "player_name": "Reza", "player_avatar": ""},
    ]

    game_state = await game_service.create_game("game-names", players)

    assert game_state.players[0].player_name == "Ali"
    assert game_state.players[0].player_avatar == "/avatars/1.jpg"
    assert game_state.players[1].player_name == "Reza"
    assert game_state.players[1].player_avatar == ""


@pytest.mark.asyncio
async def test_game_state_expires(redis, game_service, start_game):
    """State is written with a TTL so abandoned games cannot leak forever."""
    from app.services.game_service import GAME_ACTIVE_TTL_SECONDS, GAME_FINISHED_TTL_SECONDS
    from app.utils.redis_keys import get_game_state_key

    key = get_game_state_key("ttl-active")
    await start_game("ttl-active", [{"player_id": "p1"}, {"player_id": "p2"}])

    ttl_active = await redis.ttl(key)
    assert 0 < ttl_active <= GAME_ACTIVE_TTL_SECONDS

    state = await game_service.get_game_state("ttl-active")
    state.status = "finished"
    state.winner = "p1"
    await game_service.save_game_state(state)

    ttl_finished = await redis.ttl(key)
    assert 0 < ttl_finished <= GAME_FINISHED_TTL_SECONDS
    assert ttl_finished < ttl_active
