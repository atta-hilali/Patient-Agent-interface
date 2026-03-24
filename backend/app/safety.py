from __future__ import annotations

import re

from .models import SafetyCheckResponse, SafetyRuleMatch


CRISIS_PATTERNS = [
    r"\bsuicid(?:e|al|e?d?)\b",
    r"\bkill myself\b",
    r"\boverdose\b",
    r"\bchest pain\b",
    r"\bcan(?:not|'?t)\s+breathe\b",
    r"\bstroke\b",
    r"\bunconscious\b",
]

MED_CHANGE_PATTERNS = [
    r"\bchange (?:my )?(?:med|medication|dose|dosage)\b",
    r"\bincrease (?:my )?(?:med|medication|dose|dosage)\b",
    r"\bdecrease (?:my )?(?:med|medication|dose|dosage)\b",
    r"\bstop (?:my )?(?:med|medication)\b",
    r"\bstart (?:a )?new (?:med|medication)\b",
]

PAIN_SCORE_PATTERN = re.compile(r"\bpain(?:\s+(?:is|level|score))?\s*[:=]?\s*(\d{1,2})\b", re.IGNORECASE)


def run_preflight_safety_check(text: str, *, pain_threshold: int = 7) -> SafetyCheckResponse:
    content = (text or "").strip()
    lowered = content.lower()
    matches: list[SafetyRuleMatch] = []

    for pattern in CRISIS_PATTERNS:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            matches.append(
                SafetyRuleMatch(
                    rule="crisis_keyword",
                    message="Potential crisis language detected.",
                    details={"pattern": pattern},
                )
            )
            break

    pain_match = PAIN_SCORE_PATTERN.search(lowered)
    if pain_match:
        score = int(pain_match.group(1))
        if score > pain_threshold:
            matches.append(
                SafetyRuleMatch(
                    rule="high_pain_score",
                    message=f"Pain score {score} exceeds threshold {pain_threshold}.",
                    details={"score": score, "threshold": pain_threshold},
                )
            )

    for pattern in MED_CHANGE_PATTERNS:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            matches.append(
                SafetyRuleMatch(
                    rule="medication_change_request",
                    message="Medication change request detected.",
                    details={"pattern": pattern},
                )
            )
            break

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
