#!/usr/bin/env bash
# === FILE: backend/fix-502.sh ===
# One-shot recovery script for nginx 502 / Django startup issues.
# Usage:  bash fix-502.sh
set -euo pipefail
cd "$(dirname "$0")"

echo "==> tearing down old containers"
docker compose down

echo "==> building fresh images (picks up new requirements.txt)"
docker compose build django daphne celery celery_beat

echo "==> starting services"
docker compose up -d

echo "==> waiting up to 60s for Django to become healthy"
for i in $(seq 1 30); do
  if curl -fsS http://localhost:8000/api/v1/health/ >/dev/null 2>&1; then
    echo "    Django responding on :8000"
    break
  fi
  printf "."
  sleep 2
done
echo

echo
echo "==> container status"
docker compose ps

echo
echo "==> last 30 lines of django logs"
docker compose logs --tail=30 django || true

echo
echo "==> nginx round-trip test"
curl -i http://localhost/api/v1/health/ | head -20

echo
echo "==> CORS preflight test (should include Access-Control-Allow-Origin)"
curl -i -X OPTIONS http://localhost/api/v1/auth/login/ \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type" 2>&1 | head -20

echo
echo "Done. If both health checks returned HTTP/200, log in from the"
echo "browser at http://localhost:5173 — it should work now."
