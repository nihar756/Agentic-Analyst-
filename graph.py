
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, Any
from agents.code_agent import code_agent
from agents.execution_agent import execution_agent
from agents.insight_agent import insight_agent
from agents.query_agent import query_agent
from agents.schema_agent import schema_agent
from agents.visualization_agent import visualization_agent
from agents.save_user_message_agent import save_user_message_agent
from agents.save_query_agent import save_query_agent
from agents.save_chart_agent import save_chart_agent
from agents.save_assistant_agent import save_assistant_agent
from agents.save_state_agent import save_state_agent
import pandas as pd

# from asyncio import graph

class AgentState(TypedDict):
    file_path: str
    query: str

    dataset_id:int
    conversation_id:int
    
    df: Optional[pd.DataFrame]
    schema: Optional[dict]

    parsed_query: Optional[str]
    code: Optional[str]

    result: Optional[Any]
    error: Optional[str]

    insights: Optional[str]
    chart_path: Optional[str]


def route_after_execute(state):
    if state["error"]:
        return "error"
    return "insight"


def build_graph():
    graph = StateGraph(AgentState)

    # graph.add_node("schema", schema_agent)
    # graph.add_node("query", query_agent)
    # graph.add_node("code", code_agent)
    # graph.add_node("execute", execution_agent)
    # graph.add_node("visualization", visualization_agent)
    # graph.add_node("insight", insight_agent)
    # # graph.add_node("error", error_agent)
    
    graph.add_node("schema", schema_agent)

    graph.add_node(
        "save_user_message",
        save_user_message_agent
    )

    graph.add_node("query", query_agent)

    graph.add_node("code", code_agent)

    graph.add_node(
        "save_query",
        save_query_agent
    )

    graph.add_node(
        "execute",
        execution_agent
    )

    graph.add_node(
        "save_state",
        save_state_agent
    )

    graph.add_node(
        "visualization",
        visualization_agent
    )

    graph.add_node(
        "save_chart",
        save_chart_agent
    )

    graph.add_node(
        "insight",
        insight_agent
    )

    graph.add_node(
        "save_assistant",
        save_assistant_agent
    )

    graph.set_entry_point("schema")

    # graph.add_edge("schema", "query")
    # graph.add_edge("query", "code")
    # graph.add_edge("code", "execute")

    # graph.add_edge("execute", "visualization")
    # graph.add_edge("visualization", "insight")
    # graph.add_edge("insight", END)
    
    graph.add_edge("schema","save_user_message")
    graph.add_edge("save_user_message","query")
    graph.add_edge("query","code")
    graph.add_edge("code","save_query")
    graph.add_edge("save_query","execute")
    graph.add_edge("execute","save_state")
    graph.add_edge("save_state","visualization")
    graph.add_edge("visualization","save_chart")
    graph.add_edge("save_chart","insight")
    graph.add_edge("insight","save_assistant")
    graph.add_edge("save_assistant",END)
    return graph.compile()