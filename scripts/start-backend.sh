#!/usr/bin/env sh
set -eu
project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_root/backend"
../.venv/bin/python -m alembic upgrade head
exec ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
