from database.crud import create_conversation
from graph import build_graph
# from langgraph.graph import StateGraph, END
# from typing import TypedDict, Optional, Any
def analyze_csv(file_path, query):
    state = {
        "file_path": file_path,
        "query": query,
        "conversation_id": create_conversation()  # this should be generated uniquely for each conversation
    }

    result = build_graph().invoke(state)

    return {
        "result": result.get("result"),
        "insights": result.get("insights"),
        "error": result.get("error"),
        "chart_path": result.get("chart_path")
    }


# ================= RUN =================
response = analyze_csv(
    "public/download.csv",
    
    "Show a scatter plot of price vs revenue"
)

print("\n===== RESULT =====")
print(response["result"])

print("\n===== INSIGHTS =====")
print(response["insights"])

print("\n===== CHART PATH =====")
print(response["chart_path"])

print("\n===== ERROR =====")
print(response["error"])