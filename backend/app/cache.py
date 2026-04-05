from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

from .config import Settings
from .models import AuthToken, PatientContext
from .session_cache import SessionCache

try:
    from cryptography.fernet import Fernet, InvalidToken
except Exception:  # noqa: BLE001
    Fernet = None  # type: ignore[assignment]
    InvalidToken = Exception  # type: ignore[assignment]

try:
    from redis.asyncio import Redis
except Exception:  # noqa: BLE001
    Redis = None  # type: ignore[assignment]


def _derive_fernet_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _build_fernet(secret: str) -> Fernet | None:
    if Fernet is None:
        return None
    try:
        return Fernet(secret.encode("utf-8"))
    except Exception:  # noqa: BLE001
        return Fernet(_derive_fernet_key(secret))


@dataclass
class InMemoryEntry:
    value: bytes
    expires_at: float


class WorkflowCache:
    def __init__(self, settings: Settings) -> None:
        self.ttl_sec = settings.workflow_cache_ttl_sec
        self.key_prefix = settings.workflow_cache_key_prefix
        self.encrypt_enabled = settings.workflow_cache_encrypt
        self.redis_required = settings.redis_required
        self._fernet = _build_fernet(settings.context_encryption_key) if self.encrypt_enabled else None
        self._memory: dict[str, InMemoryEntry] = {}
        self._redis: Redis | None = None

        if self.redis_required and Redis is None:
            raise RuntimeError("REDIS_REQUIRED=true but redis package is unavailable.")

        if self.redis_required and not settings.redis_url:
            raise RuntimeError("REDIS_REQUIRED=true but REDIS_URL is not configured.")

        if settings.redis_url and Redis is not None:
            try:
                self._redis = Redis.from_url(settings.redis_url, decode_responses=False)
            except Exception:  # noqa: BLE001
                if self.redis_required:
                    raise RuntimeError("Failed to initialize Redis client while REDIS_REQUIRED=true.") from None
                self._redis = None

    def cache_key(self, source_id: str, patient_id: str) -> str:
        return f"{self.key_prefix}:{source_id}:{patient_id}"

    def _cleanup_memory(self) -> None:
        now = time.time()
        expired = [key for key, item in self._memory.items() if item.expires_at <= now]
        for key in expired:
            self._memory.pop(key, None)

    def _encrypt(self, payload: dict[str, Any]) -> bytes:
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        if not self._fernet:
            return raw
        return self._fernet.encrypt(raw)

    def _decrypt(self, value: bytes) -> dict[str, Any] | None:
        raw = value
        if self._fernet:
            try:
                raw = self._fernet.decrypt(value)
            except InvalidToken:
                return None
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except Exception:  # noqa: BLE001
            return None
        return parsed if isinstance(parsed, dict) else None

    async def get(self, *, source_id: str, patient_id: str) -> dict[str, Any] | None:
        key = self.cache_key(source_id=source_id, patient_id=patient_id)

        if self._redis:
            try:
                cached = await self._redis.get(key)
                if cached:
                    if isinstance(cached, str):
                        cached = cached.encode("utf-8")
                    decoded = self._decrypt(cached)
                    if decoded:
                        return decoded
            except Exception:  # noqa: BLE001
                if self.redis_required:
                    raise RuntimeError("Redis read failed while REDIS_REQUIRED=true.") from None
                self._redis = None

        if self.redis_required:
            raise RuntimeError("Redis cache is required but unavailable.")

        self._cleanup_memory()
        item = self._memory.get(key)
        if not item:
            return None
        return self._decrypt(item.value)

    async def set(self, *, source_id: str, patient_id: str, snapshot: dict[str, Any]) -> None:
        key = self.cache_key(source_id=source_id, patient_id=patient_id)
        encoded = self._encrypt(snapshot)

        if self._redis:
            try:
                await self._redis.set(key, encoded, ex=self.ttl_sec)
                return
            except Exception:  # noqa: BLE001
                if self.redis_required:
                    raise RuntimeError("Redis write failed while REDIS_REQUIRED=true.") from None
                self._redis = None

        if self.redis_required:
            raise RuntimeError("Redis cache is required but unavailable.")

        self._cleanup_memory()
        self._memory[key] = InMemoryEntry(value=encoded, expires_at=time.time() + self.ttl_sec)

    async def exists(self, *, source_id: str, patient_id: str) -> bool:
        key = self.cache_key(source_id=source_id, patient_id=patient_id)

        if self._redis:
            try:
                return bool(await self._redis.exists(key))
            except Exception:  # noqa: BLE001
                if self.redis_required:
                    raise RuntimeError("Redis exists check failed while REDIS_REQUIRED=true.") from None
                self._redis = None

        if self.redis_required:
            raise RuntimeError("Redis cache is required but unavailable.")

        self._cleanup_memory()
        return key in self._memory

    async def ping(self) -> bool:
        if self._redis:
            try:
                result = await self._redis.ping()
                return bool(result)
            except Exception:  # noqa: BLE001
                if self.redis_required:
                    raise RuntimeError("Redis ping failed while REDIS_REQUIRED=true.") from None
                self._redis = None
        if self.redis_required:
            raise RuntimeError("Redis cache is required but unavailable.")
        return False


_session_cache_singleton: SessionCache | None = None


def get_session_cache() -> SessionCache:
    global _session_cache_singleton
    if _session_cache_singleton is None:
        from .config import get_settings

        _session_cache_singleton = SessionCache(settings=get_settings())
    return _session_cache_singleton


async def read_prompt(session_id: str) -> str:
    if not session_id:
        return ""
    prompt = await get_session_cache().get_prompt(session_id)
    return prompt or ""


async def read_context(session_id: str, patient_id: str) -> PatientContext | None:
    if not session_id or not patient_id:
        return None
    raw = await get_session_cache().get_context(session_id, patient_id)
    if not raw:
        return None
    try:
        return PatientContext.model_validate(raw)
    except Exception:  # noqa: BLE001
        return None


async def read_patient_id_for_session(session_id: str) -> str:
    if not session_id:
        return ""
    raw_token = await get_session_cache().get_token(session_id)
    if not raw_token:
        return ""
    try:
        token = AuthToken.model_validate(raw_token)
        return token.patient_id
    except Exception:  # noqa: BLE001
        if isinstance(raw_token, dict):
            return str(raw_token.get("patient_id") or raw_token.get("patient") or "")
        return ""


async def read_context_for_session(session_id: str) -> PatientContext | None:
    patient_id = await read_patient_id_for_session(session_id)
    if not patient_id:
        return None
    return await read_context(session_id, patient_id)
