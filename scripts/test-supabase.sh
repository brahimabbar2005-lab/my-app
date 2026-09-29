#!/usr/bin/env bash
# Apply the Supabase migrations and seeds to an empty Postgres and run the RLS
# tests. Uses $DATABASE_URL when set (CI service container); otherwise starts a
# throwaway local cluster.
#
#   scripts/test-supabase.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PSQL_OPTS=(-v ON_ERROR_STOP=1 -q -X)

cleanup() { :; }
if [[ -z "${DATABASE_URL:-}" ]]; then
  PGBIN="$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -1)"
  DATA="$(mktemp -d)"
  PORT="${PGPORT:-54329}"
  RUN=()
  if [[ "$(id -u)" == "0" ]]; then chown postgres "$DATA"; RUN=(runuser -u postgres --); fi
  "${RUN[@]}" "$PGBIN/initdb" -D "$DATA" -U postgres --auth=trust >/dev/null
  "${RUN[@]}" "$PGBIN/pg_ctl" -D "$DATA" -o "-p $PORT -k /tmp" -l "$DATA/log" -w start >/dev/null
  cleanup() { "${RUN[@]}" "$PGBIN/pg_ctl" -D "$DATA" -m fast stop >/dev/null || true; rm -rf "$DATA"; }
  DATABASE_URL="postgresql://postgres@localhost:$PORT/postgres"
fi
trap cleanup EXIT

run() { psql "$DATABASE_URL" "${PSQL_OPTS[@]}" -f "$1"; }

echo "→ Supabase shim (auth schema, roles)"
run "$ROOT/supabase/tests/00_supabase_shim.sql"
for f in "$ROOT"/supabase/migrations/*.sql; do echo "→ migration $(basename "$f")"; run "$f"; done
echo "→ seeds"
run "$ROOT/supabase/seed/seed.sql"
run "$ROOT/supabase/seed/emergency_contacts.sql"
echo "→ RLS tests"
psql "$DATABASE_URL" "${PSQL_OPTS[@]}" -o /dev/null -f "$ROOT/supabase/tests/rls.test.sql"
echo "✓ migrations, seeds and RLS tests passed on an empty database"
