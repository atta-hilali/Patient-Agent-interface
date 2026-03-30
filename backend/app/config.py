import os
import secrets
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


def _parse_origins(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [_clean_string(item) for item in raw.split(",") if _clean_string(item)]


def _clean_string(raw: str | None) -> str:
    if raw is None:
        return ""
    value = raw.strip()
    if len(value) >= 2 and ((value[0] == value[-1] == "'") or (value[0] == value[-1] == '"')):
        value = value[1:-1].strip()
    return value


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
    redis_required: bool
    workflow_cache_key_prefix: str
    workflow_cache_encrypt: bool
    context_encryption_key: str

    hl7_mllp_enabled: bool
    hl7_mllp_host: str
    hl7_mllp_port: int
    hl7_mllp_source_id: str

    consent_required: bool
    consent_session_ttl_sec: int
    preflight_pain_threshold: int

    asr_base_url: str
    asr_health_path: str
    asr_transcribe_path: str
    asr_default_language: str
    asr_timeout_sec: int
    asr_auth_header: str
    asr_auth_token: str
    asr_verify_tls: bool


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
        epic_client_id=_clean_string(os.getenv("EPIC_CLIENT_ID", "")),
        epic_redirect_uri=_clean_string(os.getenv("EPIC_REDIRECT_URI", "")),
        epic_authorize_url=_clean_string(os.getenv(
            "EPIC_AUTHORIZE_URL",
            "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize",
        )),
        epic_token_url=_clean_string(os.getenv(
            "EPIC_TOKEN_URL",
            "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token",
        )),
        epic_aud=_clean_string(os.getenv(
            "EPIC_AUD",
            "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4",
        )),
        epic_scope=_clean_string(os.getenv(
            "EPIC_SCOPE",
            "openid fhirUser launch/patient patient/*.read",
        )),
        oauth_state_ttl_sec=_as_int(os.getenv("OAUTH_STATE_TTL_SEC"), 600),
        workflow_cache_ttl_sec=_as_int(os.getenv("WORKFLOW_CACHE_TTL_SEC"), 300),
        redis_url=_clean_string(os.getenv("REDIS_URL", "")),
        redis_required=_as_bool(os.getenv("REDIS_REQUIRED"), False),
        workflow_cache_key_prefix=_clean_string(os.getenv("WORKFLOW_CACHE_KEY_PREFIX", "ctx")),
        workflow_cache_encrypt=_as_bool(os.getenv("WORKFLOW_CACHE_ENCRYPT"), True),
        context_encryption_key=_clean_string(os.getenv("CONTEXT_ENCRYPTION_KEY", _default_fernet_key())),
        hl7_mllp_enabled=_as_bool(os.getenv("HL7_MLLP_ENABLED"), False),
        hl7_mllp_host=_clean_string(os.getenv("HL7_MLLP_HOST", "0.0.0.0")),
        hl7_mllp_port=_as_int(os.getenv("HL7_MLLP_PORT"), 2575),
        hl7_mllp_source_id=_clean_string(os.getenv("HL7_MLLP_SOURCE_ID", "hl7-mllp")),
        consent_required=_as_bool(os.getenv("CONSENT_REQUIRED"), True),
        consent_session_ttl_sec=_as_int(os.getenv("CONSENT_SESSION_TTL_SEC"), 3600),
        preflight_pain_threshold=_as_int(os.getenv("PREFLIGHT_PAIN_THRESHOLD"), 7),
        asr_base_url=_clean_string(os.getenv("ASR_BASE_URL", "")),
        asr_health_path=_clean_string(os.getenv("ASR_HEALTH_PATH", "/v1/health/ready")),
        asr_transcribe_path=_clean_string(os.getenv("ASR_TRANSCRIBE_PATH", "/v1/audio/transcriptions")),
        asr_default_language=_clean_string(os.getenv("ASR_DEFAULT_LANGUAGE", "en-US")),
        asr_timeout_sec=_as_int(os.getenv("ASR_TIMEOUT_SEC"), 60),
        asr_auth_header=_clean_string(os.getenv("ASR_AUTH_HEADER", "Authorization")),
        asr_auth_token=_clean_string(os.getenv("ASR_AUTH_TOKEN", "")),
        asr_verify_tls=_as_bool(os.getenv("ASR_VERIFY_TLS"), True),
    )
