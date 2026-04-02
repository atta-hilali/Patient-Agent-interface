# from __future__ import annotations
from __future__ import annotations

# from langchain_core.tools import tool
from langchain_core.tools import tool

# from app.agent.llm_client import call_medgemma_vision
from app.agent.llm_client import call_medgemma_vision
# from app.agent.tools.schemas import ImageAnalysisInput, ImageFinding, ToolTextResult, dump_tool_result
from app.agent.tools.schemas import ImageAnalysisInput, ImageFinding, ToolTextResult, dump_tool_result


# @tool(args_schema=ImageAnalysisInput)
@tool(args_schema=ImageAnalysisInput)
# async def analyze_image(image_b64: str, patient_context_summary: str) -> str:
async def analyze_image(image_b64: str, patient_context_summary: str) -> str:
    # """Analyze a patient-uploaded image and describe findings in plain language."""
    """Analyze a patient-uploaded image and describe findings in plain language."""
    # prompt = (
    prompt = (
        # f"Patient context: {patient_context_summary}\n\n"
        f"Patient context: {patient_context_summary}\n\n"
        # "Describe what you observe in plain language relevant to this patient. "
        "Describe what you observe in plain language relevant to this patient. "
        # "Note anything clinically significant. Do not diagnose. "
        "Note anything clinically significant. Do not diagnose. "
        # "If anything requires clinical assessment, clearly say so."
        "If anything requires clinical assessment, clearly say so."
    # )
    )
    # finding_text = await call_medgemma_vision(prompt, image_b64)
    finding_text = await call_medgemma_vision(prompt, image_b64)
    # result = ImageFinding(finding=finding_text or "No image finding returned.")
    result = ImageFinding(finding=finding_text or "No image finding returned.")
    # return dump_tool_result(
    return dump_tool_result(
        # ToolTextResult(
        ToolTextResult(
            # tool_name="analyze_image",
            tool_name="analyze_image",
            # summary=result.finding,
            summary=result.finding,
            # data={"findings": [result.model_dump(mode="json")]},
            data={"findings": [result.model_dump(mode="json")]},
        # )
        )
    # )
    )
