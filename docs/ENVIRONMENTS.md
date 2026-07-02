# Environments (prospect)

prospect uses **three standard environments**, matching the Doppler `prospect` project
configs. This mirrors the platform standard already adopted by conectai.

| Env | Doppler config | Infra | Rule |
|---|---|---|---|
| **dev** | `dev` (+ `dev_personal` per developer) | **local** containers (`docker-compose.yml`) | disposable — create/destroy/modify freely; never depend on deployed infra |
| **stg** | `stg` | deployed clone of prod (Dokploy; aliases `stg_*`) | **prod-like** — treat as production; **never develop/change directly**; changes arrive via PR/CI |
| **prd** | `prd` | production (Dokploy; aliases `prd_*`) | production |

`ENVIRONMENT` (`app/settings.py`) is `dev` \| `stg` \| `prd`; `settings.is_dev` /
`is_stg` / `is_prod` gate behavior (e.g. the verbose error handler in `main.py`).

## Running locally (dev) — one command, fully seeded

The dev stack is self-contained — `docker-compose.yml` brings up **api + listmonk +
postgres + PocketBase**. All config (infra URLs *and* secrets) comes from Doppler `dev`;
compose passes it through, so the same file needs no per-env editing:

```bash
doppler run -p prospect -c dev -- docker compose up --build
```

**The stack seeds itself** — no manual PocketBase admin or Listmonk API-token setup.
Two idempotent one-shots run before the api starts (it waits via
`depends_on … service_completed_successfully`), so a fresh `up` is never racing an
empty/unseeded backend:

- **`pb-init`** (`tools/dev/pb_init.py` + `seed_chatwoot.py`) — authenticates as the PocketBase
  superuser (the muchobien image bootstraps it from `POCKETBASE_BOT_EMAIL`/`POCKETBASE_BOT_PASSWORD`),
  imports the dev/test schema (`services/pocketbase/pb_schema.dev.json`), and seeds the chatwoot
  instance graph. Re-running upserts (`deleteMissing=false`) and the seed is idempotent.
- **`listmonk-init`** (`tools/dev/listmonk_init.py`) — logs into Listmonk as the
  super-admin, (re)creates the `monk_api` API user, and writes the freshly-minted
  `LISTMONK_USER`/`LISTMONK_TOKEN` into the shared `seed_env` volume. Listmonk issues a
  token only once, at creation, so it deletes+recreates the user each `up` to guarantee a
  usable token. This is prospect's analogue of conectai's `.env.full` pattern: a seed step
  that discovers a value the app needs and hands it over via an env file.

The api container sources that env file at startup
(`sh -c 'set -a; . /seed/.env.local; set +a; exec …'`), so `LISTMONK_USER`/`LISTMONK_TOKEN`
arrive without ever being committed or pasted into Doppler.

- api → http://localhost:8000 · Listmonk → http://localhost:9000 · PocketBase admin →
  http://localhost:8090/_/ (log in with the `POCKETBASE_BOT_*` dev creds).
- **dev infra URLs are in-container hostnames** — Doppler `dev` holds
  `POCKETBASE_API_URL=http://pocketbase:8090` and `LISTMONK_API_URL=http://listmonk_app:9000/api`
  (note the `/api` suffix — the app appends `/lists`, `/campaigns`, …). These resolve inside
  the compose network; a **host** process can't reach those names (see below).

## Why dev is local (not the staging backend)

Pointing local development at the deployed staging Listmonk/PocketBase causes conflicts —
CI and other developers share it, and mutations collide. So **dev runs everything locally**:
a throwaway Postgres, Listmonk, and PocketBase you can reset at will (`docker compose down -v`).
This keeps **stg** clean: stg is treated like prod and only changes via PR/CI.

## Running the tests against the local stack

The suite is **integration tests** — they hit live Listmonk and PocketBase. With the dev
stack up, the in-container hostnames in Doppler `dev` don't resolve from a **host** process,
so override the two URLs to the published `localhost` ports for a host test run:

```bash
cd services/api
doppler run -p prospect -c dev -- env \
  LISTMONK_API_URL=http://localhost:9000/api \
  POCKETBASE_API_URL=http://localhost:8090 \
  task ci_test
```

`LISTMONK_USER`/`LISTMONK_TOKEN` for the host run come from the seeded API user — read them
from the running stack once:

```bash
docker run --rm -v prospect_seed_env:/seed alpine cat /seed/.env.local
```

(stg/prd run on Dokploy with their own Doppler configs and externally-provisioned
Listmonk/PocketBase — they are not seeded by these one-shots.)

### Chatwoot handler tests

The `/messenger/chat` handler reads its per-tenant config from the conectai-merged PocketBase
collections (`instances`, `service_secrets`, …). The two committed schemas disagree with the
handler code, so `tools/dev/gen_dev_schema.py` produces **`pb_schema.dev.json`** — a TEST
FIXTURE that keeps `monk_client_lists.client` as text (core contract) and adds the chatwoot
collections (with `monk_channel_configs.handler` extended to accept `chat`, rules stripped).
`pb-init` imports it and `seed_chatwoot.py` wires instance `87v79w2os56q298`, so the chatwoot
**integration + channel** tests run green inside the normal `ci_test` (`TEST_CHATWOOT_INSTANCE_ID`
is set in `.env.ci`). The two **live-Chatwoot** tests stay skipped unless you point at a real
Chatwoot: `TEST_CHATWOOT_LIVE=1` (template list) and `TEST_CHATWOOT_PHONE`+`TEST_CHATWOOT_TEMPLATE`
(WhatsApp e2e send). Regenerate the fixture if the source schemas change (see the script header).

## Provisioning a config's secrets

`scripts/provision-doppler-secrets.sh <dev|stg|prd>` mints the generatable secrets and
sets the in-network coordinates for a config; the few values another system issues
(`LISTMONK_USER/TOKEN`, `DOCKPLOY_WEBHOOK`, `DOPPLER_TOKEN_*`) are printed as a checklist.
In **dev** those last two aren't needed and `LISTMONK_USER/TOKEN` are produced by
`listmonk-init` above.

## Standing up a fresh stg / prd

The deployed stacks (`docker-compose.stg.yml` / `.prd.yml`) run **no seeding one-shots** — unlike
dev they don't self-seed. After the first Dockploy deploy of an env:

1. **PocketBase** — stg runs its own `pocketbase` container that bootstraps the superuser from
   `POCKETBASE_BOT_*` (already wired). Import the **lean** schema (`pb_schema.json` — the app only
   reads `monk_client_lists` + `monk_lists`; the chatwoot fixture is dev-only) into it:
   `PB_PUBLIC_URL=https://pb.stg.ailian.com.br scripts/provision-pb-schema.sh stg`. **prd** uses an
   external PocketBase — confirm it already has the bot superuser + lean schema.
2. **Collected secrets** — `scripts/provision-collected-secrets.sh <stg|prd>` mints the Listmonk API
   user on the deployed Listmonk and sets `LISTMONK_USER/TOKEN`, `DOCKPLOY_WEBHOOK`, `OTEL_…`, and
   `DOPPLER_TOKEN_<ENV>` (→ GitHub secret). Then redeploy so the api picks up `LISTMONK_TOKEN`.
