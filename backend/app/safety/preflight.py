from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except Exception:  # noqa: BLE001
    yaml = None


DEFAULT_PROFILE = "general_medicine"


@dataclass
class PreflightResult:
    escalate: bool
    reason: Optional[str] = None
    bypass_llm: bool = False
    severity: Optional[str] = None
    message_key: Optional[str] = None
    pain_score: Optional[int] = None

    @property
    def triggered(self) -> bool:
        return self.escalate

    @property
    def trigger_type(self) -> Optional[str]:
        return self.reason


class PreflightChecker:
    def __init__(
        self,
        config_path: str | None = None,
        *,
        pain_threshold: int = 7,
    ) -> None:
        base_dir = Path(__file__).resolve().parents[2]
        resolved_path = Path(config_path) if config_path else (base_dir / "config" / "preflight_rules.yaml")
        self.config_path = resolved_path
        self.pain_threshold = pain_threshold
        self.config = self._load_config()
        self._compiled_profiles: dict[str, dict[str, Any]] = {}

        # These regexes are the deterministic "stop before model" rules. They catch
        # obvious emergencies, high pain scores, and dosage-change requests before
        # NemoGuard or MedGemma are allowed to spend time on the turn.
        self.pain_score_patterns = [
            re.compile(r"\bpain\s+(?:is|was|at|around)\s+(\d{1,2})\s*(?:/|out of)\s*10\b", re.IGNORECASE),
            re.compile(r"\b(\d{1,2})\s*(?:/|out of)\s*10\b", re.IGNORECASE),
            re.compile(r"\bpain\s+score\s*(?:is|was|:)?\s*(\d{1,2})\b", re.IGNORECASE),
        ]
        self.contextual_false_positive_markers = [
            "years ago",
            "in general",
            "education",
            "article",
            "leaflet",
            "awareness",
            "what does",
            "explain",
            "summarize",
            "told to",
            "support group",
            "movie",
            "dream",
            "last year",
            "survivors",
            "in case of an emergency",
            "what unconscious means",
        ]
        self.immediacy_markers = [
            "right now",
            "now",
            "currently",
            "today",
            "suddenly",
            "again",
            "feel like",
            "having",
            "started",
        ]

    def _load_config(self) -> dict[str, Any]:
        if yaml is None or not self.config_path.exists():
            return {
                "crisis_keywords": [
                    r"chest.?pain",
                    r"can.?t.?breathe",
                    r"can.?t.?breath",
                    r"cant.?breathe",
                    r"cant.?breath",
                    r"cannot.?breathe",
                    r"cannot.?breath",
                    r"suicidal",
                    r"suicid",
                    r"want.?to.?suicide",
                    r"kill.?myself",
                    r"heart.?attack",
                    r"stroke",
                    r"severe.?pain",
                    r"emergency",
                    r"call.?911",
                    r"overdose",
                    r"unconscious",
                ],
                "medication_change_keywords": [
                    r"stop.?taking",
                    r"change.?my.?dose",
                    r"double.?my",
                    r"take.?more.?than",
                    r"skip.?my.?medication",
                ],
                "specialty_overrides": {},
            }

        raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        return raw if isinstance(raw, dict) else {}

    def _profile_rules(self, profile: str | None) -> dict[str, Any]:
        normalized = (profile or DEFAULT_PROFILE).strip() or DEFAULT_PROFILE
        if normalized in self._compiled_profiles:
            return self._compiled_profiles[normalized]

        base_crisis = list(self.config.get("crisis_keywords", []))
        base_medication = list(self.config.get("medication_change_keywords", []))
        overrides = self.config.get("specialty_overrides", {}) or {}
        profile_rules = overrides.get(normalized, {}) if isinstance(overrides, dict) else {}
        crisis_terms = base_crisis + list(profile_rules.get("crisis_keywords", []))
        medication_terms = base_medication + list(profile_rules.get("medication_change_keywords", []))

        compiled = {
            "crisis_keywords": crisis_terms,
            "medication_keywords": medication_terms,
            "crisis_patterns": re.compile("|".join(crisis_terms), re.IGNORECASE),
            "medication_patterns": re.compile("|".join(medication_terms), re.IGNORECASE),
        }
        self._compiled_profiles[normalized] = compiled
        return compiled

    def pain_score_extractor(self, text: str) -> Optional[int]:
        content = text or ""
        for pattern in self.pain_score_patterns:
            match = pattern.search(content)
            if not match:
                continue
            try:
                score = int(match.group(1))
            except (TypeError, ValueError):
                continue
            if 0 <= score <= 10:
                return score
        return None

    async def preflight_check(self, text: str, profile: str | None = None) -> PreflightResult:
        return self.check(text, profile=profile)

    def check(self, text: str, profile: str | None = None) -> PreflightResult:
        content = text or ""
        rules = self._profile_rules(profile)

        if rules["crisis_patterns"].search(content) and not self._is_contextual_reference(content):
            return PreflightResult(
                escalate=True,
                reason="crisis_keyword",
                bypass_llm=True,
                severity="HIGH",
                message_key="crisis_escalation",
            )

        pain_score = self.pain_score_extractor(content)
        if pain_score is not None and pain_score >= self.pain_threshold:
            return PreflightResult(
                escalate=True,
                reason=f"pain_score:{pain_score}",
                bypass_llm=True,
                severity="HIGH",
                message_key="pain_escalation",
                pain_score=pain_score,
            )

        if rules["medication_patterns"].search(content):
            return PreflightResult(
                escalate=True,
                reason="medication_change_request",
                bypass_llm=False,
                severity="HIGH",
                message_key="medication_change_blocked",
            )

        return PreflightResult(escalate=False)

    def _is_contextual_reference(self, text: str) -> bool:
        lowered = text.lower()
        if any(marker in lowered for marker in self.immediacy_markers):
            return False
        if "cannot breathe through my nose" in lowered:
            return True
        if any(marker in lowered for marker in self.contextual_false_positive_markers):
            return True
        if lowered.endswith("?") and any(marker in lowered for marker in ["what", "explain", "summarize"]):
            return True
        return False


class AllergyIndex:
    def __init__(self, ctx: Any) -> None:
        self._names = set()
        self._conflict_meds = set()
        for allergy in getattr(ctx, "allergies", []):
            name = getattr(allergy, "substance", "")
            if name:
                self._names.add(name.lower())
        for conflict in getattr(ctx, "allergyConflicts", []):
            message = getattr(conflict, "message", "")
            if message:
                self._conflict_meds.add(message.lower())

    def check_text(self, text: str) -> Optional[str]:
        lowered = (text or "").lower()
        for name in self._names:
            if re.search(r"\b" + re.escape(name) + r"\b", lowered):
                return name
        return None


_checker: Optional[PreflightChecker] = None


def get_preflight_checker() -> PreflightChecker:
    global _checker
    if _checker is None:
        _checker = PreflightChecker()
    return _checker
