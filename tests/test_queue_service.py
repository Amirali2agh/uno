import pytest

from app.services.queue_service import QueueService
from app.utils.redis_keys import get_queue_key, get_queue_players_key


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


@pytest.mark.asyncio
async def test_player_is_removed_from_the_other_mode(redis):
    """A player can never sit in two matchmaking queues at once."""
    queue_service = QueueService(redis)

    await queue_service.join_queue(
        {"player_id": "player_a", "player_name": "", "player_avatar": "", "player_count": 2}
    )
    await queue_service.join_queue(
        {"player_id": "player_a", "player_name": "", "player_avatar": "", "player_count": 4}
    )

    assert await redis.llen(get_queue_key(2)) == 0
    assert await redis.llen(get_queue_key(4)) == 1
    assert await redis.hlen(get_queue_players_key(2)) == 0


@pytest.mark.asyncio
async def test_joining_twice_keeps_a_single_entry(redis):
    queue_service = QueueService(redis)
    payload = {"player_id": "player_a", "player_name": "A", "player_avatar": "", "player_count": 2}

    await queue_service.join_queue(payload)
    await queue_service.join_queue(payload)

    assert await redis.llen(get_queue_key(2)) == 1
    assert await redis.hlen(get_queue_players_key(2)) == 1


@pytest.mark.asyncio
async def test_concurrent_joins_do_not_lose_players(redis):
    """Concurrent queue mutations must not drop entries (the old loop did)."""
    import asyncio

    queue_service = QueueService(redis)
    await asyncio.gather(
        *[
            queue_service.join_queue(
                {"player_id": f"p{i}", "player_name": "", "player_avatar": "", "player_count": 2}
            )
            for i in range(10)
        ]
    )

    assert await redis.llen(get_queue_key(2)) == 10


@pytest.mark.asyncio
async def test_match_payloads_are_cleaned_up(redis):
    """Popping a match also removes the payload hash entries."""
    queue_service = QueueService(redis)
    for player_id in ("player_a", "player_b"):
        await queue_service.join_queue(
            {"player_id": player_id, "player_name": player_id, "player_avatar": "", "player_count": 2}
        )

    match = await queue_service.try_match(2)

    assert [p["player_name"] for p in match] == ["player_a", "player_b"]
    assert await redis.llen(get_queue_key(2)) == 0
    assert await redis.hlen(get_queue_players_key(2)) == 0
