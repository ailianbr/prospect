# Doppler Architecture

## Why Doppler

All secrets are managed through Doppler instead of environment files or GitHub secrets directly. The main reasons:

- **Single source of truth** — credentials live in one place, not scattered across `.env` files, CI secrets, and docker compose overrides.
- **Scoped service tokens** — each environment gets its own token. A token for `stg` can only read `stg` secrets; it has no access to `prd`. This limits blast radius if a token leaks.
- **Branch configs** — a branch config inherits all secrets from its parent and only overrides specific values. This is used to mock deployment webhooks during local `act` runs without duplicating the entire config.
- **Single GitHub secret** — CI workflows only need `DOPPLER_TOKEN_STG` or `DOPPLER_TOKEN_PRD`. All app secrets flow through Doppler at runtime via `doppler run -- <command>`.

---

## Environments

Three root environments exist in the `prospect` Doppler project:

| Environment | Where it runs | Purpose |
|-------------|--------------|---------|
| `dev` | Local machine | Docker Compose stack for local development and testing |
| `stg` | Dockploy (dev server) | Latest build of `development` branch — acts as staging |
| `prd` | Dockploy (prod server) | Public-facing production API |

### `dev` — local environment

Contains everything needed to run the full docker compose stack locally:

- Listmonk DB credentials (`POSTGRES_*`, `LISTMONK_DB_*`)
- PocketBase admin credentials
- API credentials (`LISTMONK_USER`, `LISTMONK_TOKEN`, `LISTMONK_API_URL`, `POCKETBASE_*`)
- App secrets used by services (`ENCRYPTION`, `PB_INVITATION_PEPPER`, `N8N_WEBHOOK_*`, `ANTHROPIC_API_KEY`)

### `stg` — staging environment (Dockploy)

Contains only what the deployed API container needs:

- API credentials (`LISTMONK_USER`, `LISTMONK_TOKEN`, `LISTMONK_API_URL`, `POCKETBASE_*`)
- `DOCKPLOY_WEBHOOK` — URL to trigger a redeploy on Dockploy when a new `:stg` image is pushed

### `prd` — production environment (Dockploy)

Same shape as `stg` but pointing at production infrastructure:

- API credentials (production values)
- `DOCKPLOY_WEBHOOK` — URL to trigger a redeploy on Dockploy when a new `:vX.X.X` image is pushed

---

## Branch Configs

Branch configs inherit all secrets from their parent environment and override specific values. They exist to make local `act` testing safe — the `DOCKPLOY_WEBHOOK` is overridden with a mock URL (`https://httpbin.org/get`) so running workflows locally never triggers a real deployment.

| Branch config | Parent | Purpose | Key override |
|---------------|--------|---------|--------------|
| `dev_act` | `dev` | Local `act` runs targeting dev env | `OLD_DOCKPLOY_DEV_WEBHOOK` (legacy) |
| `dev_local_test` | `dev` | Local test runs against local containers | — |
| `dev_personal` | `dev` | Personal dev overrides | — |
| `stg_act` | `stg` | Local `act` runs targeting stg env | `DOCKPLOY_WEBHOOK=https://httpbin.org/get` |
| `prd_act` | `prd` | Local `act` runs targeting prd env | `DOCKPLOY_WEBHOOK=https://httpbin.org/get` |

---

## Service Tokens

Each environment has a **service token** — a read-only credential scoped to a single config. Service tokens cannot write secrets or access other environments.

| Token | Scoped to | Stored in | Used by |
|-------|-----------|-----------|---------|
| `DOPPLER_TOKEN_STG` | `stg` config | `stg_act` (Doppler) + GitHub secret | `deploy-stg.yml`, `ci.yml`, `release.yml` test job |
| `DOPPLER_TOKEN_PRD` | `prd` config | `prd_act` (Doppler) + GitHub secret | `release.yml` release job |

Tokens are stored in the `_act` branch configs so that local `act` runs can inject them into the container the same way GitHub Actions does.

To rotate a token:

```bash
# Create a new token for the config
doppler configs tokens create "act-local" --config stg --project prospect --plain

# Update the stored value in the branch config and GitHub
doppler secrets set DOPPLER_TOKEN_STG=<new-token> --config stg_act --project prospect
gh secret set DOPPLER_TOKEN_STG --body "<new-token>" -R ailianbr/prospect
```

---

## How a Workflow Consumes Secrets

Every workflow step that needs secrets does:

```yaml
run: doppler run -- <command>
env:
  DOPPLER_TOKEN: ${{ secrets.DOPPLER_TOKEN_STG }}
```

The `DOPPLER_TOKEN` env var is the only thing the Doppler CLI needs to authenticate. It then injects all secrets from the corresponding config into the process environment before the command runs.

For values that need shell expansion (like the deploy webhook curl), the pattern is:

```yaml
run: doppler run -- sh -c 'curl -s -X GET "$DOCKPLOY_WEBHOOK"'
env:
  DOPPLER_TOKEN: ${{ secrets.DOPPLER_TOKEN_STG }}
```

The `sh -c` wrapper ensures Doppler injects `$DOCKPLOY_WEBHOOK` before the shell evaluates it. Without the wrapper, bash expands `$DOCKPLOY_WEBHOOK` before Doppler runs and the value arrives empty.

---

## GitHub Secrets

Only two secrets exist in the GitHub repository:

| Secret | Value |
|--------|-------|
| `DOPPLER_TOKEN_STG` | Service token for the `stg` Doppler config |
| `DOPPLER_TOKEN_PRD` | Service token for the `prd` Doppler config |

`GITHUB_TOKEN` is auto-generated by GitHub Actions per run (used for GHCR image pushes) and does not need to be configured.

---

## Doppler Setup Reference

### Local `doppler.yaml` mapping (gitignored)

```
repo root     → prospect / dev_act
services/api/ → prospect / dev_local_test
```

### Recreating branch configs from scratch

```bash
# stg_act
doppler configs create stg_act --project prospect
doppler secrets set DOCKPLOY_WEBHOOK=https://httpbin.org/get --config stg_act --project prospect
STG_TOKEN=$(doppler configs tokens create "act-local" --config stg --project prospect --plain)
doppler secrets set DOPPLER_TOKEN_STG="$STG_TOKEN" --config stg_act --project prospect
gh secret set DOPPLER_TOKEN_STG --body "$STG_TOKEN" -R ailianbr/prospect

# prd_act
doppler configs create prd_act --project prospect
doppler secrets set DOCKPLOY_WEBHOOK=https://httpbin.org/get --config prd_act --project prospect
PRD_TOKEN=$(doppler configs tokens create "act-local" --config prd --project prospect --plain)
doppler secrets set DOPPLER_TOKEN_PRD="$PRD_TOKEN" --config prd_act --project prospect
gh secret set DOPPLER_TOKEN_PRD --body "$PRD_TOKEN" -R ailianbr/prospect
```
