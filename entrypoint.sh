#!/bin/sh

set -e

# Wait for the database to become available
echo "Waiting for PostgreSQL..."
while ! nc -z db 5432; do
  sleep 1
done
echo "PostgreSQL started."

# Apply migrations
python manage.py migrate

echo "Command to execute: $@"
# Start your Django app (you can modify this if you use a different command to start your app)
exec "$@"
