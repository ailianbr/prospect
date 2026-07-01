# Workflow Alignment — stage + prod redeploy

> **Status:** PROPOSED — for review before implementation. Drafted 2026-06-25.
> **Scope:** `prospect` only. Aligns this repo with the platform conventions now established by
> `conectai` (the `python_services` rebuild) ahead of the stage + prod redeploy.
> **Companion docs:** [`workflows.md`](workflows.md) (current CI/CD), [`doppler-architecture.md`](doppler-architecture.md) (secrets).

## Context

prospect is being redeployed into **two environments — stage and prod**. This is a good moment to
close the small gaps between how prospect is wired and how the rest of the platform now works, so
the Dockploy apps we stand up are consistent with conectai and integration-service from day one.

**Good news first:** prospect is already mostly aligned, and on some axes it is *ahead* of conectai:

| Already "our way" | Notes |
|---|---|
| Secrets via Doppler, three root configs `dev` / `stg` / `prd` | exactly the platform model — nothing to change here |
| `pydantic-settings` config | standard |
| release-please + Conventional Commits + GHCR publish | conectai does **not** have this yet |
| OpenTelemetry instrumentation + observability docs | standard |
| Multi-stage Dockerfile + per-env compose (`stg` / `prd`) | standard |
| Dockploy deploy via pull-based webhook | standard |
| Local CI testing with `act` (`_act` branch configs) | a nice extra |

So this is a **tune-up, not a rebuild**. Two slices follow: **P0 — environment-naming hygiene**
(blocks a clean 2-env redeploy) and **P1 — CI hardening**. Toolchain convergence (P2) is explicitly
deferred.

---

## Change Definition

```
Task:                 Align prospect's deploy artifacts and CI with the platform workflow,
                      so the stage + prod redeploy is consistent with conectai.
Classification:       ARCHITECTURE (deploy topology + CI gate) + DOCS
Affected repos:       prospect
Affected files:       docker-compose.stg.yml, .github/workflows/{deploy-dev.yml→deploy-stg.yml, ci.yml},
                      services/api/pyproject.toml, services/api/app/config (ENVIRONMENT flag),
                      docs/workflows.md, docs/doppler-architecture.md, README.md
                      (P1 hermetic tests: services/api/tests/* — TBD during implementation)
Architectural layer:  CI/CD + container packaging + service config
Pattern precedent:    conectai docs/ENVIRONMENTS.md + ailian-platform docs/standards/environments.md;
                      integration-service CI (mypy + compose-validate)
ADR needed:           No — follows the existing platform environments standard; no new decision.
Multi-tenancy risk:   No (deploy/CI only; no data-path change)
Idempotency risk:     No
New dependencies:     mypy (dev), no new runtime deps
```

---

## The core problem (P0): the layers disagree on which environment is which

prospect's **Doppler layer is already correct** — `stg` is a first-class config, scoped token and
all. But the **Docker artifacts still carry `dev` labels** for what everyone agrees is *staging*:

| Layer | Says it's… | Reality |
|---|---|---|
| Doppler config (`stg`) | **stg** | ✅ correct |
| Deploy workflow file | `deploy-**dev**.yml` | it's the staging deploy |
| Image tag built/pulled | `monk-api:**dev**` | it's the staging image |
| `docker-compose.stg.yml` container/volume/alias prefix | `**dev**_listmonk_api`, `dev_…` | it's the staging stack |
| Concurrency group | `stg-integration-tests` | ✅ correct |

The platform standard (conectai `docs/ENVIRONMENTS.md`) is unambiguous:

| Env | Doppler config | Infra | Rule |
|---|---|---|---|
| **dev** | `dev` (+ `dev_personal`) | **local, disposable** | never depends on deployed infra |
| **stg** | `stg` | deployed prod-like clone, prefixed `stg-` | never developed on directly; changes via PR/CI |
| **prd** | `prd` | production | production |

By that rule, **`dev` should mean "local only."** Anything deployed to the Dockploy dev server is
**stg** and should be labeled `stg`. Today the staging stack is wearing `dev` clothes, which is
exactly the kind of ambiguity that leads to "is this dev or stage?" incidents — and if we redeploy
as-is, our brand-new staging stack ships as `dev_listmonk_api`.

### P0 change list

All renames; no behavioral change. Because we are standing up the Dockploy apps fresh, this is the
cheapest possible moment to do it.

1. **`docker-compose.stg.yml`** — rename the `dev_` prefix to `stg_` everywhere:
   - container names `dev_listmonk_api` → `stg_listmonk_api` (and `_db`, `_app`, etc.)
   - volumes `dev_listmonk_api_db`, `dev_listmonk-data` → `stg_…`
   - network aliases `dev_*` → `stg_*`
   - the bridge network name is already `listmonk_stage_bridge` ✅ (keeps the prod-collision fix)
   - image `ghcr.io/ailianbr/monk-api:dev` → `:stg`
   - update the header comment (it currently says "dev\_ prefix")
2. **`.github/workflows/deploy-dev.yml` → `deploy-stg.yml`** — same trigger (`push: development`),
   same STG token; only the build tag changes `:dev` → `:stg`. Rename the `deploy-dev` job → `deploy-stg`.
