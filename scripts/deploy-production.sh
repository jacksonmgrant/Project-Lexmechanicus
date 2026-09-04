#!/usr/bin/env sh
set -eu

git pull --ff-only
docker compose -f docker-compose.production.yml up -d --build --remove-orphans
docker compose -f docker-compose.production.yml ps
