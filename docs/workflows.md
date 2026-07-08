# CI/CD Workflows

Four GitHub Actions workflows handle quality checks, staging deploys, versioning,
and production releases. Secrets flow through [Doppler](doppler-architecture.md),
images are published to GHCR, and deploys are triggered via the Dockploy API
(`compose.deploy`, which forces a re-pull of the freshly-built image).

```
feat/* | fix/*  ──PR→main──►  development  ──merge→main──►  release-please PR  ──merge──►  GitHub Release
     [ci.yml]                  [deploy-stg.yml]             [release-please.yml]          [release.yml]
   lint + test               lint+test+STG deploy          version/changelog PR           test + PROD deploy
```

| Workflow | File | Trigger | Result |
|----------|------|---------|--------|
| CI | `ci.yml` | PR → `main` or `development` | lint + test (merge gate) |
| Deploy Staging | `deploy-stg.yml` | push → `development` | lint + test + deploy **staging** |
| Release Please | `release-please.yml` | push → `main` | maintains the release PR |
| Release | `release.yml` | a GitHub Release is published | test + deploy **production** |

---

## CI — Lint & Test on Pull Request

**File:** `.github/workflows/ci.yml`
**Trigger:** Any pull request targeting `main` or `development`

```
PR → main | development
  ├── lint job
  │     ├── actions/checkout@v4
  │     ├── actions/setup-python@v5 (Python 3.14)
  │     ├── pip install pdm
  │     ├── pdm install --dev
  │     └── pdm run task lint            # ruff check
  └── test job (needs: lint)
        ├── dopplerhq/cli-action@v3
        ├── pdm install --dev
        └── doppler run -- pdm run task test    # pytest + coverage
              DOPPLER_TOKEN: secrets.DOPPLER_TOKEN_STG
```

If lint or tests fail the PR is blocked. Fix locally with:

```bash
cd services/api
pdm run task format   # auto-fix formatting
pdm run task lint     # verify
doppler run -- pdm run task test
```

> Tests are integration tests that hit live Listmonk/PocketBase, so they need
> Doppler-injected credentials (the `stg` service token in CI).

---

## Deploy Staging

**File:** `.github/workflows/deploy-stg.yml`
**Trigger:** Push to `development` (i.e. once a PR is merged into it)

Runs the same lint + test gate, then builds the `:stg` image and triggers a
Dockploy redeploy of the staging stack.

```
push → development
  ├── lint job
  ├── test job (needs: lint)   → uploads coverage.xml artifact
  └── deploy-stg job (needs: test)
        ├── download coverage.xml
        ├── genbadge → badges/coverage.svg
        │     └── commit & push "chore: update coverage badge [skip ci]"
        ├── docker/login-action@v3 → ghcr.io (GITHUB_TOKEN)
        ├── docker/build-push-action@v6
        │     context: services/api
        │     tag: ghcr.io/<owner>/monk-api:stg
        └── POST admin.ailian.com.br/api/compose.deploy   # force stg redeploy (re-pulls :stg)
              x-api-key: secrets.DOKPLOY_API_KEY
```

`<owner>` is the repository owner lowercased (`ailianbr`), so the image is
`ghcr.io/ailianbr/monk-api:stg`. The coverage badge commit uses `[skip ci]` to
avoid retriggering. `concurrency: stg-integration-tests` cancels in-progress runs.

---

## Release Please — Versioning

**File:** `.github/workflows/release-please.yml`
**Trigger:** Push to `main`

