
# we will use pydantic ouutput parser later once we have the basic version working. For now we will just do json parsing and error handling
from pydantic import BaseModel, Field
from typing import List, Dict, Literal
from langchain_core.output_parsers import PydanticOutputParser
import pandas as pd
import json
import os
import re
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from utils.llm import get_llm
class Aggregation(BaseModel):
    column: str = Field(
        description="Numerical column for aggregation"
    )
    operation: Literal["min", "max", "mean", "sum", "count"] = Field(
        description="Aggregation operation"
    )


class Filter(BaseModel):
    column: str = Field(description="Column to filter")
    operation: str = Field(description="Operator or operation like =, >, <, >=, <=")
    value: str = Field(description="Value to compare against")


class QuerySchema(BaseModel):
    task: str
    columns: List[str]
    filters: List[Dict]
    groupby: List[str]
    limit: int = 0
    sort_by: str = ""
    order: str = ""
    aggregation: List[Dict[str, str]]   # ✅ changed
    visualization: Dict
    
def clean_json(text):
    text = text.strip()
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    return text


def safe_json_load(llm, raw):
    try:
        return json.loads(raw)
    except:
        fix_prompt = f"""
        Convert this into valid JSON only. No explanation.

        {raw}
        """
        fixed = llm.invoke(fix_prompt).content
        return json.loads(clean_json(fixed))

def query_agent(state):
    llm = get_llm()

    schema = state["schema"]

    # ✅ Extract structured info
    numerical_cols = []
    categorical_cols = []

    for col, dtype in schema["dtypes"].items():
        if "int" in dtype or "float" in dtype:
            numerical_cols.append(col)
        else:
            categorical_cols.append(col)
    
    parser= PydanticOutputParser(pydantic_object=QuerySchema)
    format_instructions = """
    Return JSON in this exact format:

    {
        "task": "string",
        "columns": ["column1", "column2"],
        "filters": [],
        "groupby": ["column"],
        "aggregation": [
            {
            "column": "column_name",
            "operation": "min | max | mean | sum | count"
            }
        ],
        "visualization": {
            "type": "bar | line | scatter | histogram",
            "x": "column_name",
            "y": "column_name",
            "title": "string",
            "xlabel": "string",
            "ylabel": "string"
        }
    }
    """

    prompt = f"""
    Convert user query into STRICT JSON.

    IMPORTANT RULES:
    - Output ONLY valid JSON
    - DO NOT use $ref or $def or any other non-standard JSON constructs
    - No markdown
    - No explanation
    - Must be complete JSON

    DATA UNDERSTANDING:
    Numerical columns: {numerical_cols}
    Categorical columns: {categorical_cols}

    RULES FOR LOGIC:
    IMPORTANT RULE:
    
    - aggregation is OPTIONAL
    - If query is only filtering or selecting → aggregation = []
    - Use aggregation ONLY on numerical columns
    - Use groupby ONLY on categorical columns
    - Use filters based on column values
    - "top k highest" OR "top k" → order = "desc"
    - "top k lowest" OR "bottom k" → order = "asc"
    - "lowest", "smallest", "minimum" → order = "asc"
    - "highest", "largest", "maximum" → order = "desc"
    - "top k" → limit = k
    - "top" -> order = "desc"
    - "bottom" → order = "asc"
    - Combine groupby + aggregation when needed
    - If groupby exists → use df.groupby(...)
    - aggregation is a LIST
    - apply aggregation on grouped column
    - Always detect column name if mentioned
    - Example:
        "fill nulls in price with mean"
        → column = "price"

    Supported operations:
    - aggregation (min, max, avg, sum)
    - groupby (for "per category", "per region", etc.)

    SORTING RULES:
    - "sort", "ascending", "descending" → task = "sort"
    - extract column → sort_by
    - ascending → order = "asc"
    - descending → order = "desc"
    
    DATE RULES:
    - "after YYYY-MM-DD" → operator = ">"
    - "before YYYY-MM-DD" → operator = "<"
    - "between X and Y" → two filters
    - "last N days" → dynamic filter (today - N)
    - if the query has taxual date references like "january", "february", "last month", "last year" → try to convert to date filters
    
    SPECIAL TASKS:
    - If query asks about missing values → task = "missing_values"
    - If query asks about unique values → task = "unique_values"
    - If query asks about dataset size → task = "shape"

    CLEANING TASKS
    - remove nulls → "drop_nulls"
    - fill nulls with mean → "fill_nulls_mean"
    - fill nulls with value → "fill_nulls_value"
    - drop duplicates → "drop_duplicates"
    - type conversion → "convert_type"
    
    VISUALIZATION RULES:
    - If query asks for a chart/plot/graph, populate the "visualization" object with the corresponding type, x, y, title, xlabel, ylabel.
    - Otherwise, leave "visualization" as an empty dictionary {{}}.
    CRITICAL RULE:
    - If query is only filtering (>, <, =, etc.) → aggregation MUST be []
    - NEVER add aggregation unless user explicitly asks (max, min, avg, total)
    - Filtering queries should return raw rows, NOT aggregated values
    Example:
    {{
    "task": "aggregation",
    "columns": ["price"],
    "filters": [],
    "groupby": [],
    "aggregation": [
        {{"column": "price", "operation": "max"}}
    ],
    "visualization": {{}}
    }}
    Query: {state["query"]}
    {parser.get_format_instructions()}
    """
    # Format:
    # {{
    #   "task": "...",
    #   "columns": [],
    #   "filters": [],
    #   "groupby": [],
    #   "aggregation": [{{
    #         "column": "",
    #         "operation": ""
    #   }}],
    #   "visualization": {{}}
    # }}

    response = llm.invoke(prompt)

    cleaned = clean_json(response.content)
    if not cleaned.strip():
        return {
            "parsed_query": "",
            "error": "Empty response from LLM"
        }
    # print(f"Parsed query: {cleaned}")
    
    # experimental code to validate JSON structure using pydantic
    raw= response.content
    def fix_refs(obj):
        if isinstance(obj, dict):
            if "$ref" in obj:
                return {}   # remove bad refs
            return {k: fix_refs(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [fix_refs(x) for x in obj]
        return obj

    try:
        parsed = parser.parse(raw)
        parsed = parsed.dict()
    except Exception:
        parsed = safe_json_load(llm, raw)
        parsed = fix_refs(parsed)
        
    # required_keys = ["task","columns","filters","groupby","aggregation","visualization"]

    # for key in required_keys:
    #     if key not in parsed:
    #         raise ValueError(f"Missing key: {key}")
    print(f"Parsed query: {parsed}")
    return {
        "parsed_query": parsed
    }
