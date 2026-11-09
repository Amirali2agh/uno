import pytest

from app.services.queue_service import QueueService
from app.utils.redis_keys import get_queue_key


@pytest.mark.asyncio
async def test_join_and_leave_queue(redis):
    queue_service = QueueService(redis)

    joined = await queue_service.join_queue(
        {"player_id": "player_1", "player_name": "Test", "player_avatar": "", "player_count": 2}
    )

    assert joined is True
    assert await redis.llen(get_queue_key(2)) == 1


@pytest.mark.asyncio
async def test_matchmaking_trigger_success(redis):
    queue_service = QueueService(redis)
    await queue_service.join_queue(
        {"player_id": "player_a", "player_name": "", "player_avatar": "", "player_count": 2}
    )
    await queue_service.join_queue(
        {"player_id": "player_b", "player_name": "", "player_avatar": "", "player_count": 2}
    )

    match = await queue_service.try_match(2)

    assert match is not None
    assert [p["player_id"] for p in match] == ["player_a", "player_b"]
    assert await redis.llen(get_queue_key(2)) == 0


@pytest.mark.asyncio
async def test_matchmaking_insufficient_players(redis):
    queue_service = QueueService(redis)
    await queue_service.join_queue(
        {"player_id": "player_a", "player_name": "", "player_avatar": "", "player_count": 2}
    )

    assert await queue_service.try_match(2) is None
    assert await redis.llen(get_queue_key(2)) == 1


@pytest.mark.asyncio
async def test_leave_queue_removes_player(redis):
    queue_service = QueueService(redis)
    await queue_service.join_queue(
        {"player_id": "player_a", "player_name": "", "player_avatar": "", "player_count": 2}
    )

    assert await queue_service.leave_queue("player_a", 2) is True
    assert await redis.llen(get_queue_key(2)) == 0
