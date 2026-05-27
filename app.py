from graph import build_graph
# from langgraph.graph import StateGraph, END
# from typing import TypedDict, Optional, Any
def analyze_csv(file_path, query):
    state = {
        "file_path": file_path,
        "query": query
    }

    result = build_graph().invoke(state)

    return {
        "result": result.get("result"),
        "insights": result.get("insights"),
        "error": result.get("error")
    }


# ================= RUN =================
response = analyze_csv(
    "public/download.csv",
    
    "min and max price per category"
)

print("\n===== RESULT =====")
print(response["result"])

print("\n===== INSIGHTS =====")
# print(response["insights"])

print("\n===== ERROR =====")
print(response["error"])