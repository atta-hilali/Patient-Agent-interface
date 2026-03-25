from __future__ import annotations

import json
import os
import time
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

try:
    from redis.asyncio import Redis
except Exception:  # noqa: BLE001
    Redis = None  # type: ignore[assignment]

from .config import Settings


def _derive_key(raw: str) -> bytes:
    # Ensure a 32-byte AES key; hash-like derivation keeps behavior stable across restarts
    return raw.encode("utf-8")[:32].ljust(32, b"\0")


class _MemoryEntry:
    def __init__(self, value: bytes, expires_at: float) -> None:
        self.value = value
        self.expires_at = expires_at


class SessionCache:
    """
    Session-scoped cache for Phase 1 artifacts:
      - ctx:{session_id}:{patient_id}  -> PatientContext JSON (AES-256-GCM)
      - token:{session_id}             -> AuthToken JSON (AES-256-GCM)
      - prompt:{session_id}            -> rendered system prompt (AES-256-GCM)

    Fallbacks to in-memory store when Redis is unavailable.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._key = _derive_key(settings.context_encryption_key)
        self._aesgcm = AESGCM(self._key)
        self._redis: Redis | None = None
        if settings.redis_url and Redis is not None:
            try:
                self._redis = Redis.from_url(settings.redis_url, decode_responses=False)
            except Exception:  # noqa: BLE001
                self._redis = None
        self._memory: dict[str, _MemoryEntry] = {}

    def _encrypt(self, plaintext: str) -> bytes:
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return nonce + ciphertext

    def _decrypt(self, payload: bytes) -> str | None:
        if not payload or len(payload) < 13:
            return None
        nonce, ciphertext = payload[:12], payload[12:]
        try:
            return self._aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
        except Exception:  # noqa: BLE001
            return None

    async def _write(self, key: str, value: bytes, ttl: int) -> None:
        if self._redis:
            try:
                await self._redis.set(key, value, ex=ttl)
                return
            except Exception:  # noqa: BLE001
                self._redis = None
        expires_at = time.time() + ttl
        self._memory[key] = _MemoryEntry(value=value, expires_at=expires_at)

    async def _read(self, key: str) -> bytes | None:
        if self._redis:
            try:
                cached = await self._redis.get(key)
                if cached:
                    return cached if isinstance(cached, (bytes, bytearray)) else cached.encode("utf-8")
            except Exception:  # noqa: BLE001
                self._redis = None
        now = time.time()
        item = self._memory.get(key)
        if item and item.expires_at > now:
            return item.value
        if item and item.expires_at <= now:
            self._memory.pop(key, None)
        return None

    async def set_json(self, key: str, payload: Any, ttl: int) -> None:
        encoded = self._encrypt(json.dumps(payload, separators=(",", ":"), ensure_ascii=True))
        await self._write(key, encoded, ttl)

    async def get_json(self, key: str) -> Any | None:
        raw = await self._read(key)
        if raw is None:
            return None
        decoded = self._decrypt(raw)
        if not decoded:
            return None
        try:
            return json.loads(decoded)
        except Exception:  # noqa: BLE001
            return None

    async def set_context(self, session_id: str, patient_id: str, context: Any) -> str:
        key = f"ctx:{session_id}:{patient_id}"
        await self.set_json(key, context, self.settings.ctx_cache_ttl_sec)
        return key

    async def get_context(self, session_id: str, patient_id: str) -> Any | None:
        key = f"ctx:{session_id}:{patient_id}"
        return await self.get_json(key)

    async def set_token(self, session_id: str, token: Any) -> str:
        key = f"token:{session_id}"
        await self.set_json(key, token, self.settings.token_cache_ttl_sec)
        return key

    async def get_token(self, session_id: str) -> Any | None:
        key = f"token:{session_id}"
        return await self.get_json(key)

    async def set_prompt(self, session_id: str, prompt: str) -> str:
        key = f"prompt:{session_id}"
        await self._write(key, self._encrypt(prompt), self.settings.prompt_cache_ttl_sec)
        return key

    async def get_prompt(self, session_id: str) -> str | None:
        key = f"prompt:{session_id}"
        raw = await self._read(key)
        if raw is None:
            return None
        return self._decrypt(raw)
