#!/usr/bin/env bash
# Applies pending migrations from database/migrations/ to Supabase.
# Compares filenames against supabase_migrations.schema_migrations to skip
# already-applied migrations.
#
# Required env vars:
#   DATABASE_URL  - Postgres connection string (Supabase direct connection)
#
# Usage:
#   ./database/migrate.sh                            # from backend repo root
#   DATABASE_URL=postgres://... ./migrate.sh          # from this directory

set -euo pipefail

MIGRATIONS_DIR="$(cd "$(dirname "$0")/migrations" && pwd)"

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL is not set" >&2
  exit 1
fi

# Extract migration name from filename: "01_setup_tenants.sql" -> "setup_tenants"
get_migration_name() {
  basename "$1" .sql | sed 's/^[0-9]*_//'
}

# Get list of already-applied migration names
applied=$(psql "$DATABASE_URL" -t -A -c \
  "SELECT name FROM supabase_migrations.schema_migrations ORDER BY version;" 2>/dev/null || echo "")

pending=0
applied_count=0

for file in "$MIGRATIONS_DIR"/*.sql; do
  [ -f "$file" ] || continue
  name=$(get_migration_name "$file")

  if echo "$applied" | grep -qx "$name"; then
    applied_count=$((applied_count + 1))
    continue
  fi

  echo "Applying migration: $(basename "$file") ($name)"

  # Apply the migration SQL
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$file"

  # Record it in supabase_migrations.schema_migrations
  version=$(date +%Y%m%d%H%M%S)$(printf '%03d' $pending)
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c \
    "INSERT INTO supabase_migrations.schema_migrations (version, name)
     VALUES ('$version', '$name');"

  echo "  -> Applied successfully"
  pending=$((pending + 1))
done

echo ""
echo "Done. $applied_count already applied, $pending newly applied."
