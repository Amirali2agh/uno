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
    # winner is always a player id, never a sentence
    assert state.winner == "p2"
    assert state.end_reason == "disconnect_timeout"
    assert state.disconnected_player_id == "p1"


def test_global_manager_uses_configured_timeout():
    """DISCONNECT_TIMEOUT_SECONDS drives the global manager's grace period."""
    from app.config import settings
    from app.managers.room_manager import room_manager

    assert room_manager.timeout_seconds == settings.DISCONNECT_TIMEOUT_SECONDS


@pytest.mark.asyncio
async def test_disconnect_in_a_four_player_game_has_no_single_winner(redis, game_service):
    """With more seats left the match is abandoned instead of awarding a winner."""
    game_id = "timeout-4p"
    await game_service.create_game(
        game_id, [{"player_id": p} for p in ("p1", "p2", "p3", "p4")]
    )

    manager = RoomManager(timeout_seconds=0.3)
    for player_id in ("p1", "p2", "p3", "p4"):
        await manager.connect(game_id, player_id, MockWebSocket(), redis)

    await manager.disconnect(game_id, "p1", redis)
    await asyncio.sleep(0.6)

    state = await game_service.get_game_state(game_id)
    assert state.status == "finished"
    assert state.winner is None
    assert state.end_reason == "disconnect_timeout"
    assert state.disconnected_player_id == "p1"
