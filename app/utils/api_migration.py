from __future__ import annotations

from starlette.responses import Response

V1_SUNSET = "2026-12-31"
V2_TARGET = "/api/v2"
V1_MIGRATION_MESSAGE = "This endpoint has moved to v2. Use /api/v2/*."


def migration_exposed_headers() -> list[str]:
    return [
        "Deprecation",
        "Sunset",
        "Link",
        "Warning",
        "X-API-Migration-Message",
        "X-API-Migration-Target",
    ]


def add_v1_migration_headers(*, path: str, response: Response) -> None:
    if not path.startswith("/api/v1"):
        return

    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = V1_SUNSET
    response.headers["Link"] = f'<{V2_TARGET}>; rel="successor-version"'
    response.headers["Warning"] = f'299 - "{V1_MIGRATION_MESSAGE} Sunset={V1_SUNSET}"'
    response.headers["X-API-Migration-Message"] = V1_MIGRATION_MESSAGE
    response.headers["X-API-Migration-Target"] = V2_TARGET
