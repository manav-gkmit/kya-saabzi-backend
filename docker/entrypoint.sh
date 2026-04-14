#!/usr/bin/env sh
set -eu

RUN_MIGRATIONS="${RUN_MIGRATIONS:-1}"
RUN_SEEDERS="${RUN_SEEDERS:-1}"

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is required."
  exit 1
fi

if [ -z "${SECRET_KEY:-}" ]; then
  echo "SECRET_KEY is required."
  exit 1
fi

if [ "${RUN_MIGRATIONS}" != "0" ] || [ "${RUN_SEEDERS}" != "0" ]; then
  python -m app.cli.db_wait
fi

if [ "${RUN_MIGRATIONS}" != "0" ]; then
  alembic upgrade head
fi

if [ "${RUN_SEEDERS}" != "0" ]; then
  python -m app.seeders
fi

exec "$@"
