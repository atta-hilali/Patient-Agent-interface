# import asyncio
import asyncio
# import logging
import logging

# from app.agent.llm_client import call_medgemma_tool_planner
from app.agent.llm_client import call_medgemma_tool_planner
# from app.agent.state import AgentState
from app.agent.state import AgentState
# from app.agent.tools.escalation_tool import escalate_to_human
from app.agent.tools.escalation_tool import escalate_to_human
# from app.agent.tools.fhir_tools import (
from app.agent.tools.fhir_tools import (
    # get_appointments,
    get_appointments,
    # get_care_plan,
    get_care_plan,
    # get_documents,
    get_documents,
    # get_labs,
    get_labs,
    # get_medications,
    get_medications,
# )
)
# from app.agent.tools.image_tool import analyze_image
from app.agent.tools.image_tool import analyze_image
# from app.agent.tools.rag_tool import search_guidelines
from app.agent.tools.rag_tool import search_guidelines
# from app.agent.tools.rxnorm_tool import check_drug_interaction
from app.agent.tools.rxnorm_tool import check_drug_interaction


# logger = logging.getLogger(__name__)
logger = logging.getLogger(__name__)
# TOOL_TIMEOUT_S = 5.0
TOOL_TIMEOUT_S = 5.0

# TOOL_MAP = {
TOOL_MAP = {
    # "get_medications": get_medications,
    "get_medications": get_medications,
    # "get_labs": get_labs,
    "get_labs": get_labs,
    # "get_appointments": get_appointments,
    "get_appointments": get_appointments,
    # "get_care_plan": get_care_plan,
    "get_care_plan": get_care_plan,
    # "get_documents": get_documents,
    "get_documents": get_documents,
    # "check_drug_interaction": check_drug_interaction,
    "check_drug_interaction": check_drug_interaction,
    # "search_guidelines": search_guidelines,
    "search_guidelines": search_guidelines,
    # "analyze_image": analyze_image,
    "analyze_image": analyze_image,
    # "escalate_to_human": escalate_to_human,
    "escalate_to_human": escalate_to_human,
# }
}

# TOOL_CATALOG = [
TOOL_CATALOG = [
    # {
    {
        # "name": "get_medications",
        "name": "get_medications",
        # "description": "Get active medications with full dosing detail from cached patient context.",
        "description": "Get active medications with full dosing detail from cached patient context.",
        # "args_schema": {"session_id": "string"},
        "args_schema": {"session_id": "string"},
    # },
    },
    # {
    {
        # "name": "get_care_plan",
        "name": "get_care_plan",
        # "description": "Get care plan items with goals and activities from cached patient context.",
        "description": "Get care plan items with goals and activities from cached patient context.",
        # "args_schema": {"session_id": "string"},
        "args_schema": {"session_id": "string"},
    # },
    },
    # {
    {
        # "name": "get_appointments",
        "name": "get_appointments",
        # "description": "Get upcoming and past appointments with preparation notes from cached patient context.",
        "description": "Get upcoming and past appointments with preparation notes from cached patient context.",
        # "args_schema": {"session_id": "string"},
        "args_schema": {"session_id": "string"},
    # },
    },
    # {
    {
        # "name": "get_labs",
        "name": "get_labs",
        # "description": "Get lab results with reference ranges and interpretation from cached patient context.",
        "description": "Get lab results with reference ranges and interpretation from cached patient context.",
        # "args_schema": {"session_id": "string"},
        "args_schema": {"session_id": "string"},
    # },
    },
    # {
    {
        # "name": "get_documents",
        "name": "get_documents",
        # "description": "Get discharge summaries or after-visit note content.",
        "description": "Get discharge summaries or after-visit note content.",
        # "args_schema": {"session_id": "string"},
        "args_schema": {"session_id": "string"},
    # },
    },
    # {
    {
        # "name": "check_drug_interaction",
        "name": "check_drug_interaction",
        # "description": "Check RxNorm for interaction severity and description for drug combinations.",
        "description": "Check RxNorm for interaction severity and description for drug combinations.",
        # "args_schema": {"rxcuis": "list[string]", "session_id": "string"},
        "args_schema": {"rxcuis": "list[string]", "session_id": "string"},
    # },
    },
    # {
    {
        # "name": "search_guidelines",
        "name": "search_guidelines",
        # "description": "Search guideline RAG for top reranked evidence chunks.",
        "description": "Search guideline RAG for top reranked evidence chunks.",
        # "args_schema": {"query": "string"},
        "args_schema": {"query": "string"},
    # },
    },
    # {
    {
        # "name": "analyze_image",
        "name": "analyze_image",
        # "description": "Analyze a patient-uploaded image in plain language.",
        "description": "Analyze a patient-uploaded image in plain language.",
        # "args_schema": {"image_b64": "string", "patient_context_summary": "string"},
        "args_schema": {"image_b64": "string", "patient_context_summary": "string"},
    # },
    },
    # {
    {
        # "name": "escalate_to_human",
        "name": "escalate_to_human",
        # "description": "Escalate to a human by writing a FHIR flag and notifying the clinic webhook.",
        "description": "Escalate to a human by writing a FHIR flag and notifying the clinic webhook.",
        # "args_schema": {"session_id": "string", "patient_id": "string|null", "reason": "string"},
        "args_schema": {"session_id": "string", "patient_id": "string|null", "reason": "string"},
    # },
    },
# ]
]


