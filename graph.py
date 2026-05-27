
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, Any
from agents.code_agent import code_agent
from agents.execution_agent import execution_agent
from agents.insight_agent import insight_agent
from agents.query_agent import query_agent
from agents.schema_agent import schema_agent
import pandas as pd

class AgentState(TypedDict):
    file_path: str
    query: str

    df: Optional[pd.DataFrame]
    schema: Optional[dict]

    parsed_query: Optional[str]
    code: Optional[str]

    result: Optional[Any]
    error: Optional[str]

    insights: Optional[str]


def route_after_execute(state):
    if state["error"]:
        return "error"
    return "insight"


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("schema", schema_agent)
    graph.add_node("query", query_agent)
    graph.add_node("code", code_agent)
    graph.add_node("execute", execution_agent)
    graph.add_node("insight", insight_agent)
    # graph.add_node("error", error_agent)

    graph.set_entry_point("schema")

    graph.add_edge("schema", "query")
    graph.add_edge("query", "code")
    graph.add_edge("code", "execute")

    graph.add_edge("execute","insight")
    graph.add_edge("insight", END)
    return graph.compile()