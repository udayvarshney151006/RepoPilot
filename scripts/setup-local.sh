#!/usr/bin/env sh
set -eu
project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_root"
test -f .env || cp .env.example .env
test -f frontend/.env.local || cp frontend/.env.example frontend/.env.local
test -d .venv || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -c ./backend/requirements.lock.txt -e './backend[test]'
(cd backend && ../.venv/bin/python -m alembic upgrade head)
(cd frontend && corepack pnpm install --frozen-lockfile)
printf '%s\n' 'Setup complete. Run scripts/start-backend.sh and scripts/start-frontend.sh in separate terminals.'
