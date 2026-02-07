#!/usr/bin/env bash
set -euo pipefail

if [ "${WAIT_FOR_DB:-1}" = "1" ]; then
  python - <<'PY'
import os
import time
import psycopg

db = os.environ.get("POSTGRES_DB", "itin")
user = os.environ.get("POSTGRES_USER", "itin")
password = os.environ.get("POSTGRES_PASSWORD", "itin")
host = os.environ.get("POSTGRES_HOST", "db")
port = int(os.environ.get("POSTGRES_PORT", "5432"))

dsn = f"dbname={db} user={user} password={password} host={host} port={port}"
for _ in range(60):
    try:
        with psycopg.connect(dsn):
            break
    except psycopg.OperationalError:
        time.sleep(1)
else:
    raise SystemExit("Database is not available")
PY
fi

exec "$@"
