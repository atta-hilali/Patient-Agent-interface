import os
import secrets
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


def _parse_origins(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _as_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(raw: str | None, default: int) -> int:
    try:
        return int(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str
    env: str
    allowed_origins: list[str]

    epic_client_id: str
    epic_redirect_uri: str
    epic_authorize_url: str
    epic_token_url: str
    epic_aud: str
    epic_scope: str

    oauth_state_ttl_sec: int
    workflow_cache_ttl_sec: int

    redis_url: str
    workflow_cache_key_prefix: str
    workflow_cache_encrypt: bool
    context_encryption_key: str
    connectors_file: str
    internal_api_key: str
    ctx_cache_ttl_sec: int
    token_cache_ttl_sec: int
    prompt_cache_ttl_sec: int
    state_signing_key: str

    consent_required: bool
    consent_session_ttl_sec: int
    preflight_pain_threshold: int


def _default_fernet_key() -> str:
    # If operator does not set a key yet, this keeps local development running.
    # In production, set CONTEXT_ENCRYPTION_KEY explicitly so tokens survive restarts.
    return secrets.token_urlsafe(32)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "Veldooc Backend"),
        env=os.getenv("ENV", "development"),
        allowed_origins=_parse_origins(os.getenv("ALLOWED_ORIGINS")),
        epic_client_id=os.getenv("EPIC_CLIENT_ID", ""),
        epic_redirect_uri=os.getenv("EPIC_REDIRECT_URI", ""),
        epic_authorize_url=os.getenv(
            "EPIC_AUTHORIZE_URL",
            "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize",
        ),
        epic_token_url=os.getenv(
            "EPIC_TOKEN_URL",
            "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token",
        ),
        epic_aud=os.getenv(
            "EPIC_AUD",
            "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4",
        ),
        epic_scope=os.getenv(
            "EPIC_SCOPE",
            "openid fhirUser launch/patient patient/*.read",
        ),
        oauth_state_ttl_sec=_as_int(os.getenv("OAUTH_STATE_TTL_SEC"), 600),
        workflow_cache_ttl_sec=_as_int(os.getenv("WORKFLOW_CACHE_TTL_SEC"), 300),
        redis_url=os.getenv("REDIS_URL", ""),
        workflow_cache_key_prefix=os.getenv("WORKFLOW_CACHE_KEY_PREFIX", "ctx"),
        workflow_cache_encrypt=_as_bool(os.getenv("WORKFLOW_CACHE_ENCRYPT"), True),
        context_encryption_key=os.getenv("CONTEXT_ENCRYPTION_KEY", _default_fernet_key()),
        connectors_file=os.getenv("CONNECTORS_FILE", os.path.join(os.getcwd(), "docs", "connectors.json")),
        internal_api_key=os.getenv("INTERNAL_API_KEY", "dev-internal-key"),
        ctx_cache_ttl_sec=_as_int(os.getenv("CTX_CACHE_TTL_SEC"), 300),
        token_cache_ttl_sec=_as_int(os.getenv("TOKEN_CACHE_TTL_SEC"), 1800),
        prompt_cache_ttl_sec=_as_int(os.getenv("PROMPT_CACHE_TTL_SEC"), 1800),
        state_signing_key=os.getenv("STATE_SIGNING_KEY", _default_fernet_key()),
        consent_required=_as_bool(os.getenv("CONSENT_REQUIRED"), True),
        consent_session_ttl_sec=_as_int(os.getenv("CONSENT_SESSION_TTL_SEC"), 3600),
        preflight_pain_threshold=_as_int(os.getenv("PREFLIGHT_PAIN_THRESHOLD"), 7),
    )
