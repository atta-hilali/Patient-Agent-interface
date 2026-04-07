from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import httpx
from app.config import get_settings

try:
    import yaml
except Exception:  # noqa: BLE001
    yaml = None


DEFAULT_TOPIC_PROFILE = "general_medicine"
logger = logging.getLogger(__name__)

DEFAULT_TOPIC_CONFIG = {
    "allowed_topics": [
        "medication_explanation",
        "lab_result_explanation",
        "appointment_preparation",
        "care_plan_clarification",
        "symptom_reporting",
        "general_health_education",
    ],
    "blocked_topics": [
        "diagnosis",
        "prescribing",
        "dosage_change",
        "emergency_assessment",
        "mental_health_therapy",
    ],
    "escalation_triggers": [
        "pain_score_gte_7",
        "crisis_language",
        "explicit_human_request",
    ],
}

CONTENT_SAFETY_MESSAGE_KEYS = {
    "self_harm": "content_safety_self_harm",
    "crisis_language": "content_safety_crisis_language",
    "graphic_content": "content_safety_graphic_content",
    "phi_leakage": "content_safety_phi_leakage",
    "allergy_conflict": "content_safety_allergy_conflict",
}

TOPIC_CONTROL_MESSAGE_KEYS = {
    "diagnosis": "topic_control_diagnosis",
    "prescribing": "topic_control_prescribing",
    "dosage_change": "topic_control_dosage_change",
    "emergency_assessment": "topic_control_emergency_assessment",
    "mental_health_therapy": "topic_control_mental_health_therapy",
}


@dataclass
class SafetyResult:
    safe: bool
    reason: Optional[str] = None
    category: Optional[str] = None
    blocked_by: Optional[str] = None
    severity: Optional[str] = None
    action: str = "allow"
    message_key: Optional[str] = None
    discarded_draft: bool = False


