#!/usr/bin/env bash
#
# Provision the COLLECTED secrets for a DEPLOYED prospect env (stg | prd) — the values
# another system issues, which provision-doppler-secrets.sh leaves as a checklist:
#
#   LISTMONK_USER / LISTMONK_TOKEN   minted on the DEPLOYED Listmonk (via listmonk_init.py)
#   DOCKPLOY_WEBHOOK                 the Dockploy app's redeploy webhook
#   OTEL_EXPORTER_OTLP_ENDPOINT      the shared observability collector
#   DOPPLER_TOKEN_<ENV>             a service token -> GitHub Actions secret + <env>_act branch
#
# Run this AFTER the env's stack is deployed (its Listmonk is reachable) and you have the
# Dockploy webhook. Secret values are piped into Doppler / GitHub, never printed.
#
#   Usage (set what you have; missing inputs are skipped):
#     LISTMONK_PUBLIC_URL=https://listmonk.stg.ailian.com.br \
#     DOCKPLOY_WEBHOOK_URL='https://dokploy.../api/deploy/xxxx' \
#     OTEL_ENDPOINT='http://otel-collector:4317' \
#     scripts/provision-collected-secrets.sh stg
set -euo pipefail

CFG="${1:?usage: $0 <stg|prd>}"; PROJECT=prospect
case "$CFG" in stg|prd) ;; *) echo "config must be stg|prd" >&2; exit 1 ;; esac
REPO="${GH_REPO:-ailianbr/prospect}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

ds()   { doppler "$@" --project "$PROJECT" --config "$CFG"; }
need() { command -v "$1" >/dev/null || { echo "need '$1' on PATH" >&2; exit 1; }; }
need doppler; need python3

echo "▶ provisioning collected secrets for $PROJECT/$CFG"

# ── 1. Listmonk API user/token (minted on the deployed Listmonk) ─────────────
if [ -n "${LISTMONK_PUBLIC_URL:-}" ]; then
  # admin creds come from Doppler (generated earlier by provision-doppler-secrets.sh)
  LM_ADMIN_USER="$(ds secrets get LISTMONK_ADMIN_USER --plain)"
  LM_ADMIN_PASS="$(ds secrets get LISTMONK_ADMIN_PASSWORD --plain)"
  tmp="$(mktemp)"; trap 'shred -u "$tmp" 2>/dev/null || rm -f "$tmp"' EXIT
  LISTMONK_URL="$LISTMONK_PUBLIC_URL" \
    LISTMONK_ADMIN_USER="$LM_ADMIN_USER" LISTMONK_ADMIN_PASSWORD="$LM_ADMIN_PASS" \
    ENV_LOCAL_PATH="$tmp" \
    python3 "$ROOT/tools/dev/listmonk_init.py"
  set -a; . "$tmp"; set +a      # LISTMONK_USER / LISTMONK_TOKEN
  printf '%s' "$LISTMONK_USER"  | ds secrets set LISTMONK_USER  >/dev/null && echo "  set LISTMONK_USER"
  printf '%s' "$LISTMONK_TOKEN" | ds secrets set LISTMONK_TOKEN >/dev/null && echo "  set LISTMONK_TOKEN"
  echo "  (re-running rotates the token — redeploy the api afterwards so it picks up the new value)"
else
  echo "  skip LISTMONK_USER/TOKEN (set LISTMONK_PUBLIC_URL to the deployed Listmonk root to mint them)"
fi

# ── 2. Dockploy webhook + OTEL endpoint ──────────────────────────────────────
if [ -n "${DOCKPLOY_WEBHOOK_URL:-}" ]; then
  printf '%s' "$DOCKPLOY_WEBHOOK_URL" | ds secrets set DOCKPLOY_WEBHOOK >/dev/null && echo "  set DOCKPLOY_WEBHOOK"
else
  echo "  skip DOCKPLOY_WEBHOOK (set DOCKPLOY_WEBHOOK_URL)"
fi
if [ -n "${OTEL_ENDPOINT:-}" ]; then
  printf '%s' "$OTEL_ENDPOINT" | ds secrets set OTEL_EXPORTER_OTLP_ENDPOINT >/dev/null && echo "  set OTEL_EXPORTER_OTLP_ENDPOINT"
else
  echo "  skip OTEL_EXPORTER_OTLP_ENDPOINT (set OTEL_ENDPOINT)"
fi

# ── 3. DOPPLER_TOKEN_<ENV> -> GitHub Actions secret + <env>_act branch ───────
# Needed by the deploy step (the Dockploy redeploy curl), not by the tests anymore.
TOKEN_NAME="DOPPLER_TOKEN_${CFG^^}"
if [ "${SKIP_DOPPLER_TOKEN:-0}" = 1 ]; then
  echo "  skip $TOKEN_NAME (SKIP_DOPPLER_TOKEN=1)"
else
  SVC_TOKEN="$(doppler configs tokens create "ci-${CFG}" --project "$PROJECT" --config "$CFG" --plain)"
  if command -v gh >/dev/null; then
    printf '%s' "$SVC_TOKEN" | gh secret set "$TOKEN_NAME" -R "$REPO" >/dev/null && echo "  set GitHub secret $TOKEN_NAME (-R $REPO)"
  else
    echo "  gh not on PATH — set the GitHub secret $TOKEN_NAME by hand"
  fi
  # store in the _act branch so local `act` runs inject it the same way (doppler-architecture.md)
  printf '%s' "$SVC_TOKEN" | doppler secrets set "$TOKEN_NAME" --project "$PROJECT" --config "${CFG}_act" >/dev/null 2>&1 \
    && echo "  stored $TOKEN_NAME in ${CFG}_act branch" || echo "  ($TOKEN_NAME not stored in ${CFG}_act — branch may not exist)"
fi

cat <<EOF

✅ done for $PROJECT/$CFG. Verify (names only):
  doppler secrets --only-names -p $PROJECT -c $CFG | grep -E 'LISTMONK_USER|LISTMONK_TOKEN|DOCKPLOY_WEBHOOK|OTEL_'
  gh secret list -R $REPO | grep $TOKEN_NAME
EOF
