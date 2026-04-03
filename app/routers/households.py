from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any, List

from app.database.db import get_db
from app.models.households import Household
from app.schemas.households import HouseholdRead, HouseholdUpdate, HouseholdJoin
from app.util import get_current_user, get_current_household
from app.models.users import User
from app.schemas.users import UserRead

router = APIRouter(prefix="/households", tags=["households"])


@router.get("/me", response_model=HouseholdRead)
async def get_my_household(
    household_id: str = Depends(get_current_household),
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
        new_prefs = {**current_prefs, **update_data.preferences}
        household.preferences = new_prefs

    db.commit()
    db.refresh(household)
    return household


@router.get("/me/members", response_model=List[UserRead])
async def get_household_members(
    household_id: str = Depends(get_current_household),
    db: Session = Depends(get_db),
):
    """List all users belonging to the current household."""
    members = db.query(User).filter(User.household_id == household_id).all()
    return members


@router.post("/join", response_model=HouseholdRead)
async def join_household(
    join_data: HouseholdJoin,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Join an existing household using a short invite code."""
    invite_code = join_data.invite_code.upper().strip()
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
    # Check if any other users are in the old household
    remaining_members = (
        db.query(User).filter(User.household_id == old_household_id).count()
    )
    if remaining_members == 0:
        old_household = db.get(Household, old_household_id)
        if old_household:
            db.delete(old_household)
            db.commit()

    return target_household
