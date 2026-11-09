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


@pytest.mark.asyncio
async def test_draw2_as_last_card_still_penalises_next_player(game_service):
    """Going out with a Draw Two still forces the next player to draw two."""
    game_id = "rules-last-draw2"
    await prepare_state(
        game_service,
        game_id,
        hand=[Card(color="red", value="draw2")],
        top_card=Card(color="red", value="5"),
    )

    assert await game_service.play_card(game_id, "p1", 0) is True

    state = await game_service.get_game_state(game_id)
    assert state.status == "finished"
    assert state.winner == "p1"
    assert len(state.players[1].hand) == 9


@pytest.mark.asyncio
async def test_wild4_as_last_card_still_penalises_next_player(game_service):
    """Going out with a Wild Draw Four still forces the next player to draw four."""
    game_id = "rules-last-wild4"
    await prepare_state(
        game_service,
        game_id,
        hand=[Card(color="black", value="wild4")],
        top_card=Card(color="red", value="5"),
    )

    assert await game_service.play_card(game_id, "p1", 0, "blue") is True

    state = await game_service.get_game_state(game_id)
    assert state.status == "finished"
    assert state.winner == "p1"
    assert len(state.players[1].hand) == 11
    assert state.active_color == "blue"


@pytest.mark.asyncio
async def test_skip_skips_the_next_player(game_service):
    """A Skip moves the turn past the next seat."""
    game_id = "rules-skip"
    await prepare_state(
        game_service,
        game_id,
        hand=[Card(color="red", value="skip"), Card(color="blue", value="3")],
        top_card=Card(color="red", value="5"),
    )

    assert await game_service.play_card(game_id, "p1", 0) is True

    state = await game_service.get_game_state(game_id)
    # two players: skipping the opponent returns the turn to the player who skipped
    assert state.current_turn_index == 0


@pytest.mark.asyncio
async def test_reverse_in_four_player_game_flips_direction(game_service):
    """Reverse flips the direction; in a 4-seat game the previous seat plays next."""
    game_id = "rules-reverse-4p"
    state = await game_service.create_game(
        game_id, [{"player_id": p} for p in ("p1", "p2", "p3", "p4")]
    )
    state.discard_pile = [Card(color="red", value="5")]
    state.active_color = "red"
    state.players[0].hand = [Card(color="red", value="reverse"), Card(color="blue", value="3")]
    await game_service.save_game_state(state)

    assert await game_service.play_card(game_id, "p1", 0) is True

    state = await game_service.get_game_state(game_id)
    assert state.direction == -1
    assert state.current_turn_index == 3
