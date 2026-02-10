from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_api
from app.database import get_db
from app.models.check_result import CheckResult
from app.models.incident import Incident
from app.models.monitor import Monitor
from app.models.user import User
from app.plans import get_plan_limits
from app.schemas import CheckResultResponse, MonitorCreate, MonitorResponse, MonitorUpdate

router = APIRouter(prefix="/api/monitors", tags=["monitors"])


@router.get("", response_model=list[MonitorResponse])
async def list_monitors(
    user: User = Depends(get_current_user_api),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Monitor)
        .where(Monitor.user_id == user.id)
        .order_by(Monitor.created_at.desc())
    )
    monitors = result.scalars().all()
    return [MonitorResponse.model_validate(m) for m in monitors]


@router.post("", response_model=MonitorResponse, status_code=201)
async def create_monitor(
    body: MonitorCreate,
    user: User = Depends(get_current_user_api),
    db: AsyncSession = Depends(get_db),
):
    limits = get_plan_limits(user.plan)

    count_result = await db.execute(
        select(func.count(Monitor.id)).where(Monitor.user_id == user.id)
    )
    monitor_count = count_result.scalar()

    if monitor_count >= limits["max_monitors"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Your {user.plan} plan allows up to {limits['max_monitors']} monitors. "
            f"Upgrade your plan to add more.",
        )

    if body.check_interval < limits["min_check_interval"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Your {user.plan} plan requires a minimum check interval of "
            f"{limits['min_check_interval']} seconds. Upgrade your plan for faster checks.",
        )

    monitor = Monitor(
        user_id=user.id,
        name=body.name,
        url=body.url,
        method=body.method,
        check_interval=body.check_interval,
        timeout=body.timeout,
        expected_status_code=body.expected_status_code,
        is_public=body.is_public,
    )
    db.add(monitor)
    await db.commit()
    await db.refresh(monitor)

    # Schedule the monitor check
    try:
        from app.scheduler import schedule_monitor
        schedule_monitor(monitor.id, monitor.check_interval)
    except Exception:
        pass  # Scheduler may not be running (tests)

    return MonitorResponse.model_validate(monitor)


@router.get("/{monitor_id}", response_model=MonitorResponse)
async def get_monitor(
    monitor_id: str,
    user: User = Depends(get_current_user_api),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Monitor).where(Monitor.id == monitor_id, Monitor.user_id == user.id)
    )
    monitor = result.scalar_one_or_none()
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitor not found",
        )
    return MonitorResponse.model_validate(monitor)


@router.get("/{monitor_id}/results", response_model=list[CheckResultResponse])
async def get_check_results(
    monitor_id: str,
    hours: int = 24,
    limit: int = 100,
    user: User = Depends(get_current_user_api),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Monitor).where(Monitor.id == monitor_id, Monitor.user_id == user.id)
    )
    monitor = result.scalar_one_or_none()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    plan_limits = get_plan_limits(user.plan)
    hours = min(hours, plan_limits["retention_hours"])

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(CheckResult)
        .where(
            CheckResult.monitor_id == monitor_id,
            CheckResult.checked_at >= cutoff,
        )
        .order_by(CheckResult.checked_at.desc())
        .limit(limit)
    )
    results = result.scalars().all()
    return [CheckResultResponse.model_validate(r) for r in results]


@router.get("/{monitor_id}/uptime")
async def get_uptime_stats(
    monitor_id: str,
    user: User = Depends(get_current_user_api),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Monitor).where(Monitor.id == monitor_id, Monitor.user_id == user.id)
    )
    monitor = result.scalar_one_or_none()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    now = datetime.now(timezone.utc)
    periods = {
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
    }

    uptime = {}
    for label, delta in periods.items():
        cutoff = now - delta
        total_result = await db.execute(
            select(func.count(CheckResult.id)).where(
                CheckResult.monitor_id == monitor_id,
                CheckResult.checked_at >= cutoff,
            )
        )
        total = total_result.scalar() or 0

        up_result = await db.execute(
            select(func.count(CheckResult.id)).where(
                CheckResult.monitor_id == monitor_id,
                CheckResult.checked_at >= cutoff,
                CheckResult.status == "up",
            )
        )
        up_count = up_result.scalar() or 0

        uptime[label] = round((up_count / total * 100) if total > 0 else 0, 2)

    avg_result = await db.execute(
        select(func.avg(CheckResult.response_time_ms)).where(
            CheckResult.monitor_id == monitor_id,
            CheckResult.checked_at >= now - timedelta(hours=24),
            CheckResult.response_time_ms.isnot(None),
        )
    )
    avg_response = avg_result.scalar()

    incident_result = await db.execute(
        select(Incident)
        .where(Incident.monitor_id == monitor_id)
        .order_by(Incident.started_at.desc())
        .limit(10)
    )
    incidents = incident_result.scalars().all()

    return {
        "monitor_id": monitor_id,
        "uptime": uptime,
        "avg_response_time_ms": round(avg_response) if avg_response else None,
        "total_incidents": len(incidents),
        "incidents": [
            {
                "id": i.id,
                "title": i.title,
                "status": i.status,
                "started_at": i.started_at.isoformat(),
                "resolved_at": i.resolved_at.isoformat() if i.resolved_at else None,
                "error_message": i.error_message,
            }
            for i in incidents
        ],
    }


@router.patch("/{monitor_id}", response_model=MonitorResponse)
async def update_monitor(
    monitor_id: str,
    body: MonitorUpdate,
    user: User = Depends(get_current_user_api),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Monitor).where(Monitor.id == monitor_id, Monitor.user_id == user.id)
    )
    monitor = result.scalar_one_or_none()
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitor not found",
        )

    if body.check_interval is not None:
        limits = get_plan_limits(user.plan)
        if body.check_interval < limits["min_check_interval"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your {user.plan} plan requires a minimum check interval of "
                f"{limits['min_check_interval']} seconds.",
            )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(monitor, field, value)

    await db.commit()
    await db.refresh(monitor)

    # Update scheduler
    try:
        from app.scheduler import schedule_monitor, unschedule_monitor
        if monitor.is_active:
            schedule_monitor(monitor.id, monitor.check_interval)
        else:
            unschedule_monitor(monitor.id)
    except Exception:
        pass

    return MonitorResponse.model_validate(monitor)


@router.delete("/{monitor_id}", status_code=204)
async def delete_monitor(
    monitor_id: str,
    user: User = Depends(get_current_user_api),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Monitor).where(Monitor.id == monitor_id, Monitor.user_id == user.id)
    )
    monitor = result.scalar_one_or_none()
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitor not found",
        )

    try:
        from app.scheduler import unschedule_monitor
        unschedule_monitor(monitor.id)
    except Exception:
        pass

    await db.delete(monitor)
    await db.commit()
