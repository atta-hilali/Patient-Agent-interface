from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.cache import WorkflowCache
from app.config import get_settings

from .audit import get_audit_logger


def _bool_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


class HipaaChecklistService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.path = Path(__file__).resolve().parents[2] / "config" / "hipaa_launch_checklist.json"

    def _load_items(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            parsed = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return []
        return [item for item in parsed if isinstance(item, dict)]

    async def _automatic_status(self) -> dict[str, bool]:
        settings = self.settings
        cache = WorkflowCache(settings)
        redis_ok = False
        try:
            redis_ok = bool(await cache.ping()) or not settings.redis_required
        except Exception:
            redis_ok = False

        audit = get_audit_logger().verify_chain()
        # Require explicit secret/operator configuration rather than relying on
        # runtime defaults that may be auto-generated during local development.
        required_secrets = [
            bool(os.getenv("STATE_SIGNING_KEY", "").strip()),
            bool(os.getenv("CONTEXT_ENCRYPTION_KEY", "").strip()),
            bool(os.getenv("MEDGEMMA_BASE_URL", "").strip()),
        ]
        return {
            "safety_gate_enforced": bool(settings.nemoguard_enabled and settings.nemoguard_strict_order and not settings.nemoguard_fail_open),
            "immutable_audit_chain_ok": bool(audit.get("ok", False)),
            "redis_required_enabled": bool((not settings.redis_required) or redis_ok),
            "vault_or_secret_baseline": bool(settings.vault_enabled or all(required_secrets)),
        }

    async def evaluate(self) -> dict[str, Any]:
        items = self._load_items()
        auto = await self._automatic_status()
        evaluated: list[dict[str, Any]] = []

        for item in items:
            item_id = str(item.get("id") or "").strip()
            source = str(item.get("source") or "manual").strip().lower()
            required = bool(item.get("required", True))
            if source == "automatic":
                passed = bool(auto.get(item_id, False))
            else:
                # Manual attestations can be set by CI/CD release variables.
                passed = _bool_env(f"HIPAA_{item_id.upper()}_APPROVED")

            evaluated.append(
                {
                    "id": item_id,
                    "description": item.get("description", ""),
                    "source": source,
                    "required": required,
                    "passed": passed,
                }
            )

        required_items = [item for item in evaluated if item["required"]]
        passed_required = [item for item in required_items if item["passed"]]
        failed_required = [item for item in required_items if not item["passed"]]
        overall_ok = len(required_items) == len(passed_required)

        return {
            "ok": overall_ok,
            "required_total": len(required_items),
            "required_passed": len(passed_required),
            "required_failed": len(failed_required),
            "items": evaluated,
        }


_hipaa_service: HipaaChecklistService | None = None


def get_hipaa_checklist_service() -> HipaaChecklistService:
    global _hipaa_service
    if _hipaa_service is None:
        _hipaa_service = HipaaChecklistService()
    return _hipaa_service
