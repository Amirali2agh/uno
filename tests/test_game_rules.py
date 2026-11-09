import pytest

from app.services.game_service import Card, GameState


async def prepare_state(game_service, game_id, hand, top_card, active_color=None):
    """Persist a deterministic game state with a single player holding `hand`."""
    state = await game_service.create_game(
        game_id, [{"player_id": "p1"}, {"player_id": "p2"}]
    )
    state.discard_pile = [top_card]
    state.active_color = active_color or top_card.color
    state.current_turn_index = 0
    state.direction = 1
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

    assert played.ok is False
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

    assert played.ok is True
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

    assert (await game_service.play_card(game_id, "p1", 1, "yellow")).ok is True

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

    assert (await game_service.play_card(game_id, "p1", 0)).ok is True

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

    assert (await game_service.play_card(game_id, "p1", 0, "blue")).ok is True

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

    assert (await game_service.play_card(game_id, "p1", 0)).ok is True

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
    state.current_turn_index = 0
    state.direction = 1
    state.players[0].hand = [Card(color="red", value="reverse"), Card(color="blue", value="3")]
    await game_service.save_game_state(state)

    assert (await game_service.play_card(game_id, "p1", 0)).ok is True

    state = await game_service.get_game_state(game_id)
    assert state.direction == -1
    assert state.current_turn_index == 3


async def _create_with_start_card(game_service, game_id, value, player_count=2):
    """Create a game and force the flipped starting card to a known action card."""
    players = [{"player_id": f"p{i + 1}"} for i in range(player_count)]
    state = await game_service.create_game(game_id, players)
    state.discard_pile = [Card(color="red", value=value)]
    state.active_color = "red"
    state.current_turn_index = 0
    state.direction = 1
    state.players[0].hand = [Card(color="blue", value="1")]
    steps = game_service._apply_starting_card(state, state.discard_pile[-1])
    if steps:
        game_service._next_turn(state, steps)
    await game_service.save_game_state(state)
    return state


@pytest.mark.asyncio
async def test_starting_skip_skips_first_player(game_service):
    state = await _create_with_start_card(game_service, "start-skip", "skip")

    assert state.current_turn_index == 1
    assert len(state.players[1].hand) == 7


@pytest.mark.asyncio
async def test_starting_draw2_penalises_first_player(game_service):
    state = await _create_with_start_card(game_service, "start-draw2", "draw2")

    assert state.current_turn_index == 1
    assert len(state.players[0].hand) == 3  # 1 seeded + 2 drawn


@pytest.mark.asyncio
async def test_starting_reverse_two_players_acts_as_skip(game_service):
    state = await _create_with_start_card(game_service, "start-reverse-2p", "reverse")

    assert state.direction == -1
    assert state.current_turn_index == 1


@pytest.mark.asyncio
async def test_starting_reverse_four_players_flips_direction(game_service):
    state = await _create_with_start_card(game_service, "start-reverse-4p", "reverse", 4)

    assert state.direction == -1
    assert state.current_turn_index == 0
    # player 0 starts, then play continues to seat 3
    game_service._next_turn(state)
    assert state.current_turn_index == 3


@pytest.mark.asyncio
async def test_create_game_flips_a_playable_starting_card(game_service):
    """The real flip never starts the game on a black card."""
    for _ in range(10):
        state = await game_service.create_game(
            "start-flip", [{"player_id": "p1"}, {"player_id": "p2"}]
        )
        assert state.discard_pile[-1].color != "black"
        assert state.active_color == state.discard_pile[-1].color


@pytest.mark.asyncio
async def test_drawing_a_playable_card_keeps_the_turn(game_service):
    """Official rule: after drawing a playable card the player may play it."""
    game_id = "draw-play-keeps-turn"
    state = await prepare_state(
        game_service,
        game_id,
        hand=[Card(color="blue", value="1")],
        top_card=Card(color="red", value="5"),
    )
    # next card off the pile is a red card, which matches the active colour
    state.draw_pile = [Card(color="red", value="7")]
    await game_service.save_game_state(state)

    assert (await game_service.draw_card(game_id, "p1")).ok is True

    state = await game_service.get_game_state(game_id)
    assert state.current_turn_index == 0                    # still p1's turn
    assert state.drawn_card_index == 1                       # the newly drawn card
    assert (await game_service.play_card(game_id, "p1", 1)).ok is True

    state = await game_service.get_game_state(game_id)
    assert state.drawn_card_index is None
    assert state.current_turn_index == 1                     # turn passed after playing


@pytest.mark.asyncio
async def test_drawing_an_unplayable_card_passes_the_turn(game_service):
    game_id = "draw-unplayable"
    state = await prepare_state(
        game_service,
        game_id,
        hand=[Card(color="blue", value="1")],
        top_card=Card(color="red", value="5"),
    )
    state.draw_pile = [Card(color="green", value="3")]
    await game_service.save_game_state(state)

    assert (await game_service.draw_card(game_id, "p1")).ok is True

    state = await game_service.get_game_state(game_id)
    assert state.current_turn_index == 1
    assert state.drawn_card_index is None
    assert len(state.players[0].hand) == 2


