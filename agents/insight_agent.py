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

    chart_info = f"A chart was successfully generated and saved to: {state.get('chart_path')}. Mention this to the user." if state.get("chart_path") else ""

    prompt = f"""
    Explain insights clearly.
    If result contains:
    - missing values → highlight problematic columns
    - unique values → highlight categorical diversity
    - shape → explain dataset size

    


    Query: {state["query"]}
    Result: {state["result"]}
    data frame: {state["df"]}
    """

    response = llm.invoke(prompt)

    return {
        "insights": response.content
    }