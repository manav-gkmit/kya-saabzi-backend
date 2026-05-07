"""Tests for app.utils.security — bcrypt password hashing and verification."""

from __future__ import annotations

from app.utils.security import get_password_hash, verify_password


class TestGetPasswordHash:
    """Verify bcrypt hash generation."""

    def test_returns_bcrypt_hash(self) -> None:
        hashed = get_password_hash("mypassword")
        assert hashed.startswith("$2b$")

    def test_different_salts_each_call(self) -> None:
        h1 = get_password_hash("same")
        h2 = get_password_hash("same")
        assert h1 != h2  # different salts → different hashes

    def test_hash_is_string(self) -> None:
        hashed = get_password_hash("test")
        assert isinstance(hashed, str)


class TestVerifyPassword:
    """Verify password checking against bcrypt hashes."""

    def test_correct_password(self) -> None:
        hashed = get_password_hash("correct-horse-battery")
        assert verify_password("correct-horse-battery", hashed) is True

    def test_wrong_password(self) -> None:
        hashed = get_password_hash("correct")
        assert verify_password("wrong", hashed) is False

    def test_empty_password_returns_false(self) -> None:
        hashed = get_password_hash("something")
        assert verify_password("", hashed) is False

    def test_malformed_hash_returns_false(self) -> None:
        """Garbage hash should not crash — returns False."""
        assert verify_password("anything", "not-a-bcrypt-hash") is False

    def test_empty_hash_returns_false(self) -> None:
        assert verify_password("anything", "") is False
