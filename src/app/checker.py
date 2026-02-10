"""
Uptime check engine — performs HTTP checks, stores results, detects incidents, sends alerts.
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session_factory
from app.models.check_result import CheckResult
from app.models.incident import Incident
from app.models.monitor import Monitor
from app.models.user import User
from app.plans import get_plan_limits

logger = logging.getLogger("statusping.checker")
settings = get_settings()


async def perform_check(monitor_id: str) -> None:
    """Perform a single uptime check for a monitor."""
    async with get_session_factory()() as db:
        result = await db.execute(select(Monitor).where(Monitor.id == monitor_id))
        monitor = result.scalar_one_or_none()
        if not monitor or not monitor.is_active:
            return

        check_status = "up"
        status_code = None
        response_time_ms = None
        error_message = None

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=httpx.Timeout(monitor.timeout, connect=10),
                verify=True,
            ) as client:
                start = time.monotonic()
                response = await client.request(monitor.method, monitor.url)
                elapsed = time.monotonic() - start

                status_code = response.status_code
                response_time_ms = int(elapsed * 1000)

                if status_code != monitor.expected_status_code:
                    check_status = "down"
                    error_message = (
                        f"Expected status {monitor.expected_status_code}, "
                        f"got {status_code}"
                    )
        except httpx.TimeoutException:
            check_status = "down"
            error_message = f"Request timed out after {monitor.timeout}s"
        except httpx.ConnectError as e:
            check_status = "down"
            error_message = f"Connection failed: {str(e)[:200]}"
        except httpx.RequestError as e:
            check_status = "down"
            error_message = f"Request error: {str(e)[:200]}"
        except Exception as e:
            check_status = "down"
            error_message = f"Unexpected error: {str(e)[:200]}"

        # Store check result
        check_result = CheckResult(
            monitor_id=monitor.id,
            status_code=status_code,
            response_time_ms=response_time_ms,
            status=check_status,
            error_message=error_message,
            checked_at=datetime.now(timezone.utc),
        )
        db.add(check_result)

        # Update monitor status
        now = datetime.now(timezone.utc)
        monitor.last_checked_at = now

        previous_status = monitor.current_status

        if check_status == "down":
            monitor.consecutive_failures += 1
            # Only mark as down after threshold consecutive failures
            if monitor.consecutive_failures >= settings.consecutive_failures_threshold:
                monitor.current_status = "down"
        else:
            monitor.consecutive_failures = 0
            monitor.current_status = "up"

        await db.commit()

        # Handle incident detection and alerts
        await _handle_status_transition(
            db, monitor, previous_status, monitor.current_status, error_message
        )


async def _handle_status_transition(
    db: AsyncSession,
    monitor: Monitor,
    previous_status: str,
    new_status: str,
    error_message: str | None,
) -> None:
    """Detect state transitions and create/resolve incidents."""
    # Only act on actual transitions (not unknown -> up on first check)
    if previous_status == new_status:
        return

    if previous_status == "up" and new_status == "down":
        # Create new incident
        incident = Incident(
            monitor_id=monitor.id,
            title=f"{monitor.name} is down",
            status="ongoing",
            started_at=datetime.now(timezone.utc),
            error_message=error_message,
        )
        db.add(incident)
        await db.commit()
        logger.warning(f"INCIDENT: {monitor.name} ({monitor.url}) is DOWN - {error_message}")

        # Send alert
        await _send_down_alert(db, monitor, error_message)

    elif previous_status == "down" and new_status == "up":
        # Resolve ongoing incidents
        result = await db.execute(
            select(Incident).where(
                Incident.monitor_id == monitor.id,
                Incident.status == "ongoing",
            )
        )
        ongoing_incidents = result.scalars().all()
        now = datetime.now(timezone.utc)
        for incident in ongoing_incidents:
            incident.status = "resolved"
            incident.resolved_at = now
        await db.commit()

        if ongoing_incidents:
            started = ongoing_incidents[0].started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            duration = now - started
            logger.info(
                f"RESOLVED: {monitor.name} ({monitor.url}) is back UP "
                f"after {_format_duration(duration)}"
            )
            await _send_recovery_alert(db, monitor, duration)


async def _send_down_alert(
    db: AsyncSession, monitor: Monitor, error_message: str | None
) -> None:
    """Send an email alert when a monitor goes down."""
    result = await db.execute(select(User).where(User.id == monitor.user_id))
    user = result.scalar_one_or_none()
    if not user:
        return

    plan_limits = get_plan_limits(user.plan)
    if "email_alerts" not in plan_limits["features"]:
        return

    # Log the alert (actual SMTP sending requires configured server)
    logger.info(
        f"ALERT -> {user.email}: {monitor.name} is DOWN. "
        f"Error: {error_message or 'Unknown'}"
    )

    # Only attempt SMTP if credentials are configured
    if settings.smtp_username and settings.smtp_password:
        try:
            import aiosmtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[StatusPing] {monitor.name} is DOWN"
            msg["From"] = settings.smtp_from_email
            msg["To"] = user.email

            text_body = (
                f"Your monitor '{monitor.name}' is currently down.\n\n"
                f"URL: {monitor.url}\n"
                f"Error: {error_message or 'Unknown'}\n"
                f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
                f"We'll notify you when it recovers.\n\n"
                f"— StatusPing"
            )

            html_body = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: #ef4444; color: white; padding: 20px 24px; border-radius: 12px 12px 0 0;">
                    <h2 style="margin: 0; font-size: 18px;">Monitor Down</h2>
                </div>
                <div style="background: white; padding: 24px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                    <p style="margin: 0 0 16px; font-size: 15px; color: #374151;">
                        Your monitor <strong>{monitor.name}</strong> is currently <span style="color: #ef4444; font-weight: 600;">down</span>.
                    </p>
                    <table style="width: 100%; border-collapse: collapse; margin-bottom: 16px;">
                        <tr><td style="padding: 8px 0; color: #6b7280; font-size: 14px;">URL</td><td style="padding: 8px 0; font-size: 14px;">{monitor.url}</td></tr>
                        <tr><td style="padding: 8px 0; color: #6b7280; font-size: 14px;">Error</td><td style="padding: 8px 0; font-size: 14px; color: #ef4444;">{error_message or 'Unknown'}</td></tr>
                        <tr><td style="padding: 8px 0; color: #6b7280; font-size: 14px;">Time</td><td style="padding: 8px 0; font-size: 14px;">{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</td></tr>
                    </table>
                    <p style="margin: 0; font-size: 13px; color: #9ca3af;">We'll notify you when it recovers.</p>
                </div>
            </div>
            """

            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_username,
                password=settings.smtp_password,
                use_tls=settings.smtp_use_tls,
            )
            logger.info(f"Email alert sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send email alert to {user.email}: {e}")


