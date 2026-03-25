from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

try:
    from redis.asyncio import Redis
except Exception:  # noqa: BLE001
    Redis = None  # type: ignore[assignment]


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


@dataclass
class OAuthStateEntry:
    code_verifier: str
    clinic_id: str | None
    created_at: float

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "OAuthStateEntry":
        return cls(
            code_verifier=raw.get("code_verifier", ""),
            clinic_id=raw.get("clinic_id"),
            created_at=float(raw.get("created_at", 0)),
        )

    def as_json(self) -> str:
        return json.dumps(
            {
                "code_verifier": self.code_verifier,
                "clinic_id": self.clinic_id,
                "created_at": self.created_at,
            },
            ensure_ascii=True,
            separators=(",", ":"),
        )


def encode_state_token(*, code_verifier: str, clinic_id: str | None, ttl_sec: int, secret: str) -> str:
    now = int(time.time())
    payload = {
        "cv": code_verifier,
        "cid": clinic_id,
        "exp": now + ttl_sec,
        "iat": now,
    }
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return f"{_b64url_encode(body)}.{_b64url_encode(sig)}"


def decode_state_token(state: str, secret: str, ttl_sec: int) -> OAuthStateEntry | None:
    try:
        body_b64, sig_b64 = state.split(".", 1)
    except ValueError:
        return None
    try:
        body = _b64url_decode(body_b64)
        sig = _b64url_decode(sig_b64)
    except Exception:  # noqa: BLE001
        return None
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        parsed = json.loads(body.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None
    now = int(time.time())
    if int(parsed.get("exp", 0)) < now or (now - int(parsed.get("iat", 0)) > ttl_sec + 60):
        return None
    return OAuthStateEntry(
        code_verifier=parsed.get("cv", ""),
        clinic_id=parsed.get("cid"),
        created_at=float(parsed.get("iat", 0)),
    )


class OAuthStateStore:
    """
    Stores PKCE state nonces. Uses Redis if configured, falling back to in-memory.
    Also embeds a signed token in the state itself, so callbacks succeed even if the
    request is handled by a different instance than the one that issued /auth/epic/start.
    """

    def __init__(self, ttl_sec: int = 600, redis_url: str | None = None, signing_key: str = "dev-sign") -> None:
        self.ttl_sec = ttl_sec
        self.signing_key = signing_key
        self._store: dict[str, OAuthStateEntry] = {}
        self._redis: Redis | None = None
        if redis_url and Redis is not None:
            try:
                self._redis = Redis.from_url(redis_url, decode_responses=True)
            except Exception:  # noqa: BLE001
                self._redis = None

    def _cleanup(self) -> None:
        now = time.time()
        expired = [state for state, entry in self._store.items() if now - entry.created_at > self.ttl_sec]
        for state in expired:
            self._store.pop(state, None)

    async def _save_entry(self, key: str, entry: OAuthStateEntry) -> None:
        """Persist state entry to Redis and memory under the provided key."""
        if self._redis:
            try:
                await self._redis.setex(f"oauth_state:{key}", self.ttl_sec, entry.as_json())
            except Exception:  # noqa: BLE001
                self._redis = None
        self._cleanup()
        self._store[key] = entry

    async def issue_state(self, *, state: str, code_verifier: str, clinic_id: str | None = None) -> str:
        entry = OAuthStateEntry(code_verifier=code_verifier, clinic_id=clinic_id, created_at=time.time())
        token = encode_state_token(
            code_verifier=code_verifier,
            clinic_id=clinic_id,
            ttl_sec=self.ttl_sec,
            secret=self.signing_key,
        )
        # Persist under both the random state and the signed token so callbacks can validate either form.
        await self._save_entry(state, entry)
        await self._save_entry(token, entry)
        return token

    async def pop_valid(self, state: str) -> OAuthStateEntry | None:
        # Try Redis / memory
        if self._redis:
            try:
                raw = await self._redis.get(f"oauth_state:{state}")
                if raw:
                    await self._redis.delete(f"oauth_state:{state}")
                    parsed = json.loads(raw)
                    entry = OAuthStateEntry.from_raw(parsed) if isinstance(parsed, dict) else None
                    if entry and (time.time() - entry.created_at) <= self.ttl_sec:
                        return entry
            except Exception:  # noqa: BLE001
                self._redis = None

        self._cleanup()
        entry = self._store.pop(state, None)
        if entry and (time.time() - entry.created_at) <= self.ttl_sec:
            return entry

        # Stateless fallback
        return decode_state_token(state, self.signing_key, self.ttl_sec)