Uses [release-please](https://github.com/googleapis/release-please-action) to
maintain a standing "release PR" off `main`. Based on Conventional Commits it
bumps the version in `services/api/pyproject.toml`, updates
`.release-please-manifest.json`, and regenerates `services/api/CHANGELOG.md`.

```
push → main
  └── googleapis/release-please-action@v4
        config-file:   release-please-config.json   (release-type: python, package: monk-api)
        manifest-file: .release-please-manifest.json
        token:         secrets.RELEASE_PAT
```

When the release PR is **merged**, release-please publishes a GitHub Release and
tag `monk-api-vX.Y.Z` — which is what triggers the production release below.

Version bump rules (Conventional Commits):

- `fix:` / `perf:` / `refactor:` → patch (`0.0.X`)
- `feat:` → minor (`0.X.0`)
- `feat!:` / `BREAKING CHANGE:` → major (`X.0.0`)

---

## Release — Production Deploy

**File:** `.github/workflows/release.yml`
**Trigger:** `release: published` (the tag cut by release-please), or manual `workflow_dispatch`

```
release published (tag monk-api-vX.Y.Z)
  ├── test job            # ephemeral integration tests (integration-test.yml)
  ├── verify-stg job      # smoke-gate the LIVE staging stack (public endpoints, no auth):
  │     ├── GET stg-listmonkapi…/docs + /openapi.json → 200 (monk-api serving its schema)
  │     ├── GET stg-listmonk…/ → 200 (Listmonk)
  │     └── GET stg-listmonkdb…/api/health → 200 (PocketBase)
  └── release job (needs: [test, verify-stg])
        ├── derive VERSION from tag (strip "monk-api-v"), lowercase OWNER
        ├── docker/login-action@v3 → ghcr.io (GITHUB_TOKEN)
        ├── docker/build-push-action@v6      # rebuilt from main at the release commit
        │     context: services/api
        │     tags:
        │       ghcr.io/ailianbr/monk-api:vX.Y.Z
        │       ghcr.io/ailianbr/monk-api:latest
        └── POST admin.ailian.com.br/api/compose.deploy   # force prod redeploy (re-pulls :latest)
              x-api-key: secrets.DOKPLOY_API_KEY
```

Production is **gated on live staging**: the `release` job only runs once both `test`
and `verify-stg` pass, so a broken or down staging blocks the prod build/deploy. The
prod image is **built from `main`** at the release commit (not promoted from `:stg`),
so its reported version matches the release tag.

On `workflow_dispatch` the version is read from `services/api/pyproject.toml`
instead of a tag. `concurrency: stg-integration-tests` is set with
`cancel-in-progress: false` so releases queue rather than cancel each other.

### How to cut a release

1. Merge feature work into `development` (CI gate), then merge `development` → `main`.
2. release-please opens/updates a release PR on `main`. Review and **merge** it.
3. Merging the release PR creates the GitHub Release + tag, which triggers
   `release.yml`: it smoke-checks live staging (`verify-stg`), then builds `:vX.Y.Z`
   + `:latest` and redeploys production. If staging is unhealthy the gate fails and
   prod is left untouched.
4. Verify:
   - Image appears at `ghcr.io/ailianbr/monk-api` under **Packages**
   - Release tag `monk-api-vX.Y.Z` appears under **Releases**
   - Dockploy production stack picks up the new `:latest` image

---

## Secrets & Deploy Targets

- **Doppler** holds all app secrets. CI stores GitHub secrets `DOPPLER_TOKEN_STG`
  and `DOPPLER_TOKEN_PRD` (injected into the integration tests), `RELEASE_PAT` for
  release-please, and **`DOKPLOY_API_KEY`** (the Dokploy `x-api-key`) used by the
  deploy jobs. See [doppler-architecture.md](doppler-architecture.md).
- **GHCR** (`ghcr.io/ailianbr/monk-api`) hosts the images; pushes authenticate
  with the auto-provided `GITHUB_TOKEN`.
- **Dockploy** runs the staging (`stg`) and production (`prd`) stacks. The deploy
  jobs call `POST /api/compose.deploy` (force redeploy) so the stack re-pulls the
  newly-built image — the older `DOCKPLOY_WEBHOOK` is a no-op on git-source
  composes when the git SHA is unchanged. The in-repo `docker-compose.stg.yml` /
  `docker-compose.prd.yml` describe those stacks.

---

## Git Flow

```
feature/*  ──PR──►  development  ──PR──►  main  ──release-please PR──►  release
                         ↑                  ↑
                   CI lint+test       CI lint+test
                   then STG deploy    then release PR
```

| Branch | Purpose |
|--------|---------|
| `main` | Production-ready; release-please-versioned releases only |
| `development` | Integration/staging branch — merge features here first |
| `feature/*`, `feat/*`, `fix/*` | Short-lived branches, PR into `development` |

---

## Testing Workflows Locally

Workflows can be run locally with [nektos/act](https://nektosact.com) and the
Docker runner image configured in `.actrc`.

```bash
# Run the CI lint job (same environment as GitHub Actions)
act pull_request -j lint

# Dry-run to see what would execute without running containers
act pull_request --dryrun
```

`act` uses `catthehacker/ubuntu:act-latest` (set in `.actrc`), matching the
`ubuntu-latest` runner used in CI. The deploy steps call the Dokploy
`compose.deploy` API with `DOKPLOY_API_KEY`, which isn't provided under `act`, so
local runs can't trigger a real deploy — run only the `lint`/`test` jobs locally.

> The release/deploy jobs need `GITHUB_TOKEN` with `packages: write` /
> `contents: write` scopes (auto-provided by GitHub Actions, not available under
> `act`) and live Doppler tokens — run the real deploy from GitHub Actions only.
