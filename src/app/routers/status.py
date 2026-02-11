from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.check_result import CheckResult
from app.models.incident import Incident
from app.models.monitor import Monitor
from app.models.status_page import StatusPage
from app.models.user import User

router = APIRouter(prefix="/s", tags=["status-pages"])
templates = Jinja2Templates(directory="src/app/templates")


@router.get("/{slug}", response_class=HTMLResponse)
async def public_status_page(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Find user by slug
    result = await db.execute(select(User).where(User.account_slug == slug))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Status page not found")

    # Get status page config
    sp_result = await db.execute(
        select(StatusPage).where(StatusPage.user_id == user.id)
    )
    status_page = sp_result.scalar_one_or_none()
    if not status_page or not status_page.is_public:
        raise HTTPException(status_code=404, detail="Status page not found")

    # Get public monitors
    monitor_result = await db.execute(
        select(Monitor)
        .where(Monitor.user_id == user.id, Monitor.is_public == True)  # noqa: E712
        .order_by(Monitor.name)
    )
    monitors = monitor_result.scalars().all()

    now = datetime.now(timezone.utc)

    # Build monitor data with uptime info
    monitors_data = []
    for monitor in monitors:
        # Calculate 24h uptime
        cutoff_24h = now - timedelta(hours=24)
        total_result = await db.execute(
            select(func.count(CheckResult.id)).where(
                CheckResult.monitor_id == monitor.id,
                CheckResult.checked_at >= cutoff_24h,
            )
        )
        total = total_result.scalar() or 0

        up_result = await db.execute(
            select(func.count(CheckResult.id)).where(
                CheckResult.monitor_id == monitor.id,
                CheckResult.checked_at >= cutoff_24h,
                CheckResult.status == "up",
            )
        )
        up_count = up_result.scalar() or 0
        uptime_24h = round((up_count / total * 100) if total > 0 else 100, 2)

        # Get uptime bars data (last 90 days, grouped by day) — single query
        cutoff_90d = (now - timedelta(days=90)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        date_expr = func.date(CheckResult.checked_at)
        bar_result = await db.execute(
            select(
                date_expr.label("day"),
                func.count(CheckResult.id).label("total"),
                func.sum(
                    case((CheckResult.status == "up", 1), else_=0)
                ).label("up_count"),
            )
            .where(
                CheckResult.monitor_id == monitor.id,
                CheckResult.checked_at >= cutoff_90d,
            )
            .group_by(date_expr)
        )
        day_stats = {row.day: (row.total, row.up_count) for row in bar_result}

        uptime_bars = []
        for i in range(89, -1, -1):
            day_start = (now - timedelta(days=i)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            day_key = day_start.strftime("%Y-%m-%d")
            if day_key in day_stats:
                total, up_count = day_stats[day_key]
                pct = round((up_count / total * 100), 1) if total > 0 else None
                uptime_bars.append({"date": day_start.strftime("%b %d"), "pct": pct})
            else:
                uptime_bars.append({"date": day_start.strftime("%b %d"), "pct": None})

        # Get latest response time
        latest_result = await db.execute(
            select(CheckResult)
            .where(
                CheckResult.monitor_id == monitor.id,
                CheckResult.response_time_ms.isnot(None),
            )
            .order_by(CheckResult.checked_at.desc())
            .limit(1)
        )
        latest = latest_result.scalar_one_or_none()
        response_time = latest.response_time_ms if latest else None

        monitors_data.append({
            "name": monitor.name,
            "url": monitor.url,
            "status": monitor.current_status,
            "uptime_24h": uptime_24h,
            "response_time_ms": response_time,
            "uptime_bars": uptime_bars,
        })

    # Overall status
    all_up = all(m["status"] == "up" for m in monitors_data) if monitors_data else True
    any_down = any(m["status"] == "down" for m in monitors_data) if monitors_data else False
    overall_status = "down" if any_down else ("up" if all_up else "degraded")

    # Recent incidents (last 30 days)
    cutoff_30d = now - timedelta(days=30)
    monitor_ids = [m.id for m in monitors if m.is_public]
    recent_incidents = []
    if monitor_ids:
        incident_result = await db.execute(
            select(Incident)
            .join(Monitor)
            .where(
                Incident.monitor_id.in_(monitor_ids),
                Incident.started_at >= cutoff_30d,
            )
            .order_by(Incident.started_at.desc())
            .limit(20)
        )
        incidents = incident_result.scalars().all()

        for inc in incidents:
            # Get monitor name
            mon_result = await db.execute(
                select(Monitor.name).where(Monitor.id == inc.monitor_id)
            )
            mon_name = mon_result.scalar() or "Unknown"

            duration = None
            if inc.resolved_at:
                delta = inc.resolved_at - inc.started_at
                total_secs = int(delta.total_seconds())
                if total_secs < 60:
                    duration = f"{total_secs}s"
                elif total_secs < 3600:
                    duration = f"{total_secs // 60}m"
                else:
                    duration = f"{total_secs // 3600}h {(total_secs % 3600) // 60}m"

            recent_incidents.append({
                "monitor_name": mon_name,
                "title": inc.title,
                "status": inc.status,
                "started_at": inc.started_at,
                "resolved_at": inc.resolved_at,
                "duration": duration,
                "error_message": inc.error_message,
            })

    return templates.TemplateResponse(request, "status_page.html", {
        "status_page": status_page,
        "user": user,
        "monitors": monitors_data,
        "overall_status": overall_status,
        "incidents": recent_incidents,
        "now": now,
    })


@router.get("/{slug}/api")
async def public_status_api(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """JSON API for public status page data."""
    result = await db.execute(select(User).where(User.account_slug == slug))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Status page not found")

    sp_result = await db.execute(
        select(StatusPage).where(StatusPage.user_id == user.id)
    )
    status_page = sp_result.scalar_one_or_none()
    if not status_page or not status_page.is_public:
        raise HTTPException(status_code=404, detail="Status page not found")

    monitor_result = await db.execute(
        select(Monitor)
        .where(Monitor.user_id == user.id, Monitor.is_public == True)  # noqa: E712
        .order_by(Monitor.name)
    )
    monitors = monitor_result.scalars().all()

    now = datetime.now(timezone.utc)
    monitors_data = []
    for monitor in monitors:
        cutoff = now - timedelta(hours=24)
        total_result = await db.execute(
            select(func.count(CheckResult.id)).where(
                CheckResult.monitor_id == monitor.id,
                CheckResult.checked_at >= cutoff,
            )
        )
        total = total_result.scalar() or 0

        up_result = await db.execute(
            select(func.count(CheckResult.id)).where(
                CheckResult.monitor_id == monitor.id,
                CheckResult.checked_at >= cutoff,
                CheckResult.status == "up",
            )
        )
        up_count = up_result.scalar() or 0
        uptime = round((up_count / total * 100) if total > 0 else 100, 2)

        monitors_data.append({
            "name": monitor.name,
            "status": monitor.current_status,
            "uptime_24h": uptime,
        })

    all_up = all(m["status"] == "up" for m in monitors_data) if monitors_data else True
    any_down = any(m["status"] == "down" for m in monitors_data) if monitors_data else False

    return {
        "title": status_page.title,
        "overall_status": "down" if any_down else ("up" if all_up else "degraded"),
        "monitors": monitors_data,
    }
