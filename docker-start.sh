#!/bin/sh
# Applies database changes, creates the first admin when none exists yet (never resets an existing one),
# then starts the server.
set -e

alembic upgrade head

if [ -n "$ADMIN_EMAIL" ] && [ -n "$ADMIN_PASSWORD" ]; then
  python -m cartag.cli create-admin --email "$ADMIN_EMAIL" --name "Admin" --if-none
fi

# Logging is switched on here so the console SMS provider's codes show in the service log (preview only).
exec python -c "import logging, os, uvicorn; logging.basicConfig(level=logging.INFO); uvicorn.run('cartag.main:app', host='0.0.0.0', port=int(os.environ.get('PORT', '10000')))"
