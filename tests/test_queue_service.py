import pytest
import pytest_asyncio
from app.redis_client import get_redis
from app.services.queue_service import QueueService
from app.utils.redis_keys import get_queue_key

@pytest_asyncio.fixture(autouse=True)
async def clean_redis_queues():
    redis = await get_redis()
    await redis.delete(get_queue_key(2))
    await redis.delete(get_queue_key(4))
    yield
    await redis.delete(get_queue_key(2))
    await redis.delete(get_queue_key(4))

@pytest.mark.asyncio
async def test_join_and_leave_queue():
    redis = await get_redis()
    queue_service = QueueService(redis)
    joined = await queue_service.join_queue({"player_id": "player_1", "player_name": "Test", "player_avatar": "", "player_count": 2})
    assert joined is True

@pytest.mark.asyncio
async def test_matchmaking_trigger_success():
    redis = await get_redis()
    queue_service = QueueService(redis)
    await queue_service.join_queue({"player_id": "player_a", "player_name": "", "player_avatar": "", "player_count": 2})
    await queue_service.join_queue({"player_id": "player_b", "player_name": "", "player_avatar": "", "player_count": 2})
    match = await queue_service.try_match(2)
    assert match is not None
    assert len(match) == 2
    assert match[0]["player_id"] == "player_a"
    assert match[1]["player_id"] == "player_b"

@pytest.mark.asyncio
async def test_matchmaking_insufficient_players():
    redis = await get_redis()
    queue_service = QueueService(redis)
    await queue_service.join_queue({"player_id": "player_a", "player_name": "", "player_avatar": "", "player_count": 2})
    match = await queue_service.try_match(2)
    assert match is None
