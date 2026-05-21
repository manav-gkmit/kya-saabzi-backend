"""Asynchronous household management HTTP endpoints for V2 API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_async_db
from app.models.households import Household
from app.models.users import User
from app.schemas.households import HouseholdJoin, HouseholdRead, HouseholdUpdate
from app.schemas.users import UserRead
from app.services.household_async import (
    cleanup_empty_household_async,
    create_private_household_async,
    reassign_admin_if_needed_async,
    update_household_preferences_async,
)
from app.utils.auth import get_current_household_async, get_current_user_async
from app.utils.rate_limit import get_user_id_or_ip, limiter

router = APIRouter(prefix="/households", tags=["households"])


@router.get("/me", response_model=HouseholdRead)
async def get_my_household(
    household_id: UUID = Depends(get_current_household_async),
    db: AsyncSession = Depends(get_async_db),
):
    """Fetch preferences and data for the user's current household asynchronously."""
    household = await db.get(Household, household_id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")
    return household


@router.patch("/me", response_model=HouseholdRead)
async def update_my_household(
    update_data: HouseholdUpdate,
    user: User = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
):
    """Update household name and/or preferences asynchronously (admin only)."""
    household = await db.get(Household, user.household_id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")

    if household.admin_id and household.admin_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the household admin can update these settings.",
        )

    prefs = (
        update_data.preferences.model_dump(exclude_unset=True) if update_data.preferences else None
    )
    await update_household_preferences_async(
        db, household, name=update_data.name, preferences_patch=prefs
    )
    await db.commit()
    await db.refresh(household)
    return household


@router.get("/me/members", response_model=list[UserRead])
async def get_household_members(
    household_id: UUID = Depends(get_current_household_async),
    db: AsyncSession = Depends(get_async_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List all users belonging to the current household asynchronously."""
    stmt = select(User).where(User.household_id == household_id).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/join", response_model=HouseholdRead)
@limiter.limit("3/minute")
async def join_household(
    request: Request,
    join_data: HouseholdJoin,
    user: User = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
):
    """Join an existing household using a short invite code asynchronously."""
    stmt = select(Household).where(Household.invite_code == join_data.invite_code)
    result = await db.execute(stmt)
    target = result.scalars().first()

    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household with this invite code not found.",
        )
    if user.household_id == target.id:
        return target

    old_household_id = user.household_id
    user.household_id = target.id
    await db.flush()

    await cleanup_empty_household_async(db, old_household_id)
    await db.commit()
    return target


@router.post("/leave", response_model=HouseholdRead)
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
async def leave_household(
    request: Request,
    user: User = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
):
    """Leave the current household; a new private household is created asynchronously."""
    old_household_id = user.household_id

    stmt = (
        select(func.count())
        .select_from(User)
        .where(User.household_id == old_household_id, User.id != user.id)
    )
    result = await db.execute(stmt)
    other_members = result.scalar() or 0

    if other_members == 0:
        return await db.get(Household, old_household_id)

    old_household = await db.get(Household, old_household_id)
    await reassign_admin_if_needed_async(db, old_household, user.id)

    new_household = await create_private_household_async(db, user)
    await db.commit()
    await db.refresh(new_household)
    return new_household


@router.delete("/me/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_household_member(
    member_id: UUID,
    user: User = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
):
    """Remove a member from the household asynchronously (admin only)."""
    household = await db.get(Household, user.household_id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")

    if household.admin_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only the admin can remove members."
        )

    if member_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Use the /leave endpoint instead."
        )

    stmt = select(User).where(User.id == member_id, User.household_id == household.id)
    result = await db.execute(stmt)
    member = result.scalars().first()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found in your household")

    await create_private_household_async(db, member)
    await db.commit()