async def _send_recovery_alert(
    db: AsyncSession, monitor: Monitor, duration: timedelta
) -> None:
    """Send an email alert when a monitor recovers."""
    result = await db.execute(select(User).where(User.id == monitor.user_id))
    user = result.scalar_one_or_none()
    if not user:
        return

    plan_limits = get_plan_limits(user.plan)
    if "email_alerts" not in plan_limits["features"]:
        return

    logger.info(
        f"RECOVERY -> {user.email}: {monitor.name} is back UP "
        f"after {_format_duration(duration)}"
    )

    if settings.smtp_username and settings.smtp_password:
        try:
            import aiosmtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[StatusPing] {monitor.name} is back UP"
            msg["From"] = settings.smtp_from_email
            msg["To"] = user.email

            text_body = (
                f"Your monitor '{monitor.name}' has recovered.\n\n"
                f"URL: {monitor.url}\n"
                f"Downtime: {_format_duration(duration)}\n"
                f"Recovered at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
                f"— StatusPing"
            )

            html_body = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: #10b981; color: white; padding: 20px 24px; border-radius: 12px 12px 0 0;">
                    <h2 style="margin: 0; font-size: 18px;">Monitor Recovered</h2>
                </div>
                <div style="background: white; padding: 24px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                    <p style="margin: 0 0 16px; font-size: 15px; color: #374151;">
                        Your monitor <strong>{monitor.name}</strong> is back <span style="color: #10b981; font-weight: 600;">online</span>.
                    </p>
                    <table style="width: 100%; border-collapse: collapse; margin-bottom: 16px;">
                        <tr><td style="padding: 8px 0; color: #6b7280; font-size: 14px;">URL</td><td style="padding: 8px 0; font-size: 14px;">{monitor.url}</td></tr>
                        <tr><td style="padding: 8px 0; color: #6b7280; font-size: 14px;">Downtime</td><td style="padding: 8px 0; font-size: 14px;">{_format_duration(duration)}</td></tr>
                        <tr><td style="padding: 8px 0; color: #6b7280; font-size: 14px;">Recovered</td><td style="padding: 8px 0; font-size: 14px;">{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</td></tr>
                    </table>
                </div>
            </div>
            """

            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_username,
                password=settings.smtp_password,
                use_tls=settings.smtp_use_tls,
            )
            logger.info(f"Recovery email sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send recovery email to {user.email}: {e}")


async def prune_old_results() -> None:
    """Delete check results older than the plan's retention period."""
    async with get_session_factory()() as db:
        # Get all users with their plans
        result = await db.execute(select(User))
        users = result.scalars().all()

        for user in users:
            limits = get_plan_limits(user.plan)
            retention_hours = limits["retention_hours"]
            cutoff = datetime.now(timezone.utc) - timedelta(hours=retention_hours)

            # Get monitor IDs for this user
            monitor_result = await db.execute(
                select(Monitor.id).where(Monitor.user_id == user.id)
            )
            monitor_ids = [m for m in monitor_result.scalars().all()]

            if monitor_ids:
                await db.execute(
                    delete(CheckResult).where(
                        CheckResult.monitor_id.in_(monitor_ids),
                        CheckResult.checked_at < cutoff,
                    )
                )

        await db.commit()
        logger.info("Pruned old check results based on plan retention")


def _format_duration(delta: timedelta) -> str:
    """Format a timedelta as a human-readable string."""
    total_seconds = int(delta.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        return f"{minutes}m"
    elif total_seconds < 86400:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    else:
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        return f"{days}d {hours}h" if hours else f"{days}d"
