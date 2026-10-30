#!/bin/bash
# Migration script for deployment
# Runs database migrations as a one-time task

set -e

echo "Running database migrations..."
alembic upgrade head

echo "Migrations completed successfully."