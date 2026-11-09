import pytest
from pydantic import ValidationError

from app.api.websockets.room import ACTION_ADAPTER, _dispatch
from app.services.game_service import ActionResult, Card


@pytest.mark.parametrize(
    "payload",
    [
        {"action": "play_card", "card_index": "0"},   # string index used to crash the loop
        {"action": "play_card"},                       # missing index
        {"action": "play_card", "card_index": -1},     # negative
        {"action": "play_card", "card_index": 1.5},    # float
        {"action": "play_card", "card_index": True},   # bool is not an index
        {"action": "summon_dragon"},                   # unknown action
        {},
        {"action": None},
    ],
)
def test_invalid_action_payloads_are_rejected(payload):
    """Every malformed payload is rejected as a validation error, not a crash."""
    with pytest.raises(ValidationError):
        ACTION_ADAPTER.validate_python(payload)


def test_valid_action_payloads_are_accepted():
    assert ACTION_ADAPTER.validate_python({"action": "draw_card"}).action == "draw_card"
    assert ACTION_ADAPTER.validate_python({"action": "pass_turn"}).action == "pass_turn"
    assert ACTION_ADAPTER.validate_python({"action": "say_uno"}).action == "say_uno"
    assert ACTION_ADAPTER.validate_python({"action": "challenge_uno"}).action == "challenge_uno"

    play = ACTION_ADAPTER.validate_python(
        {"action": "play_card", "card_index": 3, "chosen_color": "blue", "say_uno": True}
    )
    assert play.card_index == 3
    assert play.chosen_color == "blue"
    assert play.say_uno is True


class StubService:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def draw_card(self, game_id, player_id):
        self.calls.append(("draw", game_id, player_id))
        return self.result

    async def play_card(self, game_id, player_id, card_index, chosen_color=None, say_uno=False):
        self.calls.append(("play", card_index, chosen_color, say_uno))
        return self.result

    async def challenge_uno(self, game_id, challenger_id):
        self.calls.append(("challenge", challenger_id))
        return self.result


@pytest.mark.asyncio
async def test_play_action_is_dispatched_with_all_arguments():
    service = StubService(ActionResult(ok=True))
    action = ACTION_ADAPTER.validate_python(
        {"action": "play_card", "card_index": 2, "chosen_color": "red", "say_uno": True}
    )

    await _dispatch(service, "game", "p1", action)

    assert service.calls == [("play", 2, "red", True)]


@pytest.mark.asyncio
async def test_challenge_notice_names_the_penalised_player():
    service = StubService(ActionResult(ok=True, player_id="p2"))
    action = ACTION_ADAPTER.validate_python({"action": "challenge_uno"})

    result, notice = await _dispatch(service, "game", "p1", action)

    assert result.ok is True
    assert notice == {"type": "uno_penalty", "player_id": "p2"}


# ---------------------------------------------------------------------------
# Service level reason codes
# ---------------------------------------------------------------------------

async def prepare(game_service, game_id, hand, top_card):
    state = await game_service.create_game(game_id, [{"player_id": "p1"}, {"player_id": "p2"}])
    state.discard_pile = [top_card]
    state.active_color = top_card.color
    state.current_turn_index = 0
    state.direction = 1
    state.players[0].hand = list(hand)
    await game_service.save_game_state(state)
    return state


@pytest.mark.asyncio
async def test_invalid_color_is_rejected_without_corrupting_state(game_service):
    await prepare(game_service, "code-color", [Card(color="black", value="wild")], Card(color="red", value="5"))

    result = await game_service.play_card("code-color", "p1", 0, "purple")

    assert result.ok is False
    assert result.code == "invalid_color"
    state = await game_service.get_game_state("code-color")
    assert state.active_color == "red"


@pytest.mark.asyncio
async def test_index_out_of_range_has_its_own_code(game_service):
    await prepare(game_service, "code-index", [Card(color="red", value="2")], Card(color="red", value="5"))

    result = await game_service.play_card("code-index", "p1", 5)

    assert result.code == "card_not_in_hand"


@pytest.mark.asyncio
async def test_playing_out_of_turn_has_its_own_code(game_service):
    await prepare(game_service, "code-turn", [Card(color="red", value="2")], Card(color="red", value="5"))

    result = await game_service.play_card("code-turn", "p2", 0)

    assert result.code == "not_your_turn"


@pytest.mark.asyncio
async def test_non_matching_card_has_its_own_code(game_service):
    await prepare(game_service, "code-match", [Card(color="green", value="2")], Card(color="red", value="5"))

    result = await game_service.play_card("code-match", "p1", 0)

    assert result.code == "invalid_card"


@pytest.mark.asyncio
async def test_missing_color_has_its_own_code(game_service):
    await prepare(game_service, "code-color-missing", [Card(color="black", value="wild")], Card(color="red", value="5"))

    result = await game_service.play_card("code-color-missing", "p1", 0)

    assert result.code == "color_required"
