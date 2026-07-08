#!/usr/bin/env bash
#
# Seed a `prospect` Doppler config (dev | stg | prd) in one shot.
#
#   scripts/provision-doppler-secrets.sh <dev|stg|prd>
#   FORCE=1 scripts/provision-doppler-secrets.sh <cfg>   # rotate an already-seeded config
#
# It sets the two kinds of value we DON'T need to collect:
#   • generated  — random passwords/keys we mint ourselves (piped via stdin, never printed)
#   • coordinates — identifiers + in-network hostnames we choose, derived from the compose file
#
# It does NOT set the COLLECTED values (issued by another system); those are printed as a
# short checklist at the end. Per-env quirks handled here so you don't have to remember them:
#   • dev uses ENCRYPTION; stg uses PB_ENCRYPTION  (the compose env var name differs)
#   • prd has NO PocketBase container (external PB) → its PB url + bot creds are collected
set -euo pipefail

CFG="${1:?usage: $0 <dev|stg|prd>}"; PROJECT=prospect
case "$CFG" in dev|stg|prd) ;; *) echo "config must be dev|stg|prd" >&2; exit 1 ;; esac

ds()  { doppler "$@" -p "$PROJECT" -c "$CFG"; }
rand(){ openssl rand -base64 "${1:-24}" | tr -dc 'A-Za-z0-9' | cut -c1-"${2:-32}"; }
hex() { openssl rand -hex "$1"; }                       # hex 16 -> 32 chars (PocketBase needs 32)
setsec(){ printf '%s' "$2" | ds secrets set "$1" >/dev/null && echo "  secret  $1"; }

if ds secrets --only-names 2>/dev/null | grep -qw POSTGRES_PASSWORD && [ "${FORCE:-0}" != 1 ]; then
  echo "✋ prospect/$CFG already seeded (POSTGRES_PASSWORD present)." >&2
  echo "   Re-seeding rotates DB/admin creds and breaks a running stack until migrated." >&2
  echo "   Use FORCE=1 only if you mean to rotate." >&2
  exit 1
fi

# per-env service coordinates — deployed stacks reach each other by network alias (see compose)
case "$CFG" in
  dev) PREFIX=""     ;;
  stg) PREFIX="stg_" ;;
  prd) PREFIX="prd_" ;;
esac
DB_HOST="${PREFIX}listmonk_db"
LM_URL="http://${PREFIX}listmonk_app:9000/api"   # app appends /lists,/campaigns… → needs /api

PG_PASS="$(rand 32 32)"     # generated once so listmonk + postgres creds stay in sync

echo "▶ seeding prospect/$CFG"
# --- generated secrets (every env) ---
setsec POSTGRES_PASSWORD       "$PG_PASS"
setsec LISTMONK_DB_PASSWORD    "$PG_PASS"
setsec LISTMONK_ADMIN_PASSWORD "$(rand 24 24)"

# --- identifiers + coordinates (every env) ---
ds secrets set \
  POSTGRES_USER=listmonk POSTGRES_DB=listmonk \
  LISTMONK_DB_USER=listmonk LISTMONK_DB_DATABSE=listmonk \
  LISTMONK_DB_HOST="$DB_HOST" LISTMONK_DB_PORT=5432 LISTMONK_DB_SSL_MODE=disable \
  LISTMONK_DB_MAX_OPEN=25 LISTMONK_DB_MAX_IDLE=25 LISTMONK_DB_MAX_LIFETIME=300s \
  LISTMONK_ADMIN_USER=admin LISTMONK_APP_ADDRESS=0.0.0.0:9000 LISTMONK_API_URL="$LM_URL" \
  ENVIROMENT="$CFG" ENVIRONMENT="$CFG" >/dev/null && echo "  config  identifiers + coordinates"

# --- PocketBase: present in dev/stg (container), external in prd (collected) ---
if [ "$CFG" != prd ]; then
  ENC_KEY=ENCRYPTION; [ "$CFG" = stg ] && ENC_KEY=PB_ENCRYPTION
  setsec "$ENC_KEY"              "$(hex 16)"
  setsec PB_INVITATION_PEPPER    "$(hex 16)"
  setsec N8N_WEBHOOK_SECRET      "$(hex 24)"   # configure this same value in n8n
  setsec POCKETBASE_BOT_PASSWORD "$(rand 24 24)"
  PB_URL="http://${PREFIX}pocketbase:8090"; [ "$CFG" = stg ] && PB_URL="http://stg_listmonk_api_db:8090"
  ds secrets set POCKETBASE_BOT_EMAIL="bot+${CFG}@ailian.com.br" POCKETBASE_API_URL="$PB_URL" >/dev/null \
    && echo "  config  pocketbase bot email + url"
fi

# --- collected (issued elsewhere) ---
cat <<EOF

✅ prospect/$CFG seeded. Set these COLLECTED values by hand:
  doppler secrets set LISTMONK_USER  -p $PROJECT -c $CFG   # Listmonk admin -> API users (after boot)
  doppler secrets set LISTMONK_TOKEN -p $PROJECT -c $CFG   # token Listmonk issues for that user
  doppler secrets set N8N_WEBHOOK_URL -p $PROJECT -c $CFG  # the n8n webhook endpoint
EOF
if [ "$CFG" != dev ]; then
  cat <<EOF
  doppler secrets set DOCKPLOY_WEBHOOK -p $PROJECT -c $CFG          # Dokploy app -> redeploy webhook
  doppler secrets set OTEL_EXPORTER_OTLP_ENDPOINT -p $PROJECT -c $CFG  # shared observability collector
  doppler configs tokens create deploy -c $CFG -p $PROJECT --plain  # -> GitHub secret DOPPLER_TOKEN_${CFG^^}
EOF
fi
if [ "$CFG" = prd ]; then
  cat <<EOF
  doppler secrets set POCKETBASE_API_URL     -p $PROJECT -c $CFG   # external prod PocketBase URL
  doppler secrets set POCKETBASE_BOT_EMAIL   -p $PROJECT -c $CFG   # must match the external PB bot
  doppler secrets set POCKETBASE_BOT_PASSWORD -p $PROJECT -c $CFG  # must match the external PB bot
EOF
fi
