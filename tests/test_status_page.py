"""Tests for the public status page and monitor detail view."""
import pytest
from datetime import datetime, timedelta, timezone

from httpx import AsyncClient
from sqlalchemy import select

from app.models.check_result import CheckResult
from app.models.incident import Incident
from app.models.monitor import Monitor

from tests.conftest import test_session_factory


MONITOR_DATA = {
    "name": "API Server",
    "url": "https://api.example.com",
    "method": "GET",
    "check_interval": 300,
    "timeout": 30,
    "expected_status_code": 200,
    "is_public": True,
}


@pytest.mark.asyncio
async def test_public_status_page_renders(authenticated_client: AsyncClient):
    """Test that the public status page renders for a valid slug."""
    # Create a monitor so there's content
    await authenticated_client.post("/api/monitors", json=MONITOR_DATA)

    # Access the public status page (no auth needed)
    response = await authenticated_client.get("/s/test-company")
    assert response.status_code == 200
    assert "Service Status" in response.text
    assert "API Server" in response.text


@pytest.mark.asyncio
async def test_public_status_page_not_found(client: AsyncClient):
    """Test 404 for non-existent status page."""
    response = await client.get("/s/nonexistent-slug")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_public_status_page_all_up(authenticated_client: AsyncClient):
    """Test status page shows 'All Systems Operational' when monitors are up."""
    res = await authenticated_client.post("/api/monitors", json=MONITOR_DATA)
    monitor_id = res.json()["id"]

    # Mark monitor as up
    async with test_session_factory() as db:
        result = await db.execute(select(Monitor).where(Monitor.id == monitor_id))
        monitor = result.scalar_one()
        monitor.current_status = "up"
        await db.commit()

    response = await authenticated_client.get("/s/test-company")
    assert response.status_code == 200
    assert "All Systems Operational" in response.text


@pytest.mark.asyncio
async def test_public_status_page_with_down_monitor(authenticated_client: AsyncClient):
    """Test status page shows disruption when a monitor is down."""
    res = await authenticated_client.post("/api/monitors", json=MONITOR_DATA)
    monitor_id = res.json()["id"]

    # Mark monitor as down
    async with test_session_factory() as db:
        result = await db.execute(select(Monitor).where(Monitor.id == monitor_id))
        monitor = result.scalar_one()
        monitor.current_status = "down"
        await db.commit()

    response = await authenticated_client.get("/s/test-company")
    assert response.status_code == 200
    assert "Disruption" in response.text


@pytest.mark.asyncio
async def test_private_monitors_not_shown(authenticated_client: AsyncClient):
    """Test that private monitors don't appear on the public status page."""
    await authenticated_client.post("/api/monitors", json={
        **MONITOR_DATA,
        "name": "Public API",
        "is_public": True,
    })
    await authenticated_client.post("/api/monitors", json={
        **MONITOR_DATA,
        "name": "Secret Service",
        "url": "https://secret.example.com",
        "is_public": False,
    })

    response = await authenticated_client.get("/s/test-company")
    assert response.status_code == 200
    assert "Public API" in response.text
    assert "Secret Service" not in response.text


@pytest.mark.asyncio
async def test_public_status_api(authenticated_client: AsyncClient):
    """Test the JSON API endpoint for the public status page."""
    await authenticated_client.post("/api/monitors", json=MONITOR_DATA)

    response = await authenticated_client.get("/s/test-company/api")
    assert response.status_code == 200
    data = response.json()
    assert "title" in data
    assert "overall_status" in data
    assert "monitors" in data
    assert len(data["monitors"]) == 1
    assert data["monitors"][0]["name"] == "API Server"


@pytest.mark.asyncio
async def test_status_page_with_incidents(authenticated_client: AsyncClient):
    """Test that incidents appear on the status page."""
    res = await authenticated_client.post("/api/monitors", json=MONITOR_DATA)
    monitor_id = res.json()["id"]

    # Create an incident
    async with test_session_factory() as db:
        incident = Incident(
            monitor_id=monitor_id,
            title="API Server is down",
            status="resolved",
            started_at=datetime.now(timezone.utc) - timedelta(hours=2),
            resolved_at=datetime.now(timezone.utc) - timedelta(hours=1),
            error_message="Connection refused",
        )
        db.add(incident)
        await db.commit()

    response = await authenticated_client.get("/s/test-company")
    assert response.status_code == 200
    assert "API Server is down" in response.text
    assert "Resolved" in response.text


