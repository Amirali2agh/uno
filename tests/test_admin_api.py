import httpx
import pytest

from app.config import settings
from app.main import app
from app.redis_client import get_redis


@pytest.fixture
def admin_app(redis):
    """Point the app's Redis dependency at the isolated test database."""
    app.dependency_overrides[get_redis] = lambda: redis
    yield app
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_is_disabled_without_a_configured_token(admin_app, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_TOKEN", "")

    transport = httpx.ASGITransport(app=admin_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/stats")

    assert response.status_code == 503
    assert "disabled" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_requires_the_shared_secret(admin_app, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_TOKEN", "s3cret")

    transport = httpx.ASGITransport(app=admin_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        missing = await client.get("/admin/stats")
        wrong = await client.get("/admin/stats", headers={"X-Admin-Token": "nope"})
        ok = await client.get("/admin/stats", headers={"X-Admin-Token": "s3cret"})

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert ok.status_code == 200
    payload = ok.json()
    assert payload["status"] == "healthy"
    assert payload["scope"]["queue_2p_length"] == "global"
    assert payload["scope"]["active_rooms"].startswith("process:")


@pytest.mark.asyncio
async def test_health_endpoint_stays_public(admin_app):
    transport = httpx.ASGITransport(app=admin_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "running" in response.json()["message"]
