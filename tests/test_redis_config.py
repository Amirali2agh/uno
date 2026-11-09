import pytest

from app.config import settings


def test_config_loads():
    """Application settings expose the documented defaults."""
    assert settings.APP_NAME == "UNO Game Server"
    assert settings.DISCONNECT_TIMEOUT_SECONDS == 60


@pytest.mark.asyncio
async def test_redis_connection(redis):
    """The test fixture can talk to Redis."""
    assert await redis.ping() is True