3. **`services/api/app` config** — add an `ENVIRONMENT` field (`dev` | `stg` | `prd`, `test` under
   pytest) to the pydantic settings, with `is_dev` / `is_stg` / `is_prod` helpers, mirroring
   conectai's `config.py`. Set `ENVIRONMENT` per Doppler config. This gives us a single switch to
   gate behavior (e.g. verbose logging in dev, OTEL sampling) instead of inferring it.
4. **Docs** — update `docs/workflows.md` (diagram + "Deploy Dev" → "Deploy Staging"),
   `docs/doppler-architecture.md` lines referencing the `:dev` image (§stg/§prd), and the README
   workflow note.

> **Decision to confirm:** the Dockploy *staging* app must be pointed at the new `:stg` tag (and the
> prod app at `:vX.Y.Z` / `:latest`, which is already the case). Since we're recreating the apps,
> this is a one-time setting, not a migration.

---

## P1 — CI hardening

Three gaps versus conectai's CI (`ruff` + **mypy** + `pytest` + **compose-validate**, all hermetic):

### 1. No type-checking
prospect's CI runs `ruff check` + `pytest` only. **Add `mypy`** (dev dependency + a `typecheck`
taskipy task + a CI step). Because the codebase hasn't been type-checked before, expect an initial
cleanup pass; we can land it **non-blocking** first (report-only) and flip it to a required gate once
green, so it doesn't stall the redeploy.

### 2. CI mutates files during the test run
`pyproject.toml` wires `pre_test = 'task format'` (which runs `ruff check --fix` then `ruff format`).
So `task test` **rewrites source** before running — fine locally, wrong in CI (a check that edits
what it's checking). Two fixes:
- add a CI-only `ci_test` task (or call `pytest` directly in the workflow) that skips the `pre_test`
  format hook;
- make the `lint` task also verify formatting (`ruff format --check`), so formatting drift is
  actually caught on PRs (today `lint` is `ruff check` only — formatting is never gated).

### 3. Compose files aren't validated
Add a `docker compose -f docker-compose.stg.yml config -q` (and `.prd`) step to `ci.yml` so a broken
compose file fails the PR instead of the Dockploy redeploy. Cheap, no secrets needed.

### 4. (Larger, optional within P1) Decouple unit tests from STG secrets + live infra
Today **every** test hits live Listmonk + PocketBase, so `ci.yml` needs `DOPPLER_TOKEN_STG` just to
run unit tests — meaning a PR's test run reaches into the staging environment (and can mutate it).
conectai's tests are hermetic (in-memory + mocked HTTP via `pytest-httpx`), so CI needs no secrets
and can't touch a deployed env.

Proposed **incremental** path (not a big-bang rewrite):
- introduce a hermetic **unit** layer that mocks the Listmonk and PocketBase HTTP clients (the two
  seams in `sessions.py` / `interface.py`);
- keep the existing live tests as a separate, opt-in **integration** job that still uses the STG
  token, gated/labeled so normal PRs don't depend on it.

This is the deepest *quality* convergence and the one most worth doing — but it can land after P0 +
the quick P1 items, so it doesn't block the redeploy.

---

## Out of scope (deferred — P2 toolchain convergence)

Not blocking the redeploy; tracked for later. PDM works; don't let this gate stage/prod.

| Item | Platform norm | prospect today | Why deferred |
|---|---|---|---|
| Package manager | `uv` | PDM + taskipy | Migration touches Dockerfile + CI + lockfile; no functional gain now |
| Python version | 3.12 | **3.14** | Recommend pinning to 3.12 for platform parity, but isolate from this change |
| Devcontainer | docker-in-docker | none | Onboarding nicety, not deploy-critical |
| Dockerfile non-root user | integration-service pattern | runs as root | Light hardening; fold into the uv migration |

---

## Rollout order

1. **P0** (renames + `ENVIRONMENT` flag + docs) — land before recreating the Dockploy apps.
2. Recreate the **staging** Dockploy app on `:stg`, the **prod** app on `:vX.Y.Z`/`:latest`.
3. **P1 quick wins** (mypy report-only, compose-validate, CI-no-autoformat, format-check in lint).
4. **P1 hermetic test layer** (separate PR), then flip mypy to required.

## Verification

- `docker compose -f docker-compose.stg.yml config -q` and `.prd` parse clean; no `dev_*` names
  remain in the staging stack.
- A push to `development` builds `:stg`, the staging Dockploy app pulls it, `/` healthcheck green.
- A GitHub Release builds `:vX.Y.Z` + `:latest`, prod redeploys, healthcheck green.
- `ci.yml`: lint (incl. format-check) + typecheck + tests pass; the quick-win subset needs **no**
  `DOPPLER_TOKEN_STG` once the hermetic unit layer exists.

## Risks

| Risk | Mitigation |
|---|---|
| Renaming `dev_*` → `stg_*` orphans existing named volumes on the dev server | We're recreating the apps; if any staging volume holds data worth keeping, migrate it explicitly before teardown (PocketBase data dir). Confirm staging data is disposable. |
| Dockploy app still points at the old `:dev` tag after rename | Part of recreating the app — set the image tag to `:stg` when wiring it. |
| mypy surfaces many errors and stalls the redeploy | Land mypy **report-only** first; flip to required after a cleanup PR. |
| Hermetic test refactor is larger than it looks | Scoped to a separate PR after the redeploy; live integration tests stay as the safety net meanwhile. |
