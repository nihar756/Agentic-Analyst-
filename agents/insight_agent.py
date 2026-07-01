import pandas as pd
import json
import os
import re
import sys
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
from utils.llm import get_llm

def insight_agent(state):
    llm = get_llm()

    chart_info = "A chart was successfully generated. Tell the user it is displayed below." if state.get("chart_path") else ""

    df_str = ""
    if state.get("df") is not None:
        try:
            df_str = state["df"].head(10).to_string()
        except:
            df_str = "Error formatting dataframe head"

    prompt = f"""
    You are a Senior Data Analyst. Your job is to explain the execution results of the user's query clearly and concisely.
    
    STRICT GROUNDING RULES:
    1. Base your answer ONLY on the provided "Operation Result" and the "Sample/Latest Dataset State".
    2. NEVER invent, assume, or hallucinate any numbers, products, dates, regions, or statistics that are not present in the provided context.
    3. Do NOT extrapolate or guess trends over time unless they are explicitly calculated in the "Operation Result".
    4. If the "Operation Result" is None or empty, explain that no results were returned.
    
    GUIDELINES:
    1. Summarize the "Operation Result" table/values clearly.
    2. Highlight the key answers to the user's query from the "Operation Result".
    3. {chart_info}
    4. If a data mutation/cleaning operation occurred (like fill nulls, drop duplicates, add row, delete row), summarize the changes made.
    
    CONTEXT:
    - User Query: {state["query"]}
    - Operation Result: {state["result"]}
    - Sample/Latest Dataset State:
    {df_str}
    """

    response = llm.invoke(prompt)

    return {
        "insights": response.content
    }