# from langgraph.graph import END, StateGraph
from langgraph.graph import END, StateGraph

# from app.agent.nodes.intent import intent_node
from app.agent.nodes.intent import intent_node
# from app.agent.nodes.medgemma import medgemma_node
from app.agent.nodes.medgemma import medgemma_node
# from app.agent.nodes.output import output_node
from app.agent.nodes.output import output_node
# from app.agent.nodes.safety import safety_node
from app.agent.nodes.safety import safety_node
# from app.agent.nodes.tools import tool_executor_node
from app.agent.nodes.tools import tool_executor_node
# from app.agent.state import AgentState
from app.agent.state import AgentState


# def route_intent(state: AgentState) -> str:
def route_intent(state: AgentState) -> str:
    # return state.get("intent_route") or "direct"
    return state.get("intent_route") or "direct"


# def route_safety(state: AgentState) -> str:
def route_safety(state: AgentState) -> str:
    # return state.get("safety_route") or "safe"
    return state.get("safety_route") or "safe"


# graph = StateGraph(AgentState)
graph = StateGraph(AgentState)
# graph.add_node("intent", intent_node)
graph.add_node("intent", intent_node)
# graph.add_node("tools", tool_executor_node)
graph.add_node("tools", tool_executor_node)
# graph.add_node("medgemma", medgemma_node)
graph.add_node("medgemma", medgemma_node)
# graph.add_node("safety", safety_node)
graph.add_node("safety", safety_node)
# graph.add_node("output", output_node)
graph.add_node("output", output_node)

# graph.set_entry_point("intent")
graph.set_entry_point("intent")
# graph.add_conditional_edges(
graph.add_conditional_edges(
    # "intent",
    "intent",
    # route_intent,
    route_intent,
    # {
    {
        # "tools": "tools",
        "tools": "tools",
        # "direct": "medgemma",
        "direct": "medgemma",
        # "escalate": "output",
        "escalate": "output",
    # },
    },
# )
)
# graph.add_edge("tools", "medgemma")
graph.add_edge("tools", "medgemma")
# graph.add_edge("medgemma", "safety")
graph.add_edge("medgemma", "safety")
# graph.add_conditional_edges(
graph.add_conditional_edges(
    # "safety",
    "safety",
    # route_safety,
    route_safety,
    # {
    {
        # "safe": "output",
        "safe": "output",
        # "escalate": "output",
        "escalate": "output",
    # },
    },
# )
)
# graph.add_edge("output", END)
graph.add_edge("output", END)

# agent_graph = graph.compile()
agent_graph = graph.compile()
