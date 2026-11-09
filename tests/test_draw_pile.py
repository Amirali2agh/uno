import pytest

from app.services.game_service import Card


async def prepare(game_service, game_id, *, hand, top_card, draw_pile, discard_pile=None):
    state = await game_service.create_game(game_id, [{"player_id": "p1"}, {"player_id": "p2"}])
    state.discard_pile = discard_pile if discard_pile is not None else [top_card]
    state.active_color = top_card.color
    state.current_turn_index = 0
    state.direction = 1
    state.players[0].hand = list(hand)
    state.draw_pile = list(draw_pile)
    await game_service.save_game_state(state)
    return state


@pytest.mark.asyncio
async def test_discard_pile_is_recycled_and_keeps_the_top_card(game_service):
    """When the draw pile runs out, played cards are reshuffled back in."""
    game_id = "pile-recycle"
    discarded = [Card(color="red", value=str(i % 9)) for i in range(5)]
    state = await prepare(
        game_service,
        game_id,
        hand=[Card(color="blue", value="3")],
        top_card=Card(color="red", value="5"),
        discard_pile=discarded + [Card(color="red", value="5")],
        draw_pile=[],
    )

    result = await game_service.draw_card(game_id, "p1")

    assert result.ok is True
    state = await game_service.get_game_state(game_id)
    assert len(state.players[0].hand) == 2
    # the played card stays on the table, the other five are back in the pile
    assert len(state.discard_pile) == 1
    assert len(state.draw_pile) == 4


@pytest.mark.asyncio
async def test_penalty_draws_from_a_recycled_pile(game_service):
    """A Draw Two still deals two cards when the draw pile has to be rebuilt."""
    game_id = "pile-penalty"
    state = await prepare(
        game_service,
        game_id,
        hand=[Card(color="red", value="draw2"), Card(color="red", value="7")],
        top_card=Card(color="red", value="5"),
        draw_pile=[],
        discard_pile=[Card(color="green", value="1"), Card(color="green", value="2"),
                      Card(color="red", value="5")],
    )

    result = await game_service.play_card(game_id, "p1", 0)

    assert result.ok is True
    state = await game_service.get_game_state(game_id)
    assert len(state.players[1].hand) == 9  # 7 + 2


@pytest.mark.asyncio
async def test_both_piles_empty_passes_the_turn_without_crashing(game_service):
    """With nothing left to draw the turn simply passes."""
    game_id = "pile-empty"
    await prepare(
        game_service,
        game_id,
        hand=[Card(color="blue", value="3")],
        top_card=Card(color="red", value="5"),
        draw_pile=[],
    )
    state = await game_service.get_game_state(game_id)
    assert state.discard_pile == [Card(color="red", value="5")]

    result = await game_service.draw_card(game_id, "p1")

    assert result.ok is True
    state = await game_service.get_game_state(game_id)
    assert state.current_turn_index == 1
    assert len(state.players[0].hand) == 1  # nothing was drawn


@pytest.mark.asyncio
async def test_penalty_with_an_exhausted_pile_does_not_crash(game_service):
    """A penalty that cannot be fully dealt must not break the game."""
    game_id = "pile-short-penalty"
    await prepare(
        game_service,
        game_id,
        hand=[Card(color="black", value="wild4"), Card(color="blue", value="1")],
        top_card=Card(color="red", value="5"),
        draw_pile=[],
        discard_pile=[Card(color="red", value="5"), Card(color="blue", value="2")],
    )

    result = await game_service.play_card(game_id, "p1", 0, "green")

    assert result.ok is True
    state = await game_service.get_game_state(game_id)
    # only the two recyclable cards existed; the opponent draws both, no exception
    assert len(state.players[1].hand) == 9
    assert state.status == "active"


@pytest.mark.asyncio
async def test_recycled_wild_card_is_playable_again(game_service):
    """A wild card that goes through the recycling keeps its wild semantics."""
    game_id = "pile-wild"
    state = await prepare(
        game_service,
        game_id,
        hand=[Card(color="blue", value="3")],
        top_card=Card(color="red", value="5"),
        draw_pile=[],
        discard_pile=[Card(color="black", value="wild"), Card(color="red", value="5")],
    )

    await game_service.draw_card(game_id, "p1")

    state = await game_service.get_game_state(game_id)
    recycled = state.players[0].hand[-1]
    assert recycled.color == "black"
    assert recycled.value == "wild"
