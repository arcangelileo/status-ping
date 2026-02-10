from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_api
from app.database import get_db
from app.models.monitor import Monitor
from app.models.user import User
from app.plans import get_plan_limits
from app.schemas import MonitorCreate, MonitorResponse, MonitorUpdate

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
    # Enforce plan limits
    limits = get_plan_limits(user.plan)

    # Count existing monitors
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

    # Enforce minimum check interval for plan
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

    # Enforce plan check interval limit
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
    await db.delete(monitor)
    await db.commit()
