# import os
import os
# import secrets
import secrets
# from dataclasses import dataclass
from dataclasses import dataclass
# from functools import lru_cache
from functools import lru_cache

# from dotenv import load_dotenv
from dotenv import load_dotenv


# load_dotenv()
load_dotenv()


# def _parse_origins(raw: str | None) -> list[str]:
def _parse_origins(raw: str | None) -> list[str]:
    # if not raw:
    if not raw:
        # return []
        return []
    # return [item.strip() for item in raw.split(",") if item.strip()]
    return [item.strip() for item in raw.split(",") if item.strip()]


# def _as_bool(raw: str | None, default: bool) -> bool:
def _as_bool(raw: str | None, default: bool) -> bool:
    # if raw is None:
    if raw is None:
        # return default
        return default
    # return raw.strip().lower() in {"1", "true", "yes", "on"}
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# def _as_int(raw: str | None, default: int) -> int:
def _as_int(raw: str | None, default: int) -> int:
    # try:
    try:
        # return int(raw) if raw is not None else default
        return int(raw) if raw is not None else default
    # except (TypeError, ValueError):
    except (TypeError, ValueError):
        # return default
        return default


# @dataclass(frozen=True)
@dataclass(frozen=True)
# class Settings:
class Settings:
    # app_name: str
    app_name: str
    # env: str
    env: str
    # allowed_origins: list[str]
    allowed_origins: list[str]

    # epic_client_id: str
    epic_client_id: str
    # epic_redirect_uri: str
    epic_redirect_uri: str
    # epic_authorize_url: str
    epic_authorize_url: str
    # epic_token_url: str
    epic_token_url: str
    # epic_aud: str
    epic_aud: str
    # epic_scope: str
    epic_scope: str

    # oauth_state_ttl_sec: int
    oauth_state_ttl_sec: int
    # workflow_cache_ttl_sec: int
    workflow_cache_ttl_sec: int

    # redis_url: str
    redis_url: str
    # workflow_cache_key_prefix: str
    workflow_cache_key_prefix: str
    # workflow_cache_encrypt: bool
    workflow_cache_encrypt: bool
    # context_encryption_key: str
    context_encryption_key: str
    # connectors_file: str
    connectors_file: str
    # internal_api_key: str
    internal_api_key: str
    # ctx_cache_ttl_sec: int
    ctx_cache_ttl_sec: int
    # token_cache_ttl_sec: int
    token_cache_ttl_sec: int
    # prompt_cache_ttl_sec: int
    prompt_cache_ttl_sec: int
    # state_signing_key: str
    state_signing_key: str

    # consent_required: bool
    consent_required: bool
    # consent_session_ttl_sec: int
    consent_session_ttl_sec: int
    # preflight_pain_threshold: int
    preflight_pain_threshold: int
    # voice_asr_mode: str
    voice_asr_mode: str
    # riva_grpc_target: str
    riva_grpc_target: str
    # riva_use_ssl: bool
    riva_use_ssl: bool
    # riva_language_code: str
    riva_language_code: str
    # riva_sample_rate_hz: int
    riva_sample_rate_hz: int
    # riva_asr_http_url: str
    riva_asr_http_url: str


# def _default_fernet_key() -> str:
def _default_fernet_key() -> str:
    # # If operator does not set a key yet, this keeps local development running.
    # If operator does not set a key yet, this keeps local development running.
    # # In production, set CONTEXT_ENCRYPTION_KEY explicitly so tokens survive restarts.
    # In production, set CONTEXT_ENCRYPTION_KEY explicitly so tokens survive restarts.
    # return secrets.token_urlsafe(32)
    return secrets.token_urlsafe(32)


