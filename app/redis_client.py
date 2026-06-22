import redis.asyncio as redis
from app.config import settings

# Create a global Redis client using Connection Pool
# decode_responses=True automatically decodes bytes to utf-8 strings
redis_client = redis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True
)

async def get_redis() -> redis.Redis:
    """
    Dependency to get the active Redis client instance.
    """
    return redis_client