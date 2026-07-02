from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra='ignore': the Doppler config also injects the postgres/listmonk/
    # pocketbase sidecar vars (POSTGRES_*, LISTMONK_DB_*, …); the app declares
    # only what it reads and ignores the rest instead of failing to start.
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # ── Listmonk API (the upstream this service wraps) ───────────────────────
    LISTMONK_USER: str
    LISTMONK_TOKEN: str
    LISTMONK_API_URL: str

    # ── PocketBase (tenant ownership / control plane) ────────────────────────
    POCKETBASE_BOT_EMAIL: str
    POCKETBASE_BOT_PASSWORD: str
    POCKETBASE_API_URL: str

    # ── Environment ──────────────────────────────────────────────────────────
    # Matches the Doppler config names: dev | stg | prd. Compared case-insensitively
    # via the helpers below — never read ENVIRONMENT directly.
    ENVIRONMENT: str = 'prd'

    # ── Observability / platform metadata ────────────────────────────────────
    # Empty endpoint disables OTel export (app runs without tracing). COMMIT_SHA
    # and HOSTNAME are injected by the platform (CI / Docker); they default so
    # local runs need neither.
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ''
    COMMIT_SHA: str = 'unknown'
    HOSTNAME: str = 'unknown'

    @property
    def env(self) -> str:
        return self.ENVIRONMENT.strip().lower()

    @property
    def is_dev(self) -> bool:
        return self.env == 'dev'

    @property
    def is_stg(self) -> bool:
        return self.env == 'stg'

    @property
    def is_prod(self) -> bool:
        return self.env == 'prd'


# One shared instance — import this (`from app.settings import settings`) instead of
# constructing Settings() per module, so the whole app reads env exactly once.
settings = Settings()  # type: ignore[call-arg]  # values come from env / .env