@pytest.mark.asyncio
async def test_check_results_api(authenticated_client: AsyncClient):
    """Test the check results API endpoint."""
    res = await authenticated_client.post("/api/monitors", json=MONITOR_DATA)
    monitor_id = res.json()["id"]

    # Insert a check result
    async with test_session_factory() as db:
        cr = CheckResult(
            monitor_id=monitor_id,
            status_code=200,
            response_time_ms=150,
            status="up",
            checked_at=datetime.now(timezone.utc),
        )
        db.add(cr)
        await db.commit()

    response = await authenticated_client.get(f"/api/monitors/{monitor_id}/results")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "up"
    assert data[0]["response_time_ms"] == 150


@pytest.mark.asyncio
async def test_uptime_stats_api(authenticated_client: AsyncClient):
    """Test the uptime stats API endpoint."""
    res = await authenticated_client.post("/api/monitors", json=MONITOR_DATA)
    monitor_id = res.json()["id"]

    # Insert some check results
    async with test_session_factory() as db:
        now = datetime.now(timezone.utc)
        for i in range(10):
            cr = CheckResult(
                monitor_id=monitor_id,
                status_code=200,
                response_time_ms=100 + i * 10,
                status="up",
                checked_at=now - timedelta(minutes=i * 5),
            )
            db.add(cr)
        # Add one failure
        cr_fail = CheckResult(
            monitor_id=monitor_id,
            status_code=500,
            response_time_ms=None,
            status="down",
            error_message="Server error",
            checked_at=now - timedelta(minutes=55),
        )
        db.add(cr_fail)
        await db.commit()

    response = await authenticated_client.get(f"/api/monitors/{monitor_id}/uptime")
    assert response.status_code == 200
    data = response.json()
    assert "uptime" in data
    assert "24h" in data["uptime"]
    assert data["uptime"]["24h"] > 0
    assert data["avg_response_time_ms"] is not None


@pytest.mark.asyncio
async def test_uptime_stats_unauthenticated(client: AsyncClient):
    """Test that uptime stats requires auth."""
    response = await client.get("/api/monitors/some-id/uptime")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_check_results_unauthenticated(client: AsyncClient):
    """Test that check results require auth."""
    response = await client.get("/api/monitors/some-id/results")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_monitor_detail_page_requires_auth(client: AsyncClient):
    """Test that monitor detail page redirects unauthenticated users."""
    response = await client.get("/monitors/some-id", follow_redirects=False)
    assert response.status_code == 303
    assert "/login" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_monitor_detail_page_authenticated(authenticated_client: AsyncClient):
    """Test that monitor detail page loads for authenticated users."""
    res = await authenticated_client.post("/api/monitors", json=MONITOR_DATA)
    monitor_id = res.json()["id"]

    response = await authenticated_client.get(f"/monitors/{monitor_id}")
    assert response.status_code == 200
    assert "Monitor Detail" in response.text or "monitor_detail" in response.text.lower() or monitor_id in response.text


@pytest.mark.asyncio
async def test_status_page_no_incidents_message(authenticated_client: AsyncClient):
    """Test that status page shows 'no incidents' message when there are none."""
    await authenticated_client.post("/api/monitors", json=MONITOR_DATA)

    response = await authenticated_client.get("/s/test-company")
    assert response.status_code == 200
    assert "No incidents" in response.text


@pytest.mark.asyncio
async def test_public_status_api_not_found(client: AsyncClient):
    """Test 404 for JSON API with non-existent slug."""
    response = await client.get("/s/nonexistent-slug/api")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_status_page_no_monitors(authenticated_client: AsyncClient):
    """Test status page renders properly with zero monitors."""
    response = await authenticated_client.get("/s/test-company")
    assert response.status_code == 200
    assert "No monitors" in response.text


@pytest.mark.asyncio
async def test_uptime_stats_with_no_results(authenticated_client: AsyncClient):
    """Test uptime stats returns zero/null when no check results exist."""
    res = await authenticated_client.post("/api/monitors", json=MONITOR_DATA)
    monitor_id = res.json()["id"]

    response = await authenticated_client.get(f"/api/monitors/{monitor_id}/uptime")
    assert response.status_code == 200
    data = response.json()
    assert data["uptime"]["24h"] == 0
    assert data["avg_response_time_ms"] is None
    assert data["total_incidents"] == 0
