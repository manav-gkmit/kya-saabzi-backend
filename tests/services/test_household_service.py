"""Tests for app.services.household — preferences, leave, admin, cleanup."""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.models.households import Household
from app.models.users import User
from app.services.household import (
    cleanup_empty_household,
    create_private_household,
    reassign_admin_if_needed,
    update_household_preferences,
)
from app.utils.security import get_password_hash


# ---------------------------------------------------------------------------
# update_household_preferences
# ---------------------------------------------------------------------------


class TestUpdateHouseholdPreferences:
    """Verify partial updates to household name and preferences."""

    def test_updates_name(
        self, db_session: Session, test_household: Household,
    ) -> None:
        update_household_preferences(db_session, test_household, name="New Name")
        db_session.commit()
        db_session.refresh(test_household)
        assert test_household.name == "New Name"

    def test_merges_preferences(
        self, db_session: Session, test_household: Household,
    ) -> None:
        test_household.preferences = {"is_vegetarian": False, "spice_level": "mild"}
        db_session.commit()

        update_household_preferences(
            db_session,
            test_household,
            preferences_patch={"is_vegetarian": True},
        )
        db_session.commit()
        db_session.refresh(test_household)

        assert test_household.preferences["is_vegetarian"] is True
        assert test_household.preferences["spice_level"] == "mild"

    def test_no_changes_is_noop(
        self, db_session: Session, test_household: Household,
    ) -> None:
        old_name = test_household.name
        update_household_preferences(db_session, test_household)
        db_session.commit()
        db_session.refresh(test_household)
        assert test_household.name == old_name

    def test_null_preferences_initialised(
        self, db_session: Session, test_household: Household,
    ) -> None:
        test_household.preferences = None
        db_session.commit()

        update_household_preferences(
            db_session,
            test_household,
            preferences_patch={"is_vegetarian": True},
        )
        db_session.commit()
        db_session.refresh(test_household)

        assert test_household.preferences["is_vegetarian"] is True


# ---------------------------------------------------------------------------
# create_private_household
# ---------------------------------------------------------------------------


class TestCreatePrivateHousehold:
    """Verify private household creation for a leaving user."""

    def test_creates_household_and_reassigns_user(
        self, db_session: Session, test_user: User,
    ) -> None:
        old_hh_id = test_user.household_id
        new_hh = create_private_household(db_session, test_user)
        db_session.commit()

        assert new_hh.id != old_hh_id
        assert new_hh.admin_id == test_user.id
        assert test_user.household_id == new_hh.id
        assert test_user.username in new_hh.name


# ---------------------------------------------------------------------------
# reassign_admin_if_needed
# ---------------------------------------------------------------------------


class TestReassignAdminIfNeeded:
    """Verify admin promotion when the current admin leaves."""

    def test_admin_leaves_promotes_oldest_member(
        self, db_session: Session, test_household: Household,
        test_user: User, other_user: User,
    ) -> None:
        # test_user is admin (set in conftest)
        reassign_admin_if_needed(db_session, test_household, test_user.id)
        db_session.commit()
        db_session.refresh(test_household)

        assert test_household.admin_id == other_user.id

    def test_non_admin_leaves_no_change(
        self, db_session: Session, test_household: Household,
        test_user: User, other_user: User,
    ) -> None:
        original_admin = test_household.admin_id
        reassign_admin_if_needed(db_session, test_household, other_user.id)
        db_session.commit()
        db_session.refresh(test_household)

        assert test_household.admin_id == original_admin


# ---------------------------------------------------------------------------
# cleanup_empty_household
# ---------------------------------------------------------------------------


class TestCleanupEmptyHousehold:
    """Verify orphan household deletion."""

    def test_deletes_empty_household(self, db_session: Session) -> None:
        empty = Household(name="Ghost House")
        db_session.add(empty)
        db_session.commit()
        hh_id = empty.id

        cleanup_empty_household(db_session, hh_id)
        db_session.commit()

        assert db_session.get(Household, hh_id) is None

    def test_keeps_household_with_members(
        self, db_session: Session, test_household: Household, test_user: User,
    ) -> None:
        cleanup_empty_household(db_session, test_household.id)
        db_session.commit()

        assert db_session.get(Household, test_household.id) is not None
