from __future__ import annotations

from app.models import SafetyCheckResponse, SafetyRuleMatch
from app.safety.preflight import get_preflight_checker


def run_preflight_safety_check(text: str, *, pain_threshold: int = 7) -> SafetyCheckResponse:
    matches: list[SafetyRuleMatch] = []
    checker = get_preflight_checker()
    checker.pain_threshold = pain_threshold
    result = checker.check(text)

    if result.reason:
        details = {}
        if result.pain_score is not None:
            details = {"score": result.pain_score, "threshold": pain_threshold}
        matches.append(
            SafetyRuleMatch(
                rule=result.reason,
                message="Pre-flight safety rule triggered.",
                details=details,
            )
        )

    if matches:
        return SafetyCheckResponse(
            safe=False,
            escalate=True,
            decision="escalate_immediately",
            reason="Pre-flight safety rule triggered; bypassing LLM response path.",
            matchedRules=matches,
        )

    return SafetyCheckResponse(
        safe=True,
        escalate=False,
        decision="allow_llm_path",
        reason="No blocking pre-flight safety rules matched.",
        matchedRules=[],
    )