# @lru_cache(maxsize=1)
@lru_cache(maxsize=1)
# def get_settings() -> Settings:
def get_settings() -> Settings:
    # return Settings(
    return Settings(
        # app_name=os.getenv("APP_NAME", "Veldooc Backend"),
        app_name=os.getenv("APP_NAME", "Veldooc Backend"),
        # env=os.getenv("ENV", "development"),
        env=os.getenv("ENV", "development"),
        # allowed_origins=_parse_origins(os.getenv("ALLOWED_ORIGINS")),
        allowed_origins=_parse_origins(os.getenv("ALLOWED_ORIGINS")),
        # epic_client_id=os.getenv("EPIC_CLIENT_ID", ""),
        epic_client_id=os.getenv("EPIC_CLIENT_ID", ""),
        # epic_redirect_uri=os.getenv("EPIC_REDIRECT_URI", ""),
        epic_redirect_uri=os.getenv("EPIC_REDIRECT_URI", ""),
        # epic_authorize_url=os.getenv(
        epic_authorize_url=os.getenv(
            # "EPIC_AUTHORIZE_URL",
            "EPIC_AUTHORIZE_URL",
            # "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize",
            "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize",
        # ),
        ),
        # epic_token_url=os.getenv(
        epic_token_url=os.getenv(
            # "EPIC_TOKEN_URL",
            "EPIC_TOKEN_URL",
            # "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token",
            "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token",
        # ),
        ),
        # epic_aud=os.getenv(
        epic_aud=os.getenv(
            # "EPIC_AUD",
            "EPIC_AUD",
            # "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4",
            "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4",
        # ),
        ),
        # epic_scope=os.getenv(
        epic_scope=os.getenv(
            # "EPIC_SCOPE",
            "EPIC_SCOPE",
            # "openid fhirUser launch/patient patient/*.read",
            "openid fhirUser launch/patient patient/*.read",
        # ),
        ),
        # oauth_state_ttl_sec=_as_int(os.getenv("OAUTH_STATE_TTL_SEC"), 600),
        oauth_state_ttl_sec=_as_int(os.getenv("OAUTH_STATE_TTL_SEC"), 600),
        # workflow_cache_ttl_sec=_as_int(os.getenv("WORKFLOW_CACHE_TTL_SEC"), 300),
        workflow_cache_ttl_sec=_as_int(os.getenv("WORKFLOW_CACHE_TTL_SEC"), 300),
        # redis_url=os.getenv("REDIS_URL", ""),
        redis_url=os.getenv("REDIS_URL", ""),
        # workflow_cache_key_prefix=os.getenv("WORKFLOW_CACHE_KEY_PREFIX", "ctx"),
        workflow_cache_key_prefix=os.getenv("WORKFLOW_CACHE_KEY_PREFIX", "ctx"),
        # workflow_cache_encrypt=_as_bool(os.getenv("WORKFLOW_CACHE_ENCRYPT"), True),
        workflow_cache_encrypt=_as_bool(os.getenv("WORKFLOW_CACHE_ENCRYPT"), True),
        # context_encryption_key=os.getenv("CONTEXT_ENCRYPTION_KEY", _default_fernet_key()),
        context_encryption_key=os.getenv("CONTEXT_ENCRYPTION_KEY", _default_fernet_key()),
        # connectors_file=os.getenv("CONNECTORS_FILE", os.path.join(os.getcwd(), "docs", "connectors.json")),
        connectors_file=os.getenv("CONNECTORS_FILE", os.path.join(os.getcwd(), "docs", "connectors.json")),
        # internal_api_key=os.getenv("INTERNAL_API_KEY", "dev-internal-key"),
        internal_api_key=os.getenv("INTERNAL_API_KEY", "dev-internal-key"),
        # ctx_cache_ttl_sec=_as_int(os.getenv("CTX_CACHE_TTL_SEC"), 300),
        ctx_cache_ttl_sec=_as_int(os.getenv("CTX_CACHE_TTL_SEC"), 300),
        # token_cache_ttl_sec=_as_int(os.getenv("TOKEN_CACHE_TTL_SEC"), 1800),
        token_cache_ttl_sec=_as_int(os.getenv("TOKEN_CACHE_TTL_SEC"), 1800),
        # prompt_cache_ttl_sec=_as_int(os.getenv("PROMPT_CACHE_TTL_SEC"), 1800),
        prompt_cache_ttl_sec=_as_int(os.getenv("PROMPT_CACHE_TTL_SEC"), 1800),
        # state_signing_key=os.getenv("STATE_SIGNING_KEY", _default_fernet_key()),
        state_signing_key=os.getenv("STATE_SIGNING_KEY", _default_fernet_key()),
        # consent_required=_as_bool(os.getenv("CONSENT_REQUIRED"), True),
        consent_required=_as_bool(os.getenv("CONSENT_REQUIRED"), True),
        # consent_session_ttl_sec=_as_int(os.getenv("CONSENT_SESSION_TTL_SEC"), 3600),
        consent_session_ttl_sec=_as_int(os.getenv("CONSENT_SESSION_TTL_SEC"), 3600),
        # preflight_pain_threshold=_as_int(os.getenv("PREFLIGHT_PAIN_THRESHOLD"), 7),
        preflight_pain_threshold=_as_int(os.getenv("PREFLIGHT_PAIN_THRESHOLD"), 7),
        # voice_asr_mode=os.getenv("VOICE_ASR_MODE", "riva_grpc"),
        voice_asr_mode=os.getenv("VOICE_ASR_MODE", "riva_grpc"),
        # riva_grpc_target=os.getenv("RIVA_GRPC_TARGET", "localhost:50051"),
        riva_grpc_target=os.getenv("RIVA_GRPC_TARGET", "localhost:50051"),
        # riva_use_ssl=_as_bool(os.getenv("RIVA_USE_SSL"), False),
        riva_use_ssl=_as_bool(os.getenv("RIVA_USE_SSL"), False),
        # riva_language_code=os.getenv("RIVA_LANGUAGE_CODE", "en-US"),
        riva_language_code=os.getenv("RIVA_LANGUAGE_CODE", "en-US"),
        # riva_sample_rate_hz=_as_int(os.getenv("RIVA_SAMPLE_RATE_HZ"), 16000),
        riva_sample_rate_hz=_as_int(os.getenv("RIVA_SAMPLE_RATE_HZ"), 16000),
        # riva_asr_http_url=os.getenv("RIVA_ASR_HTTP_URL", "http://localhost:8010/v1/asr/transcribe"),
        riva_asr_http_url=os.getenv("RIVA_ASR_HTTP_URL", "http://localhost:8010/v1/asr/transcribe"),
    # )
    )
