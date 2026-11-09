"""Shared pytest fixtures.

Every test gets its own Redis connection bound to the *current* event loop, and a
dedicated Redis database that is flushed around each test. This keeps tests
independent of each other and of any server running against the default database.
"""

import os
from urllib.parse import urlsplit, urlunsplit

import pytest_asyncio
import redis.asyncio as redis_async

from app.config import settings
from app.services.game_service import Card, GameService

# A database that is never used by the application itself (default DB is 0).
TEST_DB_INDEX = 15


def test_redis_url() -> str:
    """Redis URL used by the test suite (override with TEST_REDIS_URL)."""
    explicit = os.getenv("TEST_REDIS_URL")
    if explicit:
        return explicit

    parts = urlsplit(settings.REDIS_URL)
    return urlunsplit((parts.scheme, parts.netloc, f"/{TEST_DB_INDEX}", "", ""))


@pytest_asyncio.fixture
async def redis():
    """Isolated Redis client: fresh connection per test, flushed database."""
    client = redis_async.from_url(
        test_redis_url(),
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest_asyncio.fixture
async def game_service(redis):
    """GameService wired to the isolated Redis database."""
    return GameService(redis)


@pytest_asyncio.fixture
async def start_game(game_service):
    """Create a game with a neutral starting card so tests are deterministic.

    ``create_game`` applies the effect of the flipped card (skip / reverse /
    draw2), which would otherwise make turn order depend on the shuffle.
    """

    async def _start(game_id, players, top_card=None, direction=1, turn_index=0):
        state = await game_service.create_game(game_id, players)
        top = top_card or Card(color="red", value="5")
        state.discard_pile = [top]
        state.active_color = top.color
        state.current_turn_index = turn_index
        state.direction = direction
        await game_service.save_game_state(state)
        return state

    return _start
