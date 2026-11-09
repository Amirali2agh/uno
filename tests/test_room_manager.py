import asyncio

import pytest

from app.managers.room_manager import RoomManager
from app.services.game_service import GameService


class MockWebSocket:
    def __init__(self):
        self.is_accepted = False
        self.sent_messages = []

    async def accept(self):
        self.is_accepted = True

    async def send_json(self, data: dict):
        self.sent_messages.append(data)


@pytest.mark.asyncio
async def test_room_broadcast(redis):
    """RoomManager accepts connections and broadcasts to every seat."""
    manager = RoomManager(timeout_seconds=1)

    ws1 = MockWebSocket()
    ws2 = MockWebSocket()

    await manager.connect("game-1", "p1", ws1, redis)
    await manager.connect("game-1", "p2", ws2, redis)
    await manager.broadcast("game-1", {"type": "test_msg"})

    assert len(ws1.sent_messages) == 1
    assert len(ws2.sent_messages) == 1
    assert ws1.is_accepted is True


@pytest.mark.asyncio
async def test_disconnect_timeout(redis):
    """A player who does not reconnect loses the game after the timeout."""
    game_service = GameService(redis)
    manager = RoomManager(timeout_seconds=1)

    game_id = "timeout-game-id"
    await game_service.create_game(game_id, [{"player_id": "p1"}, {"player_id": "p2"}])

    ws1 = MockWebSocket()
    ws2 = MockWebSocket()
    await manager.connect(game_id, "p1", ws1, redis)
    await manager.connect(game_id, "p2", ws2, redis)

    await manager.disconnect(game_id, "p1", redis)

    await asyncio.sleep(1.2)

    state = await game_service.get_game_state(game_id)
    assert state.status == "finished"
    assert "p1 disconnected" in state.winner
