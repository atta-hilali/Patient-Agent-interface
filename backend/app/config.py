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
    state_signing_key: str
    workflow_cache_ttl_sec: int

    redis_url: str
    redis_required: bool
    workflow_cache_key_prefix: str
    workflow_cache_encrypt: bool
    context_encryption_key: str
    ctx_cache_ttl_sec: int
    token_cache_ttl_sec: int
    prompt_cache_ttl_sec: int

    hl7_mllp_enabled: bool
    hl7_mllp_host: str
    hl7_mllp_port: int
    hl7_mllp_source_id: str

    connectors_file: str
    internal_api_key: str

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
    voice_asr_mode: str
    riva_asr_http_url: str
    riva_grpc_target: str
    riva_use_ssl: bool
    riva_sample_rate_hz: int
    riva_language_code: str

    nemoguard_content_safety_url: str
    nemoguard_topic_control_url: str
    nemoguard_topic_dir: str
    nemoguard_enabled: bool
    nemoguard_content_enabled: bool
    nemoguard_topic_enabled: bool
    nemoguard_fail_open: bool
    nemoguard_strict_order: bool
    nemoguard_content_model: str
    nemoguard_topic_model: str

    medgemma_base_url: str
    medgemma_api_key: str
    medgemma_mode: str
    medgemma_mvp_model: str
    medgemma_sprint3_model: str
    medgemma_max_tokens: int

    tts_nim_url: str


def _default_fernet_key() -> str:
    # If operator does not set a key yet, this keeps local development running.
    # In production, set CONTEXT_ENCRYPTION_KEY explicitly so tokens survive restarts.
    return secrets.token_urlsafe(32)


def _default_state_signing_key() -> str:
    # Keep local development simple; set STATE_SIGNING_KEY explicitly in production.
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
        state_signing_key=_clean_string(os.getenv("STATE_SIGNING_KEY", _default_state_signing_key())),
        workflow_cache_ttl_sec=_as_int(os.getenv("WORKFLOW_CACHE_TTL_SEC"), 300),
        redis_url=_clean_string(os.getenv("REDIS_URL", "")),
        redis_required=_as_bool(os.getenv("REDIS_REQUIRED"), False),
        workflow_cache_key_prefix=_clean_string(os.getenv("WORKFLOW_CACHE_KEY_PREFIX", "ctx")),
        workflow_cache_encrypt=_as_bool(os.getenv("WORKFLOW_CACHE_ENCRYPT"), True),
        context_encryption_key=_clean_string(os.getenv("CONTEXT_ENCRYPTION_KEY", _default_fernet_key())),
        ctx_cache_ttl_sec=_as_int(os.getenv("CTX_CACHE_TTL_SEC"), 300),
        token_cache_ttl_sec=_as_int(os.getenv("TOKEN_CACHE_TTL_SEC"), 900),
        prompt_cache_ttl_sec=_as_int(os.getenv("PROMPT_CACHE_TTL_SEC"), 300),
        hl7_mllp_enabled=_as_bool(os.getenv("HL7_MLLP_ENABLED"), False),
        hl7_mllp_host=_clean_string(os.getenv("HL7_MLLP_HOST", "0.0.0.0")),
        hl7_mllp_port=_as_int(os.getenv("HL7_MLLP_PORT"), 2575),
        hl7_mllp_source_id=_clean_string(os.getenv("HL7_MLLP_SOURCE_ID", "hl7-mllp")),
        connectors_file=_clean_string(os.getenv("CONNECTORS_FILE", "docs/connectors.json")),
        internal_api_key=_clean_string(os.getenv("INTERNAL_API_KEY", "dev-internal-key")),
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
        voice_asr_mode=_clean_string(os.getenv("VOICE_ASR_MODE", "http_chunk")),
        riva_asr_http_url=_clean_string(os.getenv("RIVA_ASR_HTTP_URL", "http://127.0.0.1:9001/v1/asr")),
        riva_grpc_target=_clean_string(os.getenv("RIVA_GRPC_TARGET", "127.0.0.1:50052")),
        riva_use_ssl=_as_bool(os.getenv("RIVA_USE_SSL"), False),
        riva_sample_rate_hz=_as_int(os.getenv("RIVA_SAMPLE_RATE_HZ"), 16000),
        riva_language_code=_clean_string(os.getenv("RIVA_LANGUAGE_CODE", "en-US")),
        nemoguard_content_safety_url=_clean_string(
            os.getenv("NEMOGUARD_CONTENT_SAFETY_URL", "http://127.0.0.1:8002/v1/guardrail")
        ),
        nemoguard_topic_control_url=_clean_string(
            os.getenv("NEMOGUARD_TOPIC_CONTROL_URL", "http://127.0.0.1:8003/v1/guardrail")
        ),
        nemoguard_topic_dir=_clean_string(os.getenv("NEMOGUARD_TOPIC_DIR", "config/topics")),
        nemoguard_enabled=_as_bool(os.getenv("NEMOGUARD_ENABLED"), True),
        nemoguard_content_enabled=_as_bool(os.getenv("NEMOGUARD_CONTENT_ENABLED"), True),
        nemoguard_topic_enabled=_as_bool(os.getenv("NEMOGUARD_TOPIC_ENABLED"), True),
        nemoguard_fail_open=_as_bool(os.getenv("NEMOGUARD_FAIL_OPEN"), True),
        nemoguard_strict_order=_as_bool(os.getenv("NEMOGUARD_STRICT_ORDER"), True),
        nemoguard_content_model=_clean_string(os.getenv("NEMOGUARD_CONTENT_MODEL", "llama-nemotron-safety-guard-v2")),
        nemoguard_topic_model=_clean_string(os.getenv("NEMOGUARD_TOPIC_MODEL", "llama-nemotron-topic-guard-v1")),
        medgemma_base_url=_clean_string(os.getenv("MEDGEMMA_BASE_URL", "http://127.0.0.1:8001/v1")),
        medgemma_api_key=_clean_string(os.getenv("MEDGEMMA_API_KEY", "not-used")),
        medgemma_mode=_clean_string(os.getenv("MEDGEMMA_MODE", "mvp")),
        medgemma_mvp_model=_clean_string(os.getenv("MEDGEMMA_MVP_MODEL", "google/medgemma-4b-it")),
        medgemma_sprint3_model=_clean_string(os.getenv("MEDGEMMA_SPRINT3_MODEL", "google/medgemma-27b-it")),
        medgemma_max_tokens=_as_int(os.getenv("MEDGEMMA_MAX_TOKENS"), 1024),
        tts_nim_url=_clean_string(os.getenv("TTS_NIM_URL", "http://127.0.0.1:8000/v1/tts")),
    )
