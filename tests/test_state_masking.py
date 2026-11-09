import pytest

from app.managers.room_manager import RoomManager
from app.services.game_service import Card


class MockWebSocket:
    def __init__(self):
        self.sent_messages = []

    async def accept(self):
        pass

    async def send_json(self, data: dict):
        self.sent_messages.append(data)


@pytest.mark.asyncio
async def test_projection_hides_opponent_hands_and_draw_order(game_service, start_game):
    state = await start_game(
        "masking-1", [{"player_id": "p1"}, {"player_id": "p2"}]
    )
    state.players[0].hand = [Card(color="red", value="1")]
    state.players[1].hand = [Card(color="blue", value="9")]
    state.draw_pile = [Card(color="green", value="2"), Card(color="black", value="wild")]
    await game_service.save_game_state(state)

    view = state.for_player("p1").model_dump()

    assert view["players"][0]["hand"] == [{"color": "red", "value": "1"}]
    assert view["players"][1]["hand"] == []
    assert view["players"][1]["hand_size"] == 1
    assert view["draw_pile_size"] == 2
    assert "draw_pile" not in view
    assert "blue" not in str(view)


@pytest.mark.asyncio
async def test_room_broadcast_is_personalised(game_service, start_game, redis):
    state = await start_game("masking-2", [{"player_id": "p1"}, {"player_id": "p2"}])
    state.players[0].hand = [Card(color="red", value="1")]
    state.players[1].hand = [Card(color="blue", value="9")]
    await game_service.save_game_state(state)

    manager = RoomManager(timeout_seconds=1)
    ws1, ws2 = MockWebSocket(), MockWebSocket()
    await manager.connect("masking-2", "p1", ws1, redis)
    await manager.connect("masking-2", "p2", ws2, redis)

    await manager.broadcast_state("masking-2", state)

    view1 = ws1.sent_messages[-1]["state"]
    view2 = ws2.sent_messages[-1]["state"]

    assert view1["players"][0]["hand"] == [{"color": "red", "value": "1"}]
    assert view1["players"][1]["hand"] == []
    assert view2["players"][1]["hand"] == [{"color": "blue", "value": "9"}]
    assert view2["players"][0]["hand"] == []
