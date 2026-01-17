#!/bin/zsh
cd "$(dirname "$0")"

source .venv/bin/activate
export PYTHONPATH=$(pwd)

echo "Starting FastAPI on http://127.0.0.1:8010 ..."
uvicorn app:app --reload --port 8010
