#!/usr/bin/env sh
set -eu

RUN_MIGRATIONS="${RUN_MIGRATIONS:-1}"
RUN_SEEDERS="${RUN_SEEDERS:-1}"

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is required."
  exit 1
fi

if [ "${RUN_MIGRATIONS}" != "0" ]; then
  python -m app.cli.db_wait
  alembic upgrade head
fi

if [ "${RUN_SEEDERS}" != "0" ]; then
  python -m app.seeders
fi

exec "$@"
