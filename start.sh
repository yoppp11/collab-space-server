#!/bin/bash
set -e

echo "Running database migrations..."
python manage.py migrate --noinput || echo "Migration failed or no database connected yet"

echo "Collecting static files..."
python manage.py collectstatic --noinput || true

echo "Starting uvicorn server on port ${PORT:-8000}..."
exec uvicorn config.asgi:application --host 0.0.0.0 --port ${PORT:-8000}
