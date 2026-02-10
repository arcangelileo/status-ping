import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "StatusPing"
    assert "version" in data


@pytest.mark.asyncio
async def test_landing_page(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert "StatusPing" in response.text


@pytest.mark.asyncio
async def test_login_page(client: AsyncClient):
    response = await client.get("/login")
    assert response.status_code == 200
    assert "Log in" in response.text


@pytest.mark.asyncio
async def test_signup_page(client: AsyncClient):
    response = await client.get("/signup")
    assert response.status_code == 200
    assert "Create your account" in response.text
