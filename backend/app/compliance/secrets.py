from __future__ import annotations

import os
from typing import Any

import httpx

from app.config import Settings, get_settings


class SecretResolver:
    """
    Vault-first secret resolver with environment fallback.
    Supports Vault KV v2 using VAULT_ADDR/VAULT_TOKEN.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def _read_vault_path(self, path: str) -> dict[str, Any]:
        if not self.settings.vault_addr or not self.settings.vault_token:
            return {}
        target = f"{self.settings.vault_addr.rstrip('/')}/v1/{path.lstrip('/')}"
        headers = {"X-Vault-Token": self.settings.vault_token}
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(target, headers=headers)
            response.raise_for_status()
            payload = response.json()
        # KV v2 payload shape: {"data":{"data":{...}}}
        data = payload.get("data") if isinstance(payload, dict) else {}
        if isinstance(data, dict) and isinstance(data.get("data"), dict):
            return data["data"]
        return data if isinstance(data, dict) else {}

    async def _vault_lookup(self, key: str) -> str:
        if not self.settings.vault_enabled:
            return ""
        mount = self.settings.vault_mount.strip("/")
        # Allow either pre-expanded "secret/data/app" or simple mount root.
        candidates = [mount]
        if self.settings.vault_kv_version == 2 and "/data/" not in mount:
            candidates.insert(0, f"{mount}/data/app")

        for path in candidates:
            try:
                payload = await self._read_vault_path(path)
            except Exception:  # noqa: BLE001
                continue
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    async def resolve(self, key: str, default: str = "") -> str:
        env_value = os.getenv(key, "").strip()
        if env_value:
            return env_value
        vault_value = await self._vault_lookup(key)
        if vault_value:
            os.environ[key] = vault_value
            return vault_value
        return default

    async def assert_required(self, keys: list[str]) -> dict[str, Any]:
        missing: list[str] = []
        resolved: dict[str, str] = {}
        for key in keys:
            value = await self.resolve(key)
            if not value:
                missing.append(key)
            else:
                resolved[key] = "***"
        return {"ok": not missing, "missing": missing, "resolved": resolved}


_secret_resolver: SecretResolver | None = None


def get_secret_resolver() -> SecretResolver:
    global _secret_resolver
    if _secret_resolver is None:
        _secret_resolver = SecretResolver(get_settings())
    return _secret_resolver

