from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # LLM — LLM_PROVIDER: auto | heuristic | anthropic | openai | ilmu
    llm_provider: str = "auto"

    anthropic_api_key: str | None = None
    anthropic_parse_model: str = "claude-3-5-haiku-20241022"
    anthropic_analysis_model: str = "claude-3-5-sonnet-20241022"

    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_parse_model: str = "gpt-4o-mini"
    openai_analysis_model: str = "gpt-4o"

    ilmu_api_key: str | None = None
    ilmu_base_url: str = "https://api.ilmu.ai/v1"
    ilmu_parse_model: str = "ilmu-nemo-nano"
    ilmu_analysis_model: str = "nemo-super"

    database_url: str | None = None
    neon_database_url: str | None = None
    supabase_url: str | None = None
    supabase_key: str | None = None
    upstash_redis_rest_url: str | None = None
    upstash_redis_rest_token: str | None = None
    redis_url: str | None = None

    slack_bot_token: str | None = None
    slack_signing_secret: str | None = None
    slack_app_id: str | None = None
    slack_channel_id: str | None = None
    # Comma-separated Slack user IDs bootstrapped as admins (no DB entry needed)
    # e.g. SLACK_ADMIN_USER_IDS=U012ABC,U034DEF
    slack_admin_user_ids: str = ""
    # HITL decision window — auto-expires after this many minutes
    hitl_timeout_minutes: int = 30

    # ── Security ──────────────────────────────────────────────────────────────
    # Bearer token required on /agent/* and /audit/* routes.
    # Unset in development = unauthenticated access allowed.
    # In production this MUST be set — the server returns 500 if it is not.
    api_key: str | None = None

    # Comma-separated list of allowed CORS origins.
    # e.g. ALLOWED_ORIGINS=https://app.nexusflow.ai,https://www.nexusflow.ai
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Rate limiting — requests per IP per minute.
    # rate_limit_orchestrate_per_minute applies only to /agent/orchestrate (LLM calls).
    rate_limit_per_minute: int = 60
    rate_limit_orchestrate_per_minute: int = 10

    # ── Logging ───────────────────────────────────────────────────────────────
    # "json" emits structured JSON to stdout (CloudWatch / ECS awslogs driver).
    # "text" uses the standard human-readable format for local development.
    log_format: str = "text"

    # ── OpenTelemetry ─────────────────────────────────────────────────────────
    # Set OTEL_EXPORTER_OTLP_ENDPOINT to activate distributed tracing.
    # Example (ADOT sidecar): http://localhost:4318/v1/traces
    otel_service_name: str = "nexusflow-api"
    otel_exporter_otlp_endpoint: str | None = None

    # ── Redis reliability ─────────────────────────────────────────────────────
    redis_max_retries: int = 3
    redis_retry_interval_s: float = 1.0

    # ── LLM observability (Langfuse) ──────────────────────────────────────────
    # Set LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY to enable tracing.
    # Traces are sent to LANGFUSE_HOST (default: Langfuse Cloud).
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    # ── Microsoft Teams HITL ──────────────────────────────────────────────────
    # Incoming webhook URL for the Teams channel that receives HITL alerts.
    # When set, HITL alerts are posted to Teams in addition to (or instead of) Slack.
    teams_hitl_webhook_url: str | None = None

    # ── Multi-tenancy ─────────────────────────────────────────────────────────
    # HTTP header used to identify the tenant/organisation.
    # Clients pass this on every request: X-Org-ID: acme
    org_id_header: str = "X-Org-ID"
    default_org_id: str = "default"

    # ── VidStega audit trail ──────────────────────────────────────────────────
    # HMAC-SHA256 signing secret for tamper-proof LSB steganography receipts.
    vidstega_signing_secret: str = "change-me-in-production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
