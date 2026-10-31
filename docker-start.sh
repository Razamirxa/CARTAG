#!/bin/sh
# Applies database changes, makes sure the first admin exists when asked to, then starts the server.
set -e

alembic upgrade head

if [ -n "$ADMIN_EMAIL" ] && [ -n "$ADMIN_PASSWORD" ]; then
  python -m cartag.cli create-admin --email "$ADMIN_EMAIL" --name "Admin"
fi

exec uvicorn cartag.main:app --host 0.0.0.0 --port "${PORT:-10000}"
