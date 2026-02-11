"""Tests for the uptime check engine, incident detection, and result storage."""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.check_result import CheckResult
from app.models.incident import Incident
from app.models.monitor import Monitor

from tests.conftest import test_session_factory


MONITOR_DATA = {
    "name": "Test Site",
    "url": "https://httpbin.org/status/200",
    "method": "GET",
    "check_interval": 300,
    "timeout": 30,
    "expected_status_code": 200,
    "is_public": True,
}


async def create_monitor_and_get_id(client: AsyncClient) -> str:
    res = await client.post("/api/monitors", json=MONITOR_DATA)
    assert res.status_code == 201
    return res.json()["id"]


@pytest.mark.asyncio
async def test_perform_check_success(authenticated_client: AsyncClient):
    """Test that a successful HTTP check stores results and updates monitor status."""
    monitor_id = await create_monitor_and_get_id(authenticated_client)

    # Mock httpx to return a successful response
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("app.checker.httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        from app.checker import perform_check
        await perform_check(monitor_id)

    # Verify check result was stored
    async with test_session_factory() as db:
        result = await db.execute(
            select(CheckResult).where(CheckResult.monitor_id == monitor_id)
        )
        check = result.scalar_one_or_none()
        assert check is not None
        assert check.status == "up"
        assert check.status_code == 200
        assert check.response_time_ms is not None

        # Verify monitor status updated
        mon_result = await db.execute(select(Monitor).where(Monitor.id == monitor_id))
        monitor = mon_result.scalar_one()
        assert monitor.current_status == "up"
        assert monitor.consecutive_failures == 0
        assert monitor.last_checked_at is not None


@pytest.mark.asyncio
async def test_perform_check_failure(authenticated_client: AsyncClient):
    """Test that a failed HTTP check increments consecutive_failures."""
    monitor_id = await create_monitor_and_get_id(authenticated_client)

    mock_response = MagicMock()
    mock_response.status_code = 500

    with patch("app.checker.httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        from app.checker import perform_check
        await perform_check(monitor_id)

    async with test_session_factory() as db:
        result = await db.execute(
            select(CheckResult).where(CheckResult.monitor_id == monitor_id)
        )
        check = result.scalar_one()
        assert check.status == "down"
        assert check.error_message is not None

        mon_result = await db.execute(select(Monitor).where(Monitor.id == monitor_id))
        monitor = mon_result.scalar_one()
        assert monitor.consecutive_failures == 1
        # Should NOT be marked down yet (threshold is 3)
        assert monitor.current_status == "unknown"


@pytest.mark.asyncio
async def test_perform_check_timeout(authenticated_client: AsyncClient):
    """Test that a timeout is recorded as a failure."""
    monitor_id = await create_monitor_and_get_id(authenticated_client)

    import httpx as httpx_module

    with patch("app.checker.httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx_module.TimeoutException("timed out")
        )
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        from app.checker import perform_check
        await perform_check(monitor_id)

    async with test_session_factory() as db:
        result = await db.execute(
            select(CheckResult).where(CheckResult.monitor_id == monitor_id)
        )
        check = result.scalar_one()
        assert check.status == "down"
        assert "timed out" in check.error_message.lower()


@pytest.mark.asyncio
async def test_incident_created_after_threshold(authenticated_client: AsyncClient):
    """Test that an incident is created after consecutive_failures_threshold failures."""
    monitor_id = await create_monitor_and_get_id(authenticated_client)

    mock_200 = MagicMock()
    mock_200.status_code = 200
    mock_500 = MagicMock()
    mock_500.status_code = 500

    from app.checker import perform_check

    # First, establish "up" status so we get a proper up→down transition
    with patch("app.checker.httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_200)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance
        await perform_check(monitor_id)

    # Now run 3 failing checks (threshold)
    with patch("app.checker.httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_500)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        for _ in range(3):
            await perform_check(monitor_id)

    async with test_session_factory() as db:
        # Monitor should be "down" now
        mon_result = await db.execute(select(Monitor).where(Monitor.id == monitor_id))
        monitor = mon_result.scalar_one()
        assert monitor.current_status == "down"
        assert monitor.consecutive_failures == 3

        # Incident should exist
        inc_result = await db.execute(
            select(Incident).where(Incident.monitor_id == monitor_id)
        )
        incident = inc_result.scalar_one_or_none()
        assert incident is not None
        assert incident.status == "ongoing"
        assert "down" in incident.title.lower()


@pytest.mark.asyncio
async def test_incident_resolved_on_recovery(authenticated_client: AsyncClient):
    """Test that an incident is resolved when the monitor recovers."""
    monitor_id = await create_monitor_and_get_id(authenticated_client)

    mock_500 = MagicMock()
    mock_500.status_code = 500
    mock_200 = MagicMock()
    mock_200.status_code = 200

    from app.checker import perform_check

    # First, establish "up" status
    with patch("app.checker.httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_200)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance
        await perform_check(monitor_id)

    # Then make it go down (3 failures for up→down transition)
    with patch("app.checker.httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_500)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        for _ in range(3):
            await perform_check(monitor_id)

    # Then, make it recover
    with patch("app.checker.httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_200)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        await perform_check(monitor_id)

    async with test_session_factory() as db:
        # Monitor should be "up" now
        mon_result = await db.execute(select(Monitor).where(Monitor.id == monitor_id))
        monitor = mon_result.scalar_one()
        assert monitor.current_status == "up"
        assert monitor.consecutive_failures == 0

        # Incident should be resolved
        inc_result = await db.execute(
            select(Incident).where(Incident.monitor_id == monitor_id)
        )
        incident = inc_result.scalar_one()
        assert incident.status == "resolved"
        assert incident.resolved_at is not None


@pytest.mark.asyncio
async def test_inactive_monitor_not_checked(authenticated_client: AsyncClient):
    """Test that inactive monitors are not checked."""
    monitor_id = await create_monitor_and_get_id(authenticated_client)

    # Deactivate the monitor
    await authenticated_client.patch(f"/api/monitors/{monitor_id}", json={
        "is_active": False,
    })

    from app.checker import perform_check
    await perform_check(monitor_id)

    # No check result should exist
    async with test_session_factory() as db:
        result = await db.execute(
            select(CheckResult).where(CheckResult.monitor_id == monitor_id)
        )
        checks = result.scalars().all()
        assert len(checks) == 0


@pytest.mark.asyncio
async def test_prune_old_results(authenticated_client: AsyncClient):
    """Test that old check results are pruned based on plan retention."""
    monitor_id = await create_monitor_and_get_id(authenticated_client)

    # Insert old and new check results directly
    async with test_session_factory() as db:
        now = datetime.now(timezone.utc)

        # Recent result (should be kept)
        recent = CheckResult(
            monitor_id=monitor_id,
            status_code=200,
            response_time_ms=100,
            status="up",
            checked_at=now - timedelta(hours=1),
        )
        db.add(recent)

        # Old result (older than free plan's 24h retention)
        old = CheckResult(
            monitor_id=monitor_id,
            status_code=200,
            response_time_ms=100,
            status="up",
            checked_at=now - timedelta(hours=48),
        )
        db.add(old)
        await db.commit()

    from app.checker import prune_old_results
    await prune_old_results()

    async with test_session_factory() as db:
        result = await db.execute(
            select(CheckResult).where(CheckResult.monitor_id == monitor_id)
        )
        checks = result.scalars().all()
        assert len(checks) == 1  # Only the recent one should remain


@pytest.mark.asyncio
async def test_perform_check_connection_error(authenticated_client: AsyncClient):
    """Test that a connection error is recorded as a failure."""
    monitor_id = await create_monitor_and_get_id(authenticated_client)

    import httpx as httpx_module

    with patch("app.checker.httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx_module.ConnectError("Connection refused")
        )
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        from app.checker import perform_check
        await perform_check(monitor_id)

    async with test_session_factory() as db:
        result = await db.execute(
            select(CheckResult).where(CheckResult.monitor_id == monitor_id)
        )
        check = result.scalar_one()
        assert check.status == "down"
        assert "connection" in check.error_message.lower()
