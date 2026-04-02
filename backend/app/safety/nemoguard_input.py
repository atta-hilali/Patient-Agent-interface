# from __future__ import annotations
from __future__ import annotations

# from app.safety.checker import SafetyResult, get_safety_checker
from app.safety.checker import SafetyResult, get_safety_checker


# InputSafetyResult = SafetyResult
InputSafetyResult = SafetyResult


# async def check_input_safety(text: str, clinic_yaml: str | None) -> InputSafetyResult:
async def check_input_safety(text: str, clinic_yaml: str | None) -> InputSafetyResult:
    # return await get_safety_checker().check_input(text, clinic_yaml)
    return await get_safety_checker().check_input(text, clinic_yaml)
