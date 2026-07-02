#!/usr/bin/env bash
#
# Import the LEAN PocketBase schema into a DEPLOYED env's PocketBase (stg | prd).
#
# The deployed app reads only `monk_client_lists` + `monk_lists`, so production uses
# `services/pocketbase/pb_schema.json` — NOT the chatwoot dev fixture (pb_schema.dev.json).
# Idempotent (deleteMissing=false → never drops data). Mirrors how the dev stack's pb-init
# seeds locally; this is the deployed-env equivalent (stg/prd compose run no seeding one-shots).
#
#   PB_PUBLIC_URL=https://pb.stg.ailian.com.br scripts/provision-pb-schema.sh stg
#
# Superuser creds come from Doppler `POCKETBASE_BOT_*` — which the stg PB bootstraps from
# (docker-compose.stg.yml) and which must match the external prod PB's bot for prd.
set -euo pipefail

CFG="${1:?usage: $0 <stg|prd>}"; PROJECT=prospect
case "$CFG" in stg|prd) ;; *) echo "config must be stg|prd" >&2; exit 1 ;; esac
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${PB_PUBLIC_URL:?set PB_PUBLIC_URL to the deployed PocketBase root (e.g. https://pb.<env>.ailian.com.br)}"

ds()   { doppler "$@" --project "$PROJECT" --config "$CFG"; }
need() { command -v "$1" >/dev/null || { echo "need '$1' on PATH" >&2; exit 1; }; }
need doppler; need python3

EMAIL="$(ds secrets get POCKETBASE_BOT_EMAIL --plain)"
PASS="$(ds secrets get POCKETBASE_BOT_PASSWORD --plain)"
[ -n "$EMAIL" ] && [ -n "$PASS" ] || { echo "POCKETBASE_BOT_EMAIL/PASSWORD not set in $PROJECT/$CFG" >&2; exit 1; }

echo "▶ importing lean schema into $PROJECT/$CFG PocketBase ($PB_PUBLIC_URL)"
PB_URL="$PB_PUBLIC_URL" PB_ADMIN_EMAIL="$EMAIL" PB_ADMIN_PASSWORD="$PASS" \
  SCHEMA_PATH="$ROOT/services/pocketbase/pb_schema.json" \
  python3 "$ROOT/tools/dev/pb_init.py"

echo "✅ schema imported. (chatwoot collections are intentionally NOT deployed — they live in the"
echo "   dev fixture only; enable them in stg/prd once the merged schema is reconciled.)"
