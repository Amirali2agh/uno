import pytest
import pytest_asyncio
# Import the global redis_client instance directly to manage its lifecycle
from app.redis_client import redis_client, get_redis
from app.services.queue_service import QueueService
from app.utils.redis_keys import get_queue_key

@pytest_asyncio.fixture(autouse=True)
async def clean_redis_queues():
    """
    Fixture to clear the matchmaking queues and reset Redis connections.
    This prevents the 'attached to a different loop' error between tests.
    """
    # 1. Close active connections from previous event loops
    await redis_client.aclose()
    
    # 2. Re-acquire client (it will automatically bind to the current active loop)
    redis = await get_redis()
    
    # 3. Clean database queues before starting the test
    await redis.delete(get_queue_key(2))
    await redis.delete(get_queue_key(4))
    
    # Yield control to the actual test function
    yield
    
    # 4. Clean up and close connections after the test finishes
    await redis.delete(get_queue_key(2))
    await redis.delete(get_queue_key(4))
    await redis_client.aclose()

@pytest.mark.asyncio
async def test_join_and_leave_queue():
    """
    Verify that players can successfully join and leave the matchmaking queues.
    """
    redis = await get_redis()
    queue_service = QueueService(redis)
    
    # Join queue test
    joined = await queue_service.join_queue("player_1", 2)
    assert joined is True
    assert await redis.llen(get_queue_key(2)) == 1
    
    # Prevent duplicate entries test
    await queue_service.join_queue("player_1", 2)
    assert await redis.llen(get_queue_key(2)) == 1
    
    # Leave queue test
    left = await queue_service.leave_queue("player_1", 2)
    assert left is True
    assert await redis.llen(get_queue_key(2)) == 0

@pytest.mark.asyncio
async def test_matchmaking_trigger_success():
    """
    Verify that matchmaking triggers successfully and pops players when enough players join.
    """
    redis = await get_redis()
    queue_service = QueueService(redis)
    
    # Add exactly 2 players to 2p queue
    await queue_service.join_queue("player_a", 2)
    await queue_service.join_queue("player_b", 2)
    
    # Attempt to match
    match = await queue_service.try_match(2)
    
    # Should successfully return the exact players in FIFO order
    assert match == ["player_a", "player_b"]
    assert await redis.llen(get_queue_key(2)) == 0

@pytest.mark.asyncio
async def test_matchmaking_insufficient_players():
    """
    Verify that matchmaking returns None if there aren't enough players in the queue.
    """
    redis = await get_redis()
    queue_service = QueueService(redis)
    
    # Add only 1 player to a 2p queue
    await queue_service.join_queue("player_a", 2)
    
    # Attempt to match (should fail and return None)
    match = await queue_service.try_match(2)
    assert match is None
    
    # Player must still remain in the queue
    assert await redis.llen(get_queue_key(2)) == 1