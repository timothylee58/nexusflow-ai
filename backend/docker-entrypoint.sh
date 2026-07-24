#!/bin/bash
set -e

# When a PostgreSQL DATABASE_URL is present, run Alembic migrations before
# starting the application so schema changes are always applied atomically
# on ECS task startup.
if [[ -n "${DATABASE_URL}" && "${DATABASE_URL}" != sqlite* ]]; then
    echo "[entrypoint] Running Alembic migrations..."
    alembic upgrade head
    echo "[entrypoint] Migrations complete."
fi

exec "$@"
