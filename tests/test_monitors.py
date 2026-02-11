import pytest
from httpx import AsyncClient


MONITOR_DATA = {
    "name": "My Website",
    "url": "https://example.com",
    "method": "GET",
    "check_interval": 300,
    "timeout": 30,
    "expected_status_code": 200,
    "is_public": True,
}


@pytest.mark.asyncio
async def test_create_monitor(authenticated_client: AsyncClient):
    response = await authenticated_client.post("/api/monitors", json=MONITOR_DATA)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Website"
    assert data["url"] == "https://example.com"
    assert data["current_status"] == "unknown"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_create_monitor_unauthenticated(client: AsyncClient):
    response = await client.post("/api/monitors", json=MONITOR_DATA)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_monitors_empty(authenticated_client: AsyncClient):
    response = await authenticated_client.get("/api/monitors")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_monitors(authenticated_client: AsyncClient):
    await authenticated_client.post("/api/monitors", json=MONITOR_DATA)
    await authenticated_client.post("/api/monitors", json={
        **MONITOR_DATA,
        "name": "Another Site",
        "url": "https://other.com",
    })

    response = await authenticated_client.get("/api/monitors")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_get_monitor(authenticated_client: AsyncClient):
    create_res = await authenticated_client.post("/api/monitors", json=MONITOR_DATA)
    monitor_id = create_res.json()["id"]

    response = await authenticated_client.get(f"/api/monitors/{monitor_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "My Website"


@pytest.mark.asyncio
async def test_get_monitor_not_found(authenticated_client: AsyncClient):
    response = await authenticated_client.get("/api/monitors/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_monitor(authenticated_client: AsyncClient):
    create_res = await authenticated_client.post("/api/monitors", json=MONITOR_DATA)
    monitor_id = create_res.json()["id"]

    response = await authenticated_client.patch(f"/api/monitors/{monitor_id}", json={
        "name": "Updated Name",
        "check_interval": 600,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["check_interval"] == 600
    assert data["url"] == "https://example.com"  # unchanged


@pytest.mark.asyncio
async def test_update_monitor_not_found(authenticated_client: AsyncClient):
    response = await authenticated_client.patch("/api/monitors/nonexistent", json={
        "name": "Updated",
    })
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_monitor(authenticated_client: AsyncClient):
    create_res = await authenticated_client.post("/api/monitors", json=MONITOR_DATA)
    monitor_id = create_res.json()["id"]

    response = await authenticated_client.delete(f"/api/monitors/{monitor_id}")
    assert response.status_code == 204

    # Verify it's gone
    response = await authenticated_client.get(f"/api/monitors/{monitor_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_monitor_not_found(authenticated_client: AsyncClient):
    response = await authenticated_client.delete("/api/monitors/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_toggle_active(authenticated_client: AsyncClient):
    create_res = await authenticated_client.post("/api/monitors", json=MONITOR_DATA)
    monitor_id = create_res.json()["id"]
    assert create_res.json()["is_active"] is True

    # Pause
    response = await authenticated_client.patch(f"/api/monitors/{monitor_id}", json={
        "is_active": False,
    })
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    # Resume
    response = await authenticated_client.patch(f"/api/monitors/{monitor_id}", json={
        "is_active": True,
    })
    assert response.status_code == 200
    assert response.json()["is_active"] is True


@pytest.mark.asyncio
async def test_monitor_plan_limit(authenticated_client: AsyncClient):
    # Free plan allows 5 monitors
    for i in range(5):
        res = await authenticated_client.post("/api/monitors", json={
            **MONITOR_DATA,
            "name": f"Monitor {i}",
            "url": f"https://example{i}.com",
        })
        assert res.status_code == 201

    # 6th should be rejected
    response = await authenticated_client.post("/api/monitors", json={
        **MONITOR_DATA,
        "name": "Monitor 6",
        "url": "https://example6.com",
    })
    assert response.status_code == 403
    assert "plan" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_monitor_interval_limit(authenticated_client: AsyncClient):
    # Free plan min interval is 300s (5 min)
    response = await authenticated_client.post("/api/monitors", json={
        **MONITOR_DATA,
        "check_interval": 60,  # 1 minute - not allowed on free
    })
    assert response.status_code == 403
    assert "interval" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_monitor_invalid_url(authenticated_client: AsyncClient):
    response = await authenticated_client.post("/api/monitors", json={
        **MONITOR_DATA,
        "url": "not-a-url",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_monitor_invalid_method(authenticated_client: AsyncClient):
    response = await authenticated_client.post("/api/monitors", json={
        **MONITOR_DATA,
        "method": "INVALID",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_monitor_interval_limit(authenticated_client: AsyncClient):
    """Test that plan limits are enforced when updating check interval."""
    create_res = await authenticated_client.post("/api/monitors", json=MONITOR_DATA)
    monitor_id = create_res.json()["id"]

    # Free plan min interval is 300s — trying 60s should be rejected
    response = await authenticated_client.patch(f"/api/monitors/{monitor_id}", json={
        "check_interval": 60,
    })
    assert response.status_code == 403
    assert "interval" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_monitors_isolated_between_users(client: AsyncClient):
    # Create user 1 and add a monitor
    res1 = await client.post("/auth/signup", json={
        "name": "User One",
        "email": "user1@example.com",
        "password": "password123",
        "account_slug": "user-one",
    })
    cookies1 = res1.cookies
    client.cookies.update(cookies1)
    await client.post("/api/monitors", json=MONITOR_DATA)

    # Logout and create user 2
    await client.post("/auth/logout")
    client.cookies.clear()

    res2 = await client.post("/auth/signup", json={
        "name": "User Two",
        "email": "user2@example.com",
        "password": "password123",
        "account_slug": "user-two",
    })
    client.cookies.update(res2.cookies)

    # User 2 should see 0 monitors
    response = await client.get("/api/monitors")
    assert response.status_code == 200
    assert len(response.json()) == 0
