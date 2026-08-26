#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Seeding initial data..."
python -m scripts.seed

echo "Starting API server..."
exec "$@"
