# # app/agent/nodes/intent.py
# app/agent/nodes/intent.py
# from app.agent.state import AgentState
from app.agent.state import AgentState
# from app.agent.llm_client import call_medgemma_intent
from app.agent.llm_client import call_medgemma_intent

# INTENT_PROMPT = (
INTENT_PROMPT = (
    # "Given the patient question and their medical record summary below,\n"
    "Given the patient question and their medical record summary below,\n"
    # "classify the request as exactly one of:\n"
    "classify the request as exactly one of:\n"
    # "  direct   - can be answered from general context (no specific data lookup needed)\n"
    "  direct   - can be answered from general context (no specific data lookup needed)\n"
    # "  tools    - requires fetching specific data: labs, meds, appointments, guidelines, image\n"
    "  tools    - requires fetching specific data: labs, meds, appointments, guidelines, image\n"
    # "  escalate - contains a safety concern requiring human intervention\n"
    "  escalate - contains a safety concern requiring human intervention\n"
    # "Respond with exactly one word."
    "Respond with exactly one word."
# )
)

# # Tool trigger keywords for fast-path routing (avoids LLM intent call)
# Tool trigger keywords for fast-path routing (avoids LLM intent call)
# TOOL_KEYWORDS = [
TOOL_KEYWORDS = [
    # 'last', 'recent', 'result', 'level', 'value',   # lab questions
    'last', 'recent', 'result', 'level', 'value',   # lab questions
    # 'when is', 'appointment', 'next visit',           # appointment questions
    'when is', 'appointment', 'next visit',           # appointment questions
    # 'interact', 'together', 'mix', 'combine',         # drug interaction
    'interact', 'together', 'mix', 'combine',         # drug interaction
    # 'guideline', 'recommend', 'evidence', 'study',   # RAG questions
    'guideline', 'recommend', 'evidence', 'study',   # RAG questions
    # 'this image', 'this photo', 'look at',           # image analysis
    'this image', 'this photo', 'look at',           # image analysis
    # 'discharge summary', 'after visit', 'document',  # documents
    'discharge summary', 'after visit', 'document',  # documents
    # medication/timing questions
    'medication', 'medications', 'medicine', 'meds',
    'dose', 'dosage', 'pill', 'pills',
    'when should i take', 'when can i take',
    'with meals', 'before meal', 'after meal',
# ]
]

# ESCALATION_KEYWORDS = ['human', 'nurse', 'doctor', 'care team', 'person']
ESCALATION_KEYWORDS = ['human', 'nurse', 'doctor', 'care team', 'person']

# async def intent_node(state: AgentState) -> dict:
async def intent_node(state: AgentState) -> dict:
    # question = state['messages'][-1].content if state['messages'] else ''
    question = state['messages'][-1].content if state['messages'] else ''

    # # Fast-path only decides whether the tool-planning path is needed.
    # Fast-path only decides whether the tool-planning path is needed.
    # q_lower = question.lower()
    q_lower = question.lower()
    # if any(term in q_lower for term in ESCALATION_KEYWORDS) and any(
    if any(term in q_lower for term in ESCALATION_KEYWORDS) and any(
        # request in q_lower for request in ['talk to', 'speak with', 'connect me', 'call me']
        request in q_lower for request in ['talk to', 'speak with', 'connect me', 'call me']
    # ):
    ):
        # return {'intent_route': 'escalate', 'escalation_flag': True, 'escalation_reason': 'explicit_human_request'}
        return {'intent_route': 'escalate', 'escalation_flag': True, 'escalation_reason': 'explicit_human_request'}
    # if any(kw in q_lower for kw in TOOL_KEYWORDS) or state.get('image_b64'):
    if any(kw in q_lower for kw in TOOL_KEYWORDS) or state.get('image_b64'):
        # return {'intent_route': 'tools', 'tool_calls': []}
        return {'intent_route': 'tools', 'tool_calls': []}

    # # LLM classification for ambiguous questions
    # LLM classification for ambiguous questions
    # intent = await call_medgemma_intent(INTENT_PROMPT, question)
    intent = await call_medgemma_intent(INTENT_PROMPT, question)
    # intent = intent.strip().lower()
    intent = intent.strip().lower()

    # if intent == 'escalate':
    if intent == 'escalate':
        # return {'intent_route': 'escalate', 'escalation_flag': True,
        return {'intent_route': 'escalate', 'escalation_flag': True,
                # 'escalation_reason': 'intent_router_flag'}
                'escalation_reason': 'intent_router_flag'}
    # if intent == 'tools':
    if intent == 'tools':
        # return {'intent_route': 'tools', 'tool_calls': []}
        return {'intent_route': 'tools', 'tool_calls': []}
    # return {'intent_route': 'direct'}
    return {'intent_route': 'direct'}
