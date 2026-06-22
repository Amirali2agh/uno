import pytest
from app.config import settings
from app.redis_client import get_redis

# Mark this test to run asynchronously since our Redis client is async
@pytest.mark.asyncio
async def test_config_loads():
    """
    Test if the application settings are loaded correctly.
    """
    # Check if default values are correctly set
    assert settings.APP_NAME == "UNO Game Server"
    assert settings.DISCONNECT_TIMEOUT_SECONDS == 60

@pytest.mark.asyncio
async def test_redis_connection():
    """
    Test if the application can successfully connect to the Redis server.
    """
    # Get the Redis client instance
    redis = await get_redis()
    
    # Send a PING command to Redis
    response = await redis.ping()
    
    # Redis should return True for a successful PING
    assert response is True