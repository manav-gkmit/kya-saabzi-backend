"""Tests for app.services.household — preferences, leave, admin, cleanup."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.households import Household
from app.models.users import User
from app.services.household import (
    cleanup_empty_household,
    create_private_household,
    reassign_admin_if_needed,
    update_household_preferences,
)

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# update_household_preferences
# ---------------------------------------------------------------------------


class TestUpdateHouseholdPreferences:
    """Verify partial updates to household name and preferences."""

    async def test_updates_name(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        await update_household_preferences(async_db_session, async_test_household, name="New Name")
        await async_db_session.commit()
        await async_db_session.refresh(async_test_household)
        assert async_test_household.name == "New Name"

    async def test_merges_preferences(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        async_test_household.preferences = {"is_vegetarian": False, "spice_level": "mild"}
        await async_db_session.commit()

        await update_household_preferences(
            async_db_session,
            async_test_household,
            preferences_patch={"is_vegetarian": True},
        )
        await async_db_session.commit()
        await async_db_session.refresh(async_test_household)

        assert async_test_household.preferences["is_vegetarian"] is True
        assert async_test_household.preferences["spice_level"] == "mild"

    async def test_no_changes_is_noop(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        old_name = async_test_household.name
        await update_household_preferences(async_db_session, async_test_household)
        await async_db_session.commit()
        await async_db_session.refresh(async_test_household)
        assert async_test_household.name == old_name

    async def test_null_preferences_initialised(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        async_test_household.preferences = None
        await async_db_session.commit()

        await update_household_preferences(
            async_db_session,
            async_test_household,
            preferences_patch={"is_vegetarian": True},
        )
        await async_db_session.commit()
        await async_db_session.refresh(async_test_household)

        assert async_test_household.preferences["is_vegetarian"] is True


# ---------------------------------------------------------------------------
# create_private_household
# ---------------------------------------------------------------------------


class TestCreatePrivateHousehold:
    """Verify private household creation for a leaving user."""

    async def test_creates_household_and_reassigns_user(
        self,
        async_db_session: AsyncSession,
        async_test_user: User,
    ) -> None:
        old_hh_id = async_test_user.household_id
        new_hh = await create_private_household(async_db_session, async_test_user)
        await async_db_session.commit()

        assert new_hh.id != old_hh_id
        assert new_hh.admin_id == async_test_user.id
        assert async_test_user.household_id == new_hh.id
        assert async_test_user.username in new_hh.name


# ---------------------------------------------------------------------------
# reassign_admin_if_needed
# ---------------------------------------------------------------------------


class TestReassignAdminIfNeeded:
    """Verify admin promotion when the current admin leaves."""

    async def test_admin_leaves_promotes_oldest_member(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
        async_test_user: User,
    ) -> None:
        # Create other user async
        other_user = User(
            email="other@example.com",
            username="otheruser",
            hashed_password="password",
            household_id=async_test_household.id,
        )
        async_db_session.add(other_user)
        await async_db_session.commit()
        await async_db_session.refresh(other_user)

        # test_user is admin (set in conftest)
        await reassign_admin_if_needed(async_db_session, async_test_household, async_test_user.id)
        await async_db_session.commit()
        await async_db_session.refresh(async_test_household)

        assert async_test_household.admin_id == other_user.id

    async def test_non_admin_leaves_no_change(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
        async_test_user: User,
    ) -> None:
        # Create other user
        other_user = User(
            email="other2@example.com",
            username="otheruser2",
            hashed_password="password",
            household_id=async_test_household.id,
        )
        async_db_session.add(other_user)
        await async_db_session.commit()

        original_admin = async_test_household.admin_id
        await reassign_admin_if_needed(async_db_session, async_test_household, other_user.id)
        await async_db_session.commit()
        await async_db_session.refresh(async_test_household)

        assert async_test_household.admin_id == original_admin


# ---------------------------------------------------------------------------
# cleanup_empty_household
# ---------------------------------------------------------------------------


class TestCleanupEmptyHousehold:
    """Verify orphan household deletion."""

    async def test_deletes_empty_household(self, async_db_session: AsyncSession) -> None:
        empty = Household(name="Ghost House")
        async_db_session.add(empty)
        await async_db_session.commit()
        hh_id = empty.id

        await cleanup_empty_household(async_db_session, hh_id)
        await async_db_session.commit()

        assert await async_db_session.get(Household, hh_id) is None

    async def test_keeps_household_with_members(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
        async_test_user: User,
    ) -> None:
        await cleanup_empty_household(async_db_session, async_test_household.id)
        await async_db_session.commit()

        assert await async_db_session.get(Household, async_test_household.id) is not None