@pytest.mark.asyncio
async def test_cannot_draw_twice_in_one_turn(game_service):
    game_id = "draw-twice"
    state = await prepare_state(
        game_service,
        game_id,
        hand=[Card(color="blue", value="1")],
        top_card=Card(color="red", value="5"),
    )
    state.draw_pile = [Card(color="red", value="7")]
    await game_service.save_game_state(state)

    assert (await game_service.draw_card(game_id, "p1")).ok is True
    assert (await game_service.draw_card(game_id, "p1")).ok is False


@pytest.mark.asyncio
async def test_cannot_play_another_card_after_drawing(game_service):
    game_id = "draw-other-card"
    state = await prepare_state(
        game_service,
        game_id,
        hand=[Card(color="red", value="2")],
        top_card=Card(color="red", value="5"),
    )
    state.draw_pile = [Card(color="red", value="7")]
    await game_service.save_game_state(state)

    assert (await game_service.draw_card(game_id, "p1")).ok is True

    # index 0 is a different (legal) card; only the drawn one (index 1) may be played
    assert (await game_service.play_card(game_id, "p1", 0)).ok is False
    assert (await game_service.play_card(game_id, "p1", 1)).ok is True


@pytest.mark.asyncio
async def test_pass_turn_after_drawing(game_service):
    game_id = "draw-pass"
    state = await prepare_state(
        game_service,
        game_id,
        hand=[Card(color="blue", value="1")],
        top_card=Card(color="red", value="5"),
    )
    state.draw_pile = [Card(color="red", value="7")]
    await game_service.save_game_state(state)

    assert (await game_service.draw_card(game_id, "p1")).ok is True
    assert (await game_service.pass_turn(game_id, "p1")).ok is True

    state = await game_service.get_game_state(game_id)
    assert state.current_turn_index == 1
    assert state.drawn_card_index is None
    assert len(state.players[0].hand) == 2


@pytest.mark.asyncio
async def test_cannot_pass_without_drawing(game_service):
    game_id = "pass-without-draw"
    await prepare_state(
        game_service,
        game_id,
        hand=[Card(color="red", value="2")],
        top_card=Card(color="red", value="5"),
    )

    assert (await game_service.pass_turn(game_id, "p1")).ok is False


async def _two_card_state(game_service, game_id):
    """p1 holds two red cards; a play leaves them on one card."""
    return await prepare_state(
        game_service,
        game_id,
        hand=[Card(color="red", value="2"), Card(color="red", value="3")],
        top_card=Card(color="red", value="5"),
    )


@pytest.mark.asyncio
async def test_missing_uno_call_is_penalised(game_service):
    game_id = "uno-missed"
    await _two_card_state(game_service, game_id)

    assert (await game_service.play_card(game_id, "p1", 0)).ok is True

    state = await game_service.get_game_state(game_id)
    assert state.uno_window == "p1"
    assert len(state.players[0].hand) == 1

    assert (await game_service.challenge_uno(game_id, "p2")).player_id == "p1"

    state = await game_service.get_game_state(game_id)
    assert len(state.players[0].hand) == 3   # 1 + 2 penalty cards
    assert state.uno_window is None


@pytest.mark.asyncio
async def test_uno_declared_with_the_play_is_safe(game_service):
    game_id = "uno-declared"
    await _two_card_state(game_service, game_id)

    assert (await game_service.play_card(game_id, "p1", 0, say_uno=True)).ok is True

    state = await game_service.get_game_state(game_id)
    assert state.uno_window is None
    assert state.players[0].uno_declared is True

    # nothing to challenge any more
    assert (await game_service.challenge_uno(game_id, "p2")).ok is False


@pytest.mark.asyncio
async def test_saying_uno_before_the_challenge(game_service):
    game_id = "uno-late-call"
    await _two_card_state(game_service, game_id)
    await game_service.play_card(game_id, "p1", 0)

    assert (await game_service.say_uno(game_id, "p1")).ok is True
    # declaring late keeps the window open, but a challenge now backfires
    assert (await game_service.challenge_uno(game_id, "p2")).player_id == "p2"

    state = await game_service.get_game_state(game_id)
    assert len(state.players[1].hand) == 9   # 7 + 2 penalty cards
    assert len(state.players[0].hand) == 1


@pytest.mark.asyncio
async def test_cannot_say_uno_with_more_than_one_card(game_service):
    game_id = "uno-too-early"
    await prepare_state(
        game_service,
        game_id,
        hand=[Card(color="red", value="2"), Card(color="red", value="3")],
        top_card=Card(color="red", value="5"),
    )

    assert (await game_service.say_uno(game_id, "p1")).ok is False


@pytest.mark.asyncio
async def test_uno_window_closes_when_the_next_player_acts(game_service):
    game_id = "uno-window-closes"
    state = await _two_card_state(game_service, game_id)
    state.draw_pile = [Card(color="green", value="9")]
    await game_service.save_game_state(state)

    await game_service.play_card(game_id, "p1", 0)
    assert (await game_service.get_game_state(game_id)).uno_window == "p1"

    # p2 draws: the chance to challenge is gone
    assert (await game_service.draw_card(game_id, "p2")).ok is True
    state = await game_service.get_game_state(game_id)
    assert state.uno_window is None
    assert (await game_service.challenge_uno(game_id, "p2")).ok is False
