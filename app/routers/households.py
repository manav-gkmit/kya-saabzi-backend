from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from uuid import UUID

from app.database.db import get_db
from app.models.households import Household
from app.schemas.households import HouseholdRead, HouseholdUpdate, HouseholdJoin
from app.util import get_current_user, get_current_household
from app.models.users import User
from app.schemas.users import UserRead
from app.utils.rate_limit import limiter

router = APIRouter(prefix="/households", tags=["households"])


@router.get("/me", response_model=HouseholdRead)
async def get_my_household(
    household_id: UUID = Depends(get_current_household),
    db: Session = Depends(get_db),
):
    """Fetch preferences and data for the user's current household."""
    household = db.get(Household, household_id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")
    return household


@router.patch("/me", response_model=HouseholdRead)
async def update_my_household(
    update_data: HouseholdUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update household preferences.
    Only the household Admin can rename it or change shared settings.
    """
    household = db.get(Household, user.household_id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")

    # Security check: Admin only
    if household.admin_id and household.admin_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the household admin can update these settings.",
        )

    if update_data.name:
        household.name = update_data.name

    if update_data.preferences:
        # Merge new preferences into existing ones
        current_prefs = household.preferences or {}
        new_prefs_dict = update_data.preferences.dict(exclude_unset=True)
        new_prefs = {**current_prefs, **new_prefs_dict}
        household.preferences = new_prefs

    db.commit()
    db.refresh(household)
    return household


@router.get("/me/members", response_model=List[UserRead])
async def get_household_members(
    household_id: UUID = Depends(get_current_household),
    db: Session = Depends(get_db),
):
    """List all users belonging to the current household."""
    members = db.query(User).filter(User.household_id == household_id).all()
    return members


@router.post("/join", response_model=HouseholdRead)
@limiter.limit("3/minute")
async def join_household(
    request: Request,
    join_data: HouseholdJoin,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Join an existing household using a short invite code."""
    invite_code = join_data.invite_code
    target_household = (
        db.query(Household).filter(Household.invite_code == invite_code).first()
    )

    if not target_household:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household with this invite code not found.",
        )

    if user.household_id == target_household.id:
        return target_household

    # Keep track of old household to potentially clean up
    old_household_id = user.household_id

    # Update user's household
    user.household_id = target_household.id
    db.commit()

    # Optional: Clean up old household if empty
    remaining_members = (
        db.query(User).filter(User.household_id == old_household_id).count()
    )
    if remaining_members == 0:
        old_household = db.get(Household, old_household_id)
        if old_household:
            db.delete(old_household)
            db.commit()

    return target_household


@router.post("/leave", response_model=HouseholdRead)
async def leave_household(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Leave the current household.
    A new private household will be created for the user.
    """
    old_household_id = user.household_id

    # Find other members in the current household
    other_members = (
        db.query(User)
        .filter(User.household_id == old_household_id, User.id != user.id)
        .order_by(User.created_at.asc())
        .all()
    )

    if not other_members:
        # User is already alone, just return current household
        return db.get(Household, old_household_id)

    # 1. Create a new household for the leaving user
    new_household = Household(name=f"{user.username}'s Home", admin_id=user.id)
    db.add(new_household)
    db.flush()

    # 2. Update user's household
    user.household_id = new_household.id

    # 3. Handle old household admin reassignment if the leaving user was the admin
    old_household = db.get(Household, old_household_id)
    if old_household and old_household.admin_id == user.id:
        # Reassign admin to the next oldest member
        old_household.admin_id = other_members[0].id

    db.commit()
    db.refresh(new_household)
    return new_household


@router.delete("/me/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_household_member(
    member_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Remove a member from the household. Only the admin can do this.
    The removed member will be moved to a new private household.
    """
    household = db.get(Household, user.household_id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")

    # Security check: Admin only
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

    # Find the member to remove
    member = (
        db.query(User)
        .filter(User.id == member_id, User.household_id == household.id)
        .first()
    )

    if not member:
        raise HTTPException(
            status_code=404, detail="Member not found in your household"
        )

    # 1. Create a new household for the removed member
    new_household = Household(name=f"{member.username}'s Home", admin_id=member.id)
    db.add(new_household)
    db.flush()

    # 2. Update member's household
    member.household_id = new_household.id

    db.commit()
    return
