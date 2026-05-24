from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient


def test_v1_responses_include_migration_headers(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "bad"},
    )
    assert response.status_code == 401
    assert response.headers.get("Deprecation") == "true"
    assert response.headers.get("X-API-Migration-Target") == "/api/v2"
    assert "moved to v2" in (response.headers.get("X-API-Migration-Message") or "").lower()


def test_v2_responses_do_not_include_migration_headers(client: TestClient) -> None:
    response = client.post(
        "/api/v2/auth/login",
        json={"email": "missing@example.com", "password": "bad"},
    )
    assert response.status_code == 401
    assert response.headers.get("Deprecation") is None
    assert response.headers.get("X-API-Migration-Target") is None


@pytest.mark.asyncio
async def test_v2_async_client_no_migration_headers(async_client: AsyncClient) -> None:
    response = await async_client.post(
        "/api/v2/auth/login",
        json={"email": "missing@example.com", "password": "bad"},
    )
    assert response.status_code == 401
    assert response.headers.get("Deprecation") is None
    assert response.headers.get("X-API-Migration-Target") is None