class SafetyChecker:
    def __init__(
        self,
        *,
        content_safety_url: str | None = None,
        topic_control_url: str | None = None,
        topic_dir: str = "config/topics",
    ) -> None:
        settings = get_settings()
        self.content_safety_url = content_safety_url or settings.nemoguard_content_safety_url
        self.topic_control_url = topic_control_url or settings.nemoguard_topic_control_url
        requested_topic_dir = Path(topic_dir)
        if requested_topic_dir.is_absolute():
            self.topic_dir = requested_topic_dir
        else:
            base_dir = Path(__file__).resolve().parents[2]
            self.topic_dir = base_dir / requested_topic_dir

    def available_topic_profiles(self) -> list[str]:
        if not self.topic_dir.exists():
            return [DEFAULT_TOPIC_PROFILE]
        return sorted(path.stem for path in self.topic_dir.glob("*.yaml"))

    def resolve_topic_path(self, clinic_topic_yaml: str | None) -> Path:
        if not clinic_topic_yaml:
            return self.topic_dir / f"{DEFAULT_TOPIC_PROFILE}.yaml"

        candidate = Path(clinic_topic_yaml)
        if candidate.is_absolute() and candidate.exists():
            return candidate

        if candidate.suffix.lower() in {".yaml", ".yml"}:
            direct = self.topic_dir / candidate.name
            if direct.exists():
                return direct

        profile = clinic_topic_yaml.removesuffix(".yaml").removesuffix(".yml")
        return self.topic_dir / f"{profile}.yaml"

    def load_topic_yaml(self, clinic_topic_yaml: str | None) -> dict[str, Any]:
        target = self.resolve_topic_path(clinic_topic_yaml)
        if not target.exists() or yaml is None:
            return dict(DEFAULT_TOPIC_CONFIG)
        raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
        return raw if isinstance(raw, dict) else dict(DEFAULT_TOPIC_CONFIG)

    def save_custom_topic_yaml(self, *, clinic_id: str, yaml_content: str) -> str:
        self.topic_dir.mkdir(parents=True, exist_ok=True)
        target = self.topic_dir / f"{clinic_id}_custom.yaml"
        target.write_text(yaml_content, encoding="utf-8")
        return target.name

    async def _call_content_safety(self, role: str, text: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                self.content_safety_url,
                json={"messages": [{"role": role, "content": text}]},
            )
            response.raise_for_status()
            return response.json()

    async def _call_topic_control(self, role: str, text: str, config: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                self.topic_control_url,
                json={"messages": [{"role": role, "content": text}], "config": config},
            )
            response.raise_for_status()
            return response.json()

    def _normalize_category(self, category: str | None, fallback: str) -> str:
        normalized = (category or fallback).strip().lower().replace(" ", "_")
        return normalized or fallback

    def _content_safety_message_key(self, category: str | None) -> str:
        normalized = self._normalize_category(category, "content_safety")
        return CONTENT_SAFETY_MESSAGE_KEYS.get(normalized, "content_safety_general")

    def _topic_control_message_key(self, category: str | None) -> str:
        normalized = self._normalize_category(category, "topic_control")
        return TOPIC_CONTROL_MESSAGE_KEYS.get(normalized, "topic_control_general")

    async def _run_parallel_checks(self, *, role: str, text: str, clinic_topic_yaml: str | None) -> SafetyResult:
        # Both guardrails run concurrently for lower latency. If both block, content
        # safety wins because it represents the stricter safety decision.
        config = self.load_topic_yaml(clinic_topic_yaml)
        cs_response, tc_response = await asyncio.gather(
            self._call_content_safety(role, text),
            self._call_topic_control(role, text, config),
            return_exceptions=True,
        )

        for response in (cs_response, tc_response):
            if isinstance(response, Exception):
                logger.warning("NemoGuard request failed: %s", repr(response))
                if isinstance(response, (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError)):
                    return SafetyResult(
                        safe=False,
                        reason="nemoguard_unreachable",
                        category="nim_unreachable",
                        blocked_by="nemoguard_unreachable",
                        severity="HIGH",
                        action="escalate",
                        message_key="nemoguard_output_unreachable",
                        discarded_draft=role == "assistant",
                    )
                raise response

        if cs_response.get("blocked"):
            category = self._normalize_category(cs_response.get("category"), "content_safety")
            logger.info("NemoGuard content safety blocked. category=%s severity=%s", category, cs_response.get("severity"))
            return SafetyResult(
                safe=False,
                reason="content_safety",
                category=category,
                blocked_by="content_safety",
                severity=cs_response.get("severity", "HIGH"),
                action="escalate",
                message_key=self._content_safety_message_key(category),
                discarded_draft=role == "assistant",
            )

        if tc_response.get("blocked"):
            category = self._normalize_category(tc_response.get("category"), "topic_control")
            logger.info("NemoGuard topic control blocked. category=%s severity=%s", category, tc_response.get("severity"))
            return SafetyResult(
                safe=False,
                reason="topic_control",
                category=category,
                blocked_by="topic_control",
                severity=tc_response.get("severity", "HIGH"),
                action="redirect",
                message_key=self._topic_control_message_key(category),
                discarded_draft=role == "assistant",
            )

        return SafetyResult(safe=True, action="allow")

    async def check_input(self, text: str, clinic_topic_yaml: str | None) -> SafetyResult:
        return await self._run_parallel_checks(role="user", text=text, clinic_topic_yaml=clinic_topic_yaml)

    async def safety_check(self, draft: str, clinic_topic_yaml: str | None) -> SafetyResult:
        return await self._run_parallel_checks(role="assistant", text=draft, clinic_topic_yaml=clinic_topic_yaml)

    async def check_output(self, draft: str, clinic_topic_yaml: str | None) -> SafetyResult:
        return await self.safety_check(draft, clinic_topic_yaml)


_checker: SafetyChecker | None = None


def get_safety_checker() -> SafetyChecker:
    global _checker
    if _checker is None:
        settings = get_settings()
        _checker = SafetyChecker(
            content_safety_url=settings.nemoguard_content_safety_url,
            topic_control_url=settings.nemoguard_topic_control_url,
            topic_dir=settings.nemoguard_topic_dir,
        )
    return _checker
