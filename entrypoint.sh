#!/usr/bin/env bash
set -euo pipefail

# Wait for Postgres to be ready
until pg_isready -h "${DB_HOST:-db}" -p "${DB_PORT:-5432}"; do
  echo "Waiting for Postgres..."
  sleep 1
done

# Run migrations
uv run python backend/manage.py migrate --noinput

# Collect static files
uv run python backend/manage.py collectstatic --noinput || true

# Change to backend directory so Python can find the modules
cd backend

# Start Gunicorn (production-grade WSGI server)
exec uv run gunicorn backend.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3