def _default_tool_calls_from_question(question: str, session_id: str) -> list[dict]:
    q = (question or "").lower()
    medication_hints = (
        "medication",
        "medications",
        "medicine",
        "meds",
        "pill",
        "pills",
        "dose",
        "dosage",
        "when should i take",
        "when can i take",
        "with meals",
        "before meal",
        "after meal",
    )
    if any(hint in q for hint in medication_hints):
        # Deterministic retrieval for medication timing/usage questions.
        return [
            {"name": "get_medications", "args": {"session_id": session_id}},
            {"name": "get_care_plan", "args": {"session_id": session_id}},
        ]
    return []


# async def _run_safe(name: str, args: dict) -> tuple[str, str | None]:
async def _run_safe(name: str, args: dict) -> tuple[str, str | None]:
    # fn = TOOL_MAP.get(name)
    fn = TOOL_MAP.get(name)
    # if not fn:
    if not fn:
        # logger.warning("Unknown tool requested: %s", name)
        logger.warning("Unknown tool requested: %s", name)
        # return name, None
        return name, None

    # for attempt in range(2):
    for attempt in range(2):
        # try:
        try:
            # result = await asyncio.wait_for(fn.ainvoke(args), timeout=TOOL_TIMEOUT_S)
            result = await asyncio.wait_for(fn.ainvoke(args), timeout=TOOL_TIMEOUT_S)
            # return name, str(result)
            return name, str(result)
        # except asyncio.TimeoutError:
        except asyncio.TimeoutError:
            # logger.warning("Tool %s timed out on attempt %s", name, attempt + 1)
            logger.warning("Tool %s timed out on attempt %s", name, attempt + 1)
            # if attempt == 1:
            if attempt == 1:
                # return name, None
                return name, None
        # except Exception:  # noqa: BLE001
        except Exception:  # noqa: BLE001
            # logger.exception("Tool %s failed on attempt %s", name, attempt + 1)
            logger.exception("Tool %s failed on attempt %s", name, attempt + 1)
            # if attempt == 1:
            if attempt == 1:
                # return name, None
                return name, None
    # return name, None
    return name, None


# async def tool_executor_node(state: AgentState) -> dict:
async def tool_executor_node(state: AgentState) -> dict:
    # calls = state.get("tool_calls", [])
    calls = state.get("tool_calls", [])
    # if not calls:
    if not calls:
        question = state["messages"][-1].content if state.get("messages") else ""
        calls = _default_tool_calls_from_question(question, state["session_id"])
    if not calls:
        # planner_messages = list(state.get("messages", []))
        planner_messages = list(state.get("messages", []))
        # calls = await call_medgemma_tool_planner(state["system_prompt"], planner_messages, TOOL_CATALOG)
        calls = await call_medgemma_tool_planner(state["system_prompt"], planner_messages, TOOL_CATALOG)
        # calls = _hydrate_tool_calls(calls, state)
        calls = _hydrate_tool_calls(calls, state)
    # if not calls:
    if not calls:
        # return {"tool_results": {}}
        return {"tool_results": {}}

    # # Independent tools are executed together to reduce end-to-end latency.
    # Independent tools are executed together to reduce end-to-end latency.
    # results = await asyncio.gather(*[_run_safe(call["name"], call["args"]) for call in calls])
    results = await asyncio.gather(*[_run_safe(call["name"], call["args"]) for call in calls])
    # tool_results = {name: payload for name, payload in results if payload is not None}
    tool_results = {name: payload for name, payload in results if payload is not None}
    # return {"tool_results": tool_results}
    return {"tool_results": tool_results}


# def _hydrate_tool_calls(calls: list[dict], state: AgentState) -> list[dict]:
def _hydrate_tool_calls(calls: list[dict], state: AgentState) -> list[dict]:
    # hydrated = []
    hydrated = []
    # for call in calls:
    for call in calls:
        # name = call.get("name")
        name = call.get("name")
        # if name not in TOOL_MAP:
        if name not in TOOL_MAP:
            # logger.warning("Planner returned unsupported tool: %s", name)
            logger.warning("Planner returned unsupported tool: %s", name)
            # continue
            continue
        # args = dict(call.get("args") or {})
        args = dict(call.get("args") or {})
        # if name in {"get_medications", "get_care_plan", "get_appointments", "get_labs", "get_documents"}:
        if name in {"get_medications", "get_care_plan", "get_appointments", "get_labs", "get_documents"}:
            # args.setdefault("session_id", state["session_id"])
            args.setdefault("session_id", state["session_id"])
        # elif name == "check_drug_interaction":
        elif name == "check_drug_interaction":
            # args.setdefault("session_id", state["session_id"])
            args.setdefault("session_id", state["session_id"])
            # args.setdefault("rxcuis", [])
            args.setdefault("rxcuis", [])
        # elif name == "search_guidelines":
        elif name == "search_guidelines":
            # if not args.get("query") and state.get("messages"):
            if not args.get("query") and state.get("messages"):
                # args["query"] = state["messages"][-1].content
                args["query"] = state["messages"][-1].content
        # elif name == "analyze_image":
        elif name == "analyze_image":
            # if not state.get("image_b64"):
            if not state.get("image_b64"):
                # continue
                continue
            # args.setdefault("image_b64", state["image_b64"])
            args.setdefault("image_b64", state["image_b64"])
            # args.setdefault("patient_context_summary", state["system_prompt"][:500])
            args.setdefault("patient_context_summary", state["system_prompt"][:500])
        # elif name == "escalate_to_human":
        elif name == "escalate_to_human":
            # args.setdefault("session_id", state["session_id"])
            args.setdefault("session_id", state["session_id"])
            # args.setdefault("reason", "model_requested_escalation")
            args.setdefault("reason", "model_requested_escalation")
        # hydrated.append({"name": name, "args": args})
        hydrated.append({"name": name, "args": args})
    # return hydrated
    return hydrated
