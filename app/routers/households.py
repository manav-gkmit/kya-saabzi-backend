from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.database.db import get_db
from app.models.households import Household
from app.schemas.households import HouseholdRead, HouseholdUpdate
from app.util import get_current_user, get_current_household
from app.models.users import User

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
    household_id: str = Depends(get_current_household),
    db: Session = Depends(get_db),
):
    """Update household preferences (e.g. is_vegetarian, spice_level)."""
    household = db.get(Household, household_id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")
    
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
