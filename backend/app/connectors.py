from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, validator

from .config import Settings, get_settings


class ConnectorConfig(BaseModel):
    clinic_id: str
    adapter_type: Literal["fhir_r4", "hl7_v2", "cda", "rest", "csv", "manual"]
    base_url: str | None = None
    auth_method: Literal["smart_pkce", "pin", "dob", "jwt"]
    client_id: str | None = None
    topic_yaml: str | None = None
    write_back: Literal["fhir", "hl7", "webhook", "none"] = "none"
    specialty: str | None = None
    cache_ttl_s: int = 300
    active: bool = True

    @validator("clinic_id", pre=True)
    def _normalize_id(cls, value: str) -> str:  # noqa: D401
        return (value or "").strip()


class ConnectorStore:
    """
    Lightweight replacement for the Postgres connectors table described in the Phase 1 guide.
    Loads from docs/connectors.json (or CONNECTORS_FILE) and caches results in memory with a
    periodic refresh task.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cache: dict[str, ConnectorConfig] = {}
        self._lock = asyncio.Lock()
        self._refresh_task: asyncio.Task | None = None
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        path = self._resolve_connectors_path()
        if not path.exists():
            self._cache = {}
            return
        try:
            data = json.loads(path.read_text())
        except Exception:  # noqa: BLE001
            self._cache = {}
            return
        if isinstance(data, list):
            fresh: dict[str, ConnectorConfig] = {}
            for raw in data:
                try:
                    cfg = ConnectorConfig.model_validate(raw)
                except Exception:  # noqa: BLE001
                    continue
                if cfg.active:
                    fresh[cfg.clinic_id] = cfg
            self._cache = fresh

    def _save_to_disk(self) -> None:
        path = self._resolve_connectors_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [
            config.model_dump(mode="json")
            for _, config in sorted(self._cache.items(), key=lambda item: item[0])
        ]
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _resolve_connectors_path(self) -> Path:
        raw = Path(self.settings.connectors_file)
        if raw.is_absolute():
            return raw

        candidates = [
            Path.cwd() / raw,
            Path(__file__).resolve().parents[2] / raw,  # backend/
            Path(__file__).resolve().parents[3] / raw,  # repo root
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    async def refresh_loop(self) -> None:
        while True:
            await asyncio.sleep(300)
            self._load_from_disk()

    def start_background_refresh(self) -> None:
        if self._refresh_task and not self._refresh_task.done():
            return
        try:
            loop = asyncio.get_event_loop()
            self._refresh_task = loop.create_task(self.refresh_loop())
        except RuntimeError:
            # no running loop (unit tests) — ignore
            self._refresh_task = None

    async def get(self, clinic_id: str) -> ConnectorConfig:
        normalized = (clinic_id or "").strip()
        if not normalized:
            raise HTTPException(status_code=400, detail="clinic_id is required")
        async with self._lock:
            cfg = self._cache.get(normalized)
        if not cfg:
            raise HTTPException(status_code=404, detail="Clinic not found")
        return cfg

    async def update_topic_yaml(self, clinic_id: str, topic_yaml: str, specialty: str | None = None) -> ConnectorConfig:
        normalized = (clinic_id or "").strip()
        if not normalized:
            raise HTTPException(status_code=400, detail="clinic_id is required")
        async with self._lock:
            cfg = self._cache.get(normalized)
            if not cfg:
                raise HTTPException(status_code=404, detail="Clinic not found")
            updated = cfg.model_copy(
                update={
                    "topic_yaml": topic_yaml,
                    "specialty": specialty if specialty is not None else cfg.specialty,
                }
            )
            self._cache[normalized] = updated
            self._save_to_disk()
            return updated


internal_key_header = APIKeyHeader(name="X-Internal-Key", auto_error=False)


def verify_internal_key(
    provided_key: str | None = Depends(internal_key_header),
    settings: Settings = Depends(get_settings),
) -> None:
    if not provided_key or provided_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="Invalid internal key")


def get_connector_store(settings: Settings = Depends(get_settings)) -> ConnectorStore:
    store = ConnectorStore(settings)
    store.start_background_refresh()
    return store
