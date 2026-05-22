#!/usr/bin/env sh
# === FILE: backend/docker-entrypoint.sh ===
# Boots Django before exec-ing whatever command was passed.
#
# The DB setup steps run on every container start but are idempotent:
#   - makemigrations: regenerates initial migrations into the image's
#     /app/<app>/migrations directory (no-op once they exist for the
#     life of the container). They are NOT persisted across container
#     restarts because the app directory is part of the image, not a
#     mounted volume — so a fresh container always rebuilds them, which
#     produces deterministic 0001_initial migration files.
#   - migrate: applies migrations to Postgres.
#   - loaddata: loads country / dial-code fixtures (idempotent — Django
#     skips rows whose PK already exists).
#   - collectstatic: copies admin/swagger assets.
#
# DB setup only runs in the "leader" container (django). The others
# (celery, celery_beat, daphne) wait for the DB to be migrated, then
# exec their own command.

set -e

# Apps with custom models we want to generate migrations for.
APPS="core users wallet transactions referrals rewards notifications support reference"

is_db_setup_leader() {
    # Only the django service runs DB setup; the others tail-wait.
    case "$1" in
        gunicorn*) return 0 ;;
        *) return 1 ;;
    esac
}

wait_for_db() {
    python <<'PY'
import os, time, sys
import dj_database_url, psycopg2
url = os.environ.get("DATABASE_URL", "")
if not url:
    sys.exit(0)
cfg = dj_database_url.parse(url)
for i in range(60):
    try:
        psycopg2.connect(
            host=cfg["HOST"], port=cfg["PORT"] or 5432,
            user=cfg["USER"], password=cfg["PASSWORD"],
            dbname=cfg["NAME"], connect_timeout=2,
        ).close()
        print("postgres is ready")
        sys.exit(0)
    except Exception as e:
        print(f"waiting for postgres ({i+1}/60): {e}")
        time.sleep(2)
sys.exit("postgres never became reachable")
PY
}

wait_for_migrations() {
    # Followers (celery, beat, daphne) wait until the leader has created
    # the django_celery_beat_* tables before starting.
    python <<'PY'
import os, time, sys
import dj_database_url, psycopg2
url = os.environ.get("DATABASE_URL", "")
cfg = dj_database_url.parse(url)
for i in range(120):
    try:
        conn = psycopg2.connect(
            host=cfg["HOST"], port=cfg["PORT"] or 5432,
            user=cfg["USER"], password=cfg["PASSWORD"],
            dbname=cfg["NAME"], connect_timeout=2,
        )
        cur = conn.cursor()
        cur.execute(
            "SELECT to_regclass('public.django_celery_beat_crontabschedule')"
        )
        if cur.fetchone()[0] is not None:
            conn.close()
            print("migrations applied; followers may start")
            sys.exit(0)
        conn.close()
    except Exception as e:
        print(f"db not yet ready: {e}")
    print(f"waiting for migrations ({i+1}/120)...")
    time.sleep(2)
sys.exit("migrations never appeared")
PY
}

wait_for_db

if is_db_setup_leader "$1"; then
    echo "==> generating migrations"
    # makemigrations is idempotent for fresh apps; once 0001_initial
    # exists in the image, this is a no-op.
    python manage.py makemigrations $APPS --noinput || true

    echo "==> applying migrations"
    python manage.py migrate --noinput

    echo "==> loading reference fixtures"
    python manage.py loaddata fixtures/countries.json fixtures/dial_codes.json || true

    echo "==> collecting static"
    python manage.py collectstatic --noinput || true
else
    echo "==> waiting for migrations to be applied"
    wait_for_migrations
fi

echo "==> exec: $*"
exec "$@"
