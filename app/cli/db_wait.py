from __future__ import annotations

import os
import time

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError


def wait_for_db(*, database_url: str, timeout_s: int) -> None:
    deadline = time.monotonic() + timeout_s
    last_exc: Exception | None = None

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        while time.monotonic() < deadline:
            try:
                with engine.connect():
                    return
            except OperationalError as exc:
                last_exc = exc
                time.sleep(1)
    finally:
        engine.dispose()

    msg = f"Database not reachable after {timeout_s}s."
    raise RuntimeError(msg) from last_exc


def main() -> None:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to wait for the database.")

    timeout_s = int(os.environ.get("DB_WAIT_TIMEOUT", "60"))
    wait_for_db(database_url=database_url, timeout_s=timeout_s)


if __name__ == "__main__":
    main()
