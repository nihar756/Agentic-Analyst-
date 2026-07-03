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

    has_chart = bool(state.get("chart_path"))
    query_lower = state.get("query", "").lower()
    
    # We want insights if a chart is generated, or if the user asks for insights/explanations explicitly.
    insight_keywords = ["insight", "explain", "summarize", "summary", "trend", "describe", "analysis", "why", "what does", "interpret"]
    wants_insights = has_chart or any(kw in query_lower for kw in insight_keywords)

    df_str = ""
    if state.get("df") is not None:
        try:
            df_str = state["df"].head(10).to_string()
        except:
            df_str = "Error formatting dataframe head"

    if wants_insights:
        if has_chart:
            prompt = f"""
            You are a Senior Data Analyst. A chart was successfully generated for the user's query.
            Your job is to analyze the generated chart and summarize the key insights/trends it presents clearly and concisely.
            
            STRICT GROUNDING RULES:
            1. Base your insights ONLY on the provided "Operation Result" and the "Sample/Latest Dataset State".
            2. NEVER invent, assume, or hallucinate any numbers, products, dates, regions, or statistics that are not present in the provided context.
            3. Do NOT extrapolate or guess trends over time unless they are explicitly calculated in the "Operation Result".
            4. If the "Operation Result" is None or empty, explain that no results were returned.
            
            GUIDELINES:
            1. Keep your explanation concise (1-2 paragraphs max).
            2. Focus specifically on explaining what the chart shows, highlighting the key insights or trends.
            3. State clearly that the chart is displayed below.
            
            CONTEXT:
            - User Query: {state["query"]}
            - Operation Result: {state["result"]}
            - Sample/Latest Dataset State:
            {df_str}
            """
        else:
            prompt = f"""
            You are a Senior Data Analyst. Your job is to explain the execution results of the user's query clearly and concisely, focusing on providing data-driven insights.
            
            STRICT GROUNDING RULES:
            1. Base your answer ONLY on the provided "Operation Result" and the "Sample/Latest Dataset State".
            2. NEVER invent, assume, or hallucinate any numbers, products, dates, regions, or statistics that are not present in the provided context.
            3. Do NOT extrapolate or guess trends over time unless they are explicitly calculated in the "Operation Result".
            4. If the "Operation Result" is None or empty, explain that no results were returned.
            
            GUIDELINES:
            1. Summarize the key answers to the user's query.
            2. Highlight trends or patterns present in the result.
            3. Keep the response to 1-2 paragraphs.
            
            CONTEXT:
            - User Query: {state["query"]}
            - Operation Result: {state["result"]}
            - Sample/Latest Dataset State:
            {df_str}
            """
    else:
        # User doesn't need detailed analytical insights. Give a concise direct answer or action confirmation.
        prompt = f"""
        You are a helpful data analyst assistant. The user performed a query or data mutation.
        Provide a very brief, direct, one-sentence confirmation or direct answer.
        
        RULES:
        1. Do NOT write paragraphs, bullet points, or analytical insights.
        2. Be extremely concise (maximum 1-2 sentences).
        3. If the operation was a data mutation (e.g. update, delete, add, fill, drop), simply confirm the action (e.g., "The dataset has been successfully updated to remove null values.").
        4. If it was a simple query or retrieval, state the direct result clearly (e.g., "The average salary is $65,000.").
        
        CONTEXT:
        - User Query: {state["query"]}
        - Operation Result: {state["result"]}
        - Sample/Latest Dataset State:
        {df_str}
        """

    response = llm.invoke(prompt)

    return {
        "insights": response.content.strip()
    }