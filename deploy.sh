#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$HOME/ai-picturebook-backend-handwrite}"
APP_CONTAINER="${APP_CONTAINER:-ai-picturebook-app}"
BRANCH="${BRANCH:-main}"

echo "[deploy] project dir: $PROJECT_DIR"
cd "$PROJECT_DIR"

echo "[deploy] pulling latest code from origin/$BRANCH"
git pull --ff-only origin "$BRANCH"

echo "[deploy] cleaning old tts artifacts"
rm -rf uploads/tts/*
mkdir -p uploads/tts

echo "[deploy] removing old app container if present"
docker rm -f "$APP_CONTAINER" 2>/dev/null || true

echo "[deploy] rebuilding app image"
docker compose build app

echo "[deploy] starting app container"
docker compose up -d app

echo "[deploy] recent app logs"
docker logs --tail 100 "$APP_CONTAINER"
