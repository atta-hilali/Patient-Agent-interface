from __future__ import annotations

import asyncio
import json
import logging
import re
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
        self.enabled = settings.nemoguard_enabled
        self.content_enabled = settings.nemoguard_content_enabled
        self.topic_enabled = settings.nemoguard_topic_enabled
        self.fail_open = settings.nemoguard_fail_open
        self.strict_order = settings.nemoguard_strict_order
        self.content_safety_url = content_safety_url or settings.nemoguard_content_safety_url
        self.topic_control_url = topic_control_url or settings.nemoguard_topic_control_url
        self.content_model = settings.nemoguard_content_model
        self.topic_model = settings.nemoguard_topic_model
        self._model_cache: dict[str, str] = {}
        requested_topic_dir = Path(topic_dir)
        if requested_topic_dir.is_absolute():
            self.topic_dir = requested_topic_dir
        else:
            base_dir = Path(__file__).resolve().parents[2]
            self.topic_dir = base_dir / requested_topic_dir
        if not self.content_safety_url:
            self.content_enabled = False
        if not self.topic_control_url:
            self.topic_enabled = False

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

    def _base_url(self, endpoint_url: str) -> str:
        try:
            url = httpx.URL(endpoint_url)
            if not url.scheme or not url.host:
                raise ValueError("Invalid URL")
            if url.port:
                return f"{url.scheme}://{url.host}:{url.port}"
            return f"{url.scheme}://{url.host}"
        except Exception:  # noqa: BLE001
            # Fallback for malformed values; keep behavior deterministic.
            return endpoint_url.split("/v1/", 1)[0].rstrip("/")

    async def _resolve_chat_model(self, base_url: str, preferred: str) -> str:
        if preferred:
            return preferred
        cached = self._model_cache.get(base_url)
        if cached:
            return cached

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{base_url}/v1/models")
                response.raise_for_status()
                payload = response.json()
            first = ((payload or {}).get("data") or [{}])[0]
            model_id = str(first.get("id") or "").strip() or "model"
        except Exception:  # noqa: BLE001
            model_id = "model"

        self._model_cache[base_url] = model_id
        return model_id

    def _extract_json_object(self, raw: str) -> dict[str, Any]:
        text = (raw or "").strip()
        if not text:
            return {}

        # Strip markdown code fences if present.
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except Exception:  # noqa: BLE001
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
                return data if isinstance(data, dict) else {}
            except Exception:  # noqa: BLE001
                return {}
        return {}

    def _normalize_chat_result(self, payload: dict[str, Any], *, blocked_by: str) -> dict[str, Any]:
        blocked_raw = payload.get("blocked")
        if isinstance(blocked_raw, bool):
            blocked = blocked_raw
        else:
            decision = str(payload.get("decision") or payload.get("verdict") or "").strip().lower()
            blocked = decision in {"block", "blocked", "unsafe", "deny", "escalate", "redirect"}

        category = str(payload.get("category") or payload.get("topic") or payload.get("label") or "")
        if not category:
            category = blocked_by if blocked else "safe"

        severity = str(payload.get("severity") or ("HIGH" if blocked else "LOW")).upper()
        action = str(payload.get("action") or "").strip().lower()
        if action not in {"allow", "escalate", "redirect"}:
            action = "escalate" if (blocked and blocked_by == "content_safety") else ("redirect" if blocked else "allow")

        return {
            "blocked": blocked,
            "category": category,
            "severity": severity,
            "action": action,
        }

    async def _call_guardrail_chat(
        self,
        *,
        endpoint_url: str,
        role: str,
        text: str,
        blocked_by: str,
        model_name: str,
        topic_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        base_url = self._base_url(endpoint_url)
        model = await self._resolve_chat_model(base_url, model_name)
        chat_url = f"{base_url}/v1/chat/completions"

        if blocked_by == "content_safety":
            system_prompt = (
                "You are a clinical safety classifier. Return ONLY JSON with keys: "
                "blocked (boolean), category (string), severity (LOW|MEDIUM|HIGH), action (allow|escalate). "
                "Block only for clearly unsafe content (self-harm, crisis language, violence, overdose, "
                "graphic content, PHI leakage, severe allergy conflict)."
            )
        else:
            blocked_topics = (topic_config or {}).get("blocked_topics", [])
            system_prompt = (
                "You are a clinical topic-control classifier. Return ONLY JSON with keys: "
                "blocked (boolean), category (string), severity (LOW|MEDIUM|HIGH), action (allow|redirect). "
                f"Blocked topics: {blocked_topics}. "
                "Block only when the user request is in blocked topics."
            )

        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": role, "content": text},
            ],
            "temperature": 0.1,
            "max_tokens": 128,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(chat_url, json=body)
            response.raise_for_status()
            payload = response.json()

        # OpenAI-like wrapper.
        if isinstance(payload, dict) and "choices" in payload:
            choices = payload.get("choices") or []
            first = choices[0] if choices else {}
            message = first.get("message") or {}
            content = str(message.get("content") or "")
            parsed = self._extract_json_object(content)
            return self._normalize_chat_result(parsed, blocked_by=blocked_by)

        # Already a direct guardrail-shaped payload.
        if isinstance(payload, dict):
            if "blocked" in payload:
                return payload
            return self._normalize_chat_result(payload, blocked_by=blocked_by)

        return {"blocked": False, "category": "safe", "severity": "LOW", "action": "allow"}

    async def _call_content_safety(self, role: str, text: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.post(
                    self.content_safety_url,
                    json={"messages": [{"role": role, "content": text}]},
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code if exc.response is not None else 0
                # Some NemoGuard deployments expose OpenAI chat API instead of /v1/guardrail.
                if status in {404, 405}:
                    return await self._call_guardrail_chat(
                        endpoint_url=self.content_safety_url,
                        role=role,
                        text=text,
                        blocked_by="content_safety",
                        model_name=self.content_model,
                    )
                raise

    async def _call_topic_control(self, role: str, text: str, config: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.post(
                    self.topic_control_url,
                    json={"messages": [{"role": role, "content": text}], "config": config},
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code if exc.response is not None else 0
                if status in {404, 405}:
                    return await self._call_guardrail_chat(
                        endpoint_url=self.topic_control_url,
                        role=role,
                        text=text,
                        blocked_by="topic_control",
                        model_name=self.topic_model,
                        topic_config=config,
                    )
                raise

    def _normalize_category(self, category: str | None, fallback: str) -> str:
        normalized = (category or fallback).strip().lower().replace(" ", "_")
        return normalized or fallback

    def _content_safety_message_key(self, category: str | None) -> str:
        normalized = self._normalize_category(category, "content_safety")
        return CONTENT_SAFETY_MESSAGE_KEYS.get(normalized, "content_safety_general")

    def _topic_control_message_key(self, category: str | None) -> str:
        normalized = self._normalize_category(category, "topic_control")
        return TOPIC_CONTROL_MESSAGE_KEYS.get(normalized, "topic_control_general")

    def _unreachable_result(self, *, role: str, error: Exception) -> SafetyResult:
        logger.warning("NemoGuard request failed: %s", repr(error))
        if isinstance(error, (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError)):
            if self.fail_open:
                logger.warning("NemoGuard unavailable but fail-open is enabled; allowing turn.")
                return SafetyResult(safe=True, action="allow")
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
        raise error

    async def _run_strict_serial_checks(self, *, role: str, text: str, clinic_topic_yaml: str | None) -> SafetyResult:
        # Strict production mode: content safety first, then topic control only if content passes.
        if not self.content_enabled and not self.topic_enabled:
            return SafetyResult(safe=True, action="allow")

        config = self.load_topic_yaml(clinic_topic_yaml) if self.topic_enabled else {}
        if self.content_enabled:
            try:
                cs_response = await self._call_content_safety(role, text)
            except Exception as exc:  # noqa: BLE001
                return self._unreachable_result(role=role, error=exc)

            if cs_response.get("blocked"):
                category = self._normalize_category(cs_response.get("category"), "content_safety")
                logger.info(
                    "NemoGuard content safety blocked. category=%s severity=%s",
                    category,
                    cs_response.get("severity"),
                )
                return SafetyResult(
                    safe=False,
                    reason="content_safety",
                    category=category,
                    blocked_by="content_safety",
                    severity=cs_response.get("severity", "HIGH"),
                    action=cs_response.get("action", "escalate"),
                    message_key=self._content_safety_message_key(category),
                    discarded_draft=role == "assistant",
                )

        if self.topic_enabled:
            try:
                tc_response = await self._call_topic_control(role, text, config)
            except Exception as exc:  # noqa: BLE001
                return self._unreachable_result(role=role, error=exc)

            if tc_response.get("blocked"):
                category = self._normalize_category(tc_response.get("category"), "topic_control")
                logger.info(
                    "NemoGuard topic control blocked. category=%s severity=%s",
                    category,
                    tc_response.get("severity"),
                )
                return SafetyResult(
                    safe=False,
                    reason="topic_control",
                    category=category,
                    blocked_by="topic_control",
                    severity=tc_response.get("severity", "HIGH"),
                    action=tc_response.get("action", "redirect"),
                    message_key=self._topic_control_message_key(category),
                    discarded_draft=role == "assistant",
                )

        return SafetyResult(safe=True, action="allow")

    async def _run_parallel_checks(self, *, role: str, text: str, clinic_topic_yaml: str | None) -> SafetyResult:
        if not self.enabled:
            return SafetyResult(safe=True, action="allow")
        if not self.content_enabled and not self.topic_enabled:
            return SafetyResult(safe=True, action="allow")

        # Both guardrails run concurrently for lower latency. If both block, content
        # safety wins because it represents the stricter safety decision.
        config = self.load_topic_yaml(clinic_topic_yaml) if self.topic_enabled else {}
        calls = []
        labels = []
        if self.content_enabled:
            calls.append(self._call_content_safety(role, text))
            labels.append("content")
        if self.topic_enabled:
            calls.append(self._call_topic_control(role, text, config))
            labels.append("topic")

        responses = await asyncio.gather(*calls, return_exceptions=True)
        mapped: dict[str, Any] = {}
        for idx, label in enumerate(labels):
            mapped[label] = responses[idx]

        cs_response = mapped.get("content")
        tc_response = mapped.get("topic")

        for response in (cs_response, tc_response):
            if response is None:
                continue
            if isinstance(response, Exception):
                logger.warning("NemoGuard request failed: %s", repr(response))
                if isinstance(response, (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError)):
                    if self.fail_open:
                        logger.warning("NemoGuard unavailable but fail-open is enabled; allowing turn.")
                        return SafetyResult(safe=True, action="allow")
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

        if isinstance(cs_response, dict) and cs_response.get("blocked"):
            category = self._normalize_category(cs_response.get("category"), "content_safety")
            logger.info("NemoGuard content safety blocked. category=%s severity=%s", category, cs_response.get("severity"))
            return SafetyResult(
                safe=False,
                reason="content_safety",
                category=category,
                blocked_by="content_safety",
                severity=cs_response.get("severity", "HIGH"),
                action=cs_response.get("action", "escalate"),
                message_key=self._content_safety_message_key(category),
                discarded_draft=role == "assistant",
            )

        if isinstance(tc_response, dict) and tc_response.get("blocked"):
            category = self._normalize_category(tc_response.get("category"), "topic_control")
            logger.info("NemoGuard topic control blocked. category=%s severity=%s", category, tc_response.get("severity"))
            return SafetyResult(
                safe=False,
                reason="topic_control",
                category=category,
                blocked_by="topic_control",
                severity=tc_response.get("severity", "HIGH"),
                action=tc_response.get("action", "redirect"),
                message_key=self._topic_control_message_key(category),
                discarded_draft=role == "assistant",
            )

        return SafetyResult(safe=True, action="allow")

    async def check_input(self, text: str, clinic_topic_yaml: str | None) -> SafetyResult:
        if not self.enabled or (not self.content_enabled and not self.topic_enabled):
            return SafetyResult(safe=True, action="allow")
        if self.strict_order:
            return await self._run_strict_serial_checks(role="user", text=text, clinic_topic_yaml=clinic_topic_yaml)
        return await self._run_parallel_checks(role="user", text=text, clinic_topic_yaml=clinic_topic_yaml)

    async def safety_check(self, draft: str, clinic_topic_yaml: str | None) -> SafetyResult:
        if not self.enabled or (not self.content_enabled and not self.topic_enabled):
            return SafetyResult(safe=True, action="allow")
        if self.strict_order:
            return await self._run_strict_serial_checks(role="assistant", text=draft, clinic_topic_yaml=clinic_topic_yaml)
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
