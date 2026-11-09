import pytest

from app.services.game_service import Card, GameState


async def prepare_state(game_service, game_id, hand, top_card, active_color=None):
    """Persist a deterministic game state with a single player holding `hand`."""
    state = await game_service.create_game(
        game_id, [{"player_id": "p1"}, {"player_id": "p2"}]
    )
    state.discard_pile = [top_card]
    state.active_color = active_color or top_card.color
    state.players[0].hand = list(hand)
    await game_service.save_game_state(state)
    return state


@pytest.mark.asyncio
async def test_wild4_rejected_while_holding_active_color(game_service):
    """Wild Draw Four is illegal when the player holds a card of the active colour."""
    game_id = "rules-wild4-illegal"
    await prepare_state(
        game_service,
        game_id,
        hand=[Card(color="red", value="9"), Card(color="black", value="wild4")],
        top_card=Card(color="red", value="5"),
    )

    played = await game_service.play_card(game_id, "p1", 1, "blue")

    assert played is False
    state = await game_service.get_game_state(game_id)
    assert len(state.players[0].hand) == 2
    assert state.discard_pile[-1].value == "5"
    assert state.active_color == "red"


@pytest.mark.asyncio
async def test_wild4_allowed_without_active_color(game_service):
    """Without a card of the active colour the Wild Draw Four is legal."""
    game_id = "rules-wild4-legal"
    await prepare_state(
        game_service,
        game_id,
        hand=[Card(color="blue", value="9"), Card(color="black", value="wild4")],
        top_card=Card(color="red", value="5"),
    )

    played = await game_service.play_card(game_id, "p1", 1, "green")

    assert played is True
    state = await game_service.get_game_state(game_id)
    assert state.active_color == "green"
    assert len(state.players[1].hand) == 11  # 7 dealt + 4 penalty


@pytest.mark.asyncio
async def test_wild_is_always_legal(game_service):
    """A plain Wild card has no colour restriction."""
    game_id = "rules-wild-legal"
    await prepare_state(
        game_service,
        game_id,
        hand=[Card(color="red", value="9"), Card(color="black", value="wild")],
        top_card=Card(color="red", value="5"),
    )

    assert await game_service.play_card(game_id, "p1", 1, "yellow") is True

    state = await game_service.get_game_state(game_id)
    assert state.active_color == "yellow"
