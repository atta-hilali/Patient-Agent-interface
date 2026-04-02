# from typing import Any, Dict, List, Optional, TypedDict
from typing import Any, Dict, List, Optional, TypedDict

# from langchain_core.messages import BaseMessage
from langchain_core.messages import BaseMessage


# class AgentState(TypedDict):
class AgentState(TypedDict):
    # messages: List[BaseMessage]
    messages: List[BaseMessage]
    # session_id: str
    session_id: str
    # patient_ctx_key: str
    patient_ctx_key: str
    # system_prompt: str
    system_prompt: str
    # clinic_yaml: str
    clinic_yaml: str
    # history_summary: str
    history_summary: str
    # image_b64: Optional[str]
    image_b64: Optional[str]
    # modality: str
    modality: str
    # tool_calls: List[dict]
    tool_calls: List[dict]
    # tool_results: Dict[str, Any]
    tool_results: Dict[str, Any]
    # draft_response: Optional[str]
    draft_response: Optional[str]
    # raw_citations: List[dict]
    raw_citations: List[dict]
    # safety_result: Optional[dict]
    safety_result: Optional[dict]
    # safety_message_key: Optional[str]
    safety_message_key: Optional[str]
    # escalation_flag: bool
    escalation_flag: bool
    # escalation_reason: Optional[str]
    escalation_reason: Optional[str]
    # stop_severity: Optional[str]
    stop_severity: Optional[str]
    # intent_route: Optional[str]
    intent_route: Optional[str]
    # safety_route: Optional[str]
    safety_route: Optional[str]
    # ai_disabled: bool
    ai_disabled: bool
