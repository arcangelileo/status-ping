#!/bin/sh
set -e

# Run Alembic migrations before starting the app
echo "Running database migrations..."
alembic upgrade head

echo "Starting StatusPing..."
exec "$@"
