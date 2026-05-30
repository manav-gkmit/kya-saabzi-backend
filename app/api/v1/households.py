"""V1 household routes — deprecated, internally async."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_db
from app.models.households import Household
from app.models.users import User
from app.schemas.households import HouseholdJoin, HouseholdRead, HouseholdUpdate
from app.schemas.users import UserRead
from app.services.household import (
    cleanup_empty_household,
    create_private_household,
    reassign_admin_if_needed,
    update_household_preferences,
)
from app.utils.auth import get_current_household, get_current_user
from app.utils.rate_limit import get_user_id_or_ip, limiter

router = APIRouter(prefix="/households", tags=["households"])


@router.get("/me", response_model=HouseholdRead)
async def get_my_household(
    household_id: UUID = Depends(get_current_household),
    db: AsyncSession = Depends(get_db),
):
    """Fetch preferences and data for the user's current household."""
    household = await db.get(Household, household_id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")
    return household


@router.patch("/me", response_model=HouseholdRead)
async def update_my_household(
    update_data: HouseholdUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update household name and/or preferences (admin only)."""
    household = await db.get(Household, user.household_id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")

    if household.admin_id and household.admin_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the household admin can update these settings.",
        )

    prefs_patch = None
    if update_data.preferences:
        prefs_patch = update_data.preferences.model_dump(exclude_unset=True)

    await update_household_preferences(
        db,
        household,
        name=update_data.name,
        preferences_patch=prefs_patch,
    )

    await db.commit()
    await db.refresh(household)

    return household


@router.get("/me/members", response_model=list[UserRead])
async def get_household_members(
    household_id: UUID = Depends(get_current_household),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List all users belonging to the current household."""
    stmt = select(User).where(User.household_id == household_id).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/join", response_model=HouseholdRead)
@limiter.limit("3/minute")
async def join_household(
    request: Request,
    join_data: HouseholdJoin,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Join an existing household using a short invite code."""
    result = await db.execute(
        select(Household).where(Household.invite_code == join_data.invite_code)
    )
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

    await cleanup_empty_household(db, old_household_id)
    await db.commit()
    return target


@router.post("/leave", response_model=HouseholdRead)
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
async def leave_household(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Leave the current household; a new private household is created."""
    old_household_id = user.household_id

    stmt = select(User).where(User.household_id == old_household_id, User.id != user.id)
    result = await db.execute(stmt)
    other_members = result.scalars().all()
    if not other_members:
        return await db.get(Household, old_household_id)

    old_household = await db.get(Household, old_household_id)
    await reassign_admin_if_needed(db, old_household, user.id)  # type: ignore[arg-type]

    new_household = await create_private_household(db, user)

    await db.commit()
    await db.refresh(new_household)
    return new_household


@router.delete("/me/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_household_member(
    member_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a member from the household (admin only)."""
    household = await db.get(Household, user.household_id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")

    if household.admin_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the household admin can remove members.",
        )

    if member_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot remove yourself. Use the /leave endpoint instead.",
        )

    stmt = select(User).where(User.id == member_id, User.household_id == household.id)
    result = await db.execute(stmt)
    member = result.scalars().first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in your household")

    await create_private_household(db, member)
    await db.commit()
    return
