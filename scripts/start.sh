#!/usr/bin/env bash
set -euo pipefail

python manage.py migrate --noinput --skip-checks
python manage.py createcachetable

# Sync Site domain + Google SocialApp credentials on every deploy.
# Fixes 401 "Third-Party Login Failure" caused by Site domain mismatch
# (DB was set to localhost:8000 from local dev; Railway needs ihsms.up.railway.app).
# Command is idempotent — safe to run repeatedly.
if [ -n "${GOOGLE_OAUTH_CLIENT_ID:-}" ] && [ -n "${GOOGLE_OAUTH_CLIENT_SECRET:-}" ]; then
  python manage.py setup_google_oauth \
    --site-domain "ihsms.up.railway.app" \
    --site-name "IHSMS"
fi

if [ -n "${MEDIA_ROOT:-}" ] && [ -d /app/media ] && [ "$MEDIA_ROOT" != /app/media ]; then
  cp -rn /app/media/. "$MEDIA_ROOT"/ 2>/dev/null || true
fi

# Drop expired sessions so dashboard/analytics never pay for a bloated django_session
# table restored from local dumps.
python manage.py clearsessions 2>/dev/null || true

exec gunicorn talisay_housing.wsgi:application \
  --bind "0.0.0.0:${PORT:-8080}" \
  -k gthread \
  --workers 2 \
  --threads 4 \
  --timeout 180 \
  --access-logfile - \
  --error-logfile -
