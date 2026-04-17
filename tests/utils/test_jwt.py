"""Tests for app.utils.jwt — access token creation and decoding (PyJWT)."""
from __future__ import annotations

import time
from datetime import timedelta

import jwt as pyjwt
import pytest

from app.config import settings
from app.utils.jwt import create_access_token, decode_access_token


class TestCreateAccessToken:
    """Verify JWT creation with various options."""

    def test_returns_string(self) -> None:
        token = create_access_token(subject="user-123")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_payload_contains_sub_iat_exp(self) -> None:
        token = create_access_token(subject="user-123")
        payload = pyjwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
        )
        assert payload["sub"] == "user-123"
        assert "iat" in payload
        assert "exp" in payload

    def test_custom_expires_delta(self) -> None:
        delta = timedelta(minutes=5)
        token = create_access_token(subject="u", expires_delta=delta)
        payload = pyjwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
        )
        # exp - iat should be ~300 seconds
        assert abs((payload["exp"] - payload["iat"]) - 300) < 2

    def test_include_jti_adds_claim(self) -> None:
        token = create_access_token(subject="u", include_jti=True)
        payload = pyjwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
        )
        assert "jti" in payload
        assert len(payload["jti"]) > 0

    def test_no_jti_by_default(self) -> None:
        token = create_access_token(subject="u")
        payload = pyjwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
        )
        assert "jti" not in payload


class TestDecodeAccessToken:
    """Verify JWT decoding and error handling."""

    def test_valid_token(self) -> None:
        token = create_access_token(subject="user-456")
        payload = decode_access_token(token)
        assert payload["sub"] == "user-456"

    def test_expired_token_raises(self) -> None:
        token = create_access_token(
            subject="u",
            expires_delta=timedelta(seconds=-1),
        )
        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_access_token(token)

    def test_tampered_token_raises(self) -> None:
        token = create_access_token(subject="u")
        tampered = token[:-4] + "XXXX"
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_access_token(tampered)

    def test_garbage_string_raises(self) -> None:
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_access_token("not-a-jwt-at-all")

    def test_wrong_secret_raises(self) -> None:
        payload = {"sub": "u", "exp": int(time.time()) + 300}
        token = pyjwt.encode(payload, "wrong-secret", algorithm="HS256")
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_access_token(token)
