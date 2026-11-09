import asyncio

import pytest

from app.managers.room_manager import RoomManager
from app.services.game_service import Card, GameService


class MockWebSocket:
    def __init__(self):
        self.sent_messages = []

    async def accept(self):
        pass

    async def send_json(self, data: dict):
        self.sent_messages.append(data)


@pytest.mark.asyncio
async def test_lock_is_not_held_forever(redis, game_service, start_game):
    """A stuck lock holder must not hang the game: the action fails fast."""
    game_id = "lock-busy"
    await start_game(game_id, [{"player_id": "p1"}, {"player_id": "p2"}])

    # Simulate another worker holding the lock.
    holder = redis.lock(f"uno:lock:game:{game_id}", timeout=30)
    assert await holder.acquire(blocking=False) is True
    try:
        fast_service = GameService(redis, lock_blocking_timeout=0.2)
        result = await asyncio.wait_for(fast_service.draw_card(game_id, "p1"), timeout=5)

        assert result.ok is False
        assert result.code == "game_busy"
    finally:
        await holder.release()


@pytest.mark.asyncio
async def test_disconnect_timer_is_retained_and_cancelled_on_reconnect(redis, game_service, start_game):
    """Reconnecting cancels the pending timer; no game over is declared later."""
    game_id = "timer-reconnect"
    await start_game(game_id, [{"player_id": "p1"}, {"player_id": "p2"}])

    manager = RoomManager(timeout_seconds=0.3)
    ws = MockWebSocket()
    await manager.connect(game_id, "p1", ws, redis)

    await manager.disconnect(game_id, "p1", redis)
    assert (game_id, "p1") in manager._timeout_tasks

    # Player reconnects before the grace period ends.
    await manager.connect(game_id, "p1", ws, redis)
    assert (game_id, "p1") not in manager._timeout_tasks

    await asyncio.sleep(0.6)

    state = await game_service.get_game_state(game_id)
    assert state.status == "active"
    assert state.winner is None


@pytest.mark.asyncio
async def test_repeated_disconnects_keep_a_single_timer(redis, game_service, start_game):
    """Disconnect churn must not pile up timers that fire twice."""
    game_id = "timer-churn"
    await start_game(game_id, [{"player_id": "p1"}, {"player_id": "p2"}])

    manager = RoomManager(timeout_seconds=0.3)
    ws = MockWebSocket()
    await manager.connect(game_id, "p1", ws, redis)

    await manager.disconnect(game_id, "p1", redis)
    await manager.disconnect(game_id, "p1", redis)
    await manager.disconnect(game_id, "p1", redis)

    assert len([k for k in manager._timeout_tasks if k[0] == game_id]) == 1

    await asyncio.sleep(0.6)

    state = await game_service.get_game_state(game_id)
    assert state.status == "finished"
    # one game-over message per seat at most
    game_over = [m for m in ws.sent_messages if m.get("type") == "game_over"]
    assert len(game_over) <= 1
