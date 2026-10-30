#!/bin/bash
# Migration entrypoint script
# Runs database migrations before starting the application

set -e

echo "Running database migrations..."
alembic upgrade head

echo "Migrations completed successfully."
echo "Starting application..."
exec "$@"