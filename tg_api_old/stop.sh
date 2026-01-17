#!/bin/zsh
echo "Stopping FastAPI on port 8010..."
# убиваем все процессы, слушающие порт 8010
PIDS=$(lsof -ti tcp:8010)
if [ -n "$PIDS" ]; then
  kill $PIDS
else
  echo "No process running on 8010"
fi

