import pandas as pd
import json
import os
import re
import sys
import datetime
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from agents.schema_agent import safe_json_load
from utils.llm import get_llm


def validate_query(parsed, schema):
    num_cols = [c for c, d in schema["dtypes"].items() if "int" in d or "float" in d]
    all_cols = schema["columns"]

    # ✅ mapping
    op_map = {
    "avg": "mean",
    "average": "mean",
    "total": "sum",
    "count": "count"
    }

    # groupby validation
    for col in parsed.get("groupby", []):
        if col not in all_cols:
            raise ValueError(f"Invalid groupby column: {col}")

    # if not parsed.get("aggregation"):
    #     raise ValueError("Aggregation cannot be empty")
    aggregation = parsed.get("aggregation", [])
    if aggregation:
        for agg in aggregation:
            if "column" not in agg or "operation" not in agg:
                raise ValueError("Invalid aggregation format")

            # ✅ normalize operation
            op = agg["operation"].lower()
            if op in op_map:
                op = op_map[op]

            if op not in ["min", "max", "mean", "sum", "count"]:
                raise ValueError(f"Invalid aggregation operation: {agg['operation']}")

            # ✅ overwrite normalized value
            agg["operation"] = op

            if agg["column"] not in num_cols:
                raise ValueError(f"Aggregation must be on numerical column: {agg['column']}")

    return parsed




# def clean_code(text):
#     text = text.strip()
#     text = re.sub(r"```python", "", text)
#     text = re.sub(r"```", "", text)
#     return text.strip()
def clean_code(text):
    text = text.strip()

    text = re.sub(r"```python", "", text)
    text = re.sub(r"```", "", text)
    text = re.sub(r"Python", "", text)
    lines = text.split("\n")

    cleaned = []

    for line in lines:
        if line.strip().lower().startswith("here is"):
            continue

        if line.strip().lower().startswith("let me know"):
            continue

        cleaned.append(line)

    return "\n".join(cleaned).strip()

def code_agent(state):
    llm = get_llm()
    
    try:
        parsed= state["parsed_query"]
        # parsed = safe_json_load(llm, state["parsed_query"])
        parsed = validate_query(parsed, state["schema"])
    except Exception as e:
        return {
            "code": "",
            "error": f"JSON parsing failed: {str(e)}"
        }
    task = parsed.get("task", "")
    col = parsed.get("column", "")
    value = parsed.get("value", "")
    dtype = parsed.get("dtype", "")
    if task == "missing_values":
        return {"code": "result = df.isnull().sum()"}

    if task == "unique_values":
        return {"code": "result = df.nunique()"}

    if task == "shape":
        return {"code": "result = df.shape"}
    if task == "drop_nulls":
        return {"code": "df = df.dropna()\nresult = df"}

    if task == "fill_nulls_mean":
        return {"code": f"df['{col}'] = df['{col}'].fillna(df['{col}'].mean())\nresult = df"}

    if task == "fill_nulls_value":
        return {"code": f"df['{col}'] = df['{col}'].fillna({repr(value)})\nresult = df"}

    if task == "drop_duplicates":
        return {"code": "df = df.drop_duplicates()\nresult = df"}

    if task == "convert_type":
        return {"code": f"df['{col}'] = df['{col}'].astype('{dtype}')\nresult = df"}
    prompt = f"""
    Generate pandas code only.No explanation needed.

    STRICT Rules:
    - Output ONLY raw Python code.
    - Do NOT write:
            - "Here is the Python code:"
            - explanations
            - comments
            - markdown
            - backticks
            - any text before or after the code
            
    - The dataframe already contains the correct data.

    - Your job is ONLY to generate plotting commands(if needed).
    - You are NOT responsible for data preparation.
    - You are NOT allowed to create, modify, aggregate, filter, or load data.
    - You may only read from df_to_plot and create the visualization(if visualization is needed).
    - The first character of your response must be valid Python.
    - The last character of your response must be valid Python.
    - Any non-Python text will cause execution failure.
    - Generate ONLY ONE valid solution
    - Read the user query and schema carefully
    - Understand the intent of the query and the structure of the data
    - DO NOT solely rely on parsed query - use it as a guide but apply your understanding of the task
    - Generate code based on user query ,parsed query and schema
    - DO NOT generate multiple alternatives
    - STOP after writing final code
    - Use `df` as input
    - DO NOT redefine df
    - DO NOT generate sample data
    - Do not create new dataframes
    - Store final output in variable `result`
    - Only Python code
    - No explanation
    - No markdown
    - Handle groupby if present
    
    GROUPBY RULE:
    - Use column names directly:
        df.groupby("column")
    - If aggregation is EMPTY → DO NOT use groupby
    - If only filters exist → return filtered dataframe
    - DO NOT invent groupby when not needed
    
    AGGREGATION RULE:
    - Use ONLY these formats:
    - ALWAYS use named aggregation syntax
    
    GENERAL FORMAT:
        result = df.groupby("group_col").agg(
            new_column_name=("target_column", "aggregation_operation")
        ).reset_index()

        EXAMPLE:
        result = df.groupby("category").agg(
            min_price=("price", "min"),
            max_price=("price", "max")
        ).reset_index()


    INVALID (NEVER DO):
    - df.groupby(df["col"]) ❌
    - eval(...) ❌
    - df['col'].unique() ❌
    - {{col: df[col].max()}} ❌
    - df.groupby(...).agg({{"col": ["min", "max"]}}) ❌
    
    OUTPUT:
    - Store result in variable `result`
    - Only Python code
    - No explanation

    user query= {state['query']}
    schema: {state['schema']} 
    Schema:
    Columns: {state["schema"]["columns"]}
    Dtypes: {state["schema"]["dtypes"]}
    parsed query: {parsed}
    Sample:
    {state["df"].head(3).to_dict()}
    """
    # JSON:
    # {parsed}
    # df: {state['df'].head().to_dict()}

    response = llm.invoke(prompt)
    cleaned_code = clean_code(response.content)
    print(f"Generated code: {cleaned_code}")
    code = cleaned_code
    
    for col in state["schema"].get("date_columns", []):
        code += f"\ndf['{col}'] = pd.to_datetime(df['{col}'],errors='coerce')"
    
    # if parsed.get("sort_by"):
    #     order = parsed.get("order", "asc")
    #     ascending = (order == "asc")
    #     code += f"\nresult = result.sort_values(by='{parsed['sort_by']}', ascending={ascending})"
    if parsed.get("sort_by"):
        order = parsed.get("order", "asc")
        ascending = (order == "asc")

        code += f"""
    if '{parsed['sort_by']}' in result.columns:
        result = result.sort_values(
            by='{parsed['sort_by']}',
            ascending={ascending}
        )
    """
    if parsed.get("limit", 0) > 0:
        code += f"\nresult = result.head({parsed['limit']})"
        
    for f in parsed.get("filters",[]):
        if not f.get("column"):
            continue
        col = f["column"]
        op = f.get("operator") or f.get("operation")
        val = f.get("value")
        # if op == "=":
        #     op = "=="
            
        if col in state["schema"].get("date_columns", []):
            val = f"\ndf['{col}']=pd.to_datetime('{val}', errors='coerce')"
        elif isinstance(val, str):
            val = f"'{val}'"
            
        code += f"\ndf = df[df['{col}'] {op} {val}]"
        
    if parsed.get("task") == "last_n_days":
        col = parsed.get("column")
        days = parsed.get("value")

        code = f"""
    df['{col}'] = pd.to_datetime(df['{col}'], errors='coerce')
    cutoff = pd.Timestamp.today() - pd.Timedelta(days={days})
    df = df[df['{col}'] >= cutoff]
    result = df
    """
    
    if parsed.get("filters") and not parsed.get("aggregation") and not parsed.get("groupby"):
        code = ""

        for f in parsed["filters"]:
            if not f.get("column"):
                continue
            col = f["column"]
            op = f["operator"]
            val = f.get("value")

            # if op == "=":
            #     op = "=="

            if isinstance(val, str):
                val = f"'{val}'"

            code += f"\ndf = df[df['{col}'] {op} {val}]"

        code += "\nresult = df"
    
    
    # multiple aggregations
    # agg_dict = {}
    # for agg in parsed.get("aggregation", []):
    #     col = agg["column"]
    #     op = agg["operation"]

    #     if col not in agg_dict:
    #         agg_dict[col] = []
    #     agg_dict[col].append(op)

    # if parsed.get("groupby"):
    #     group_col = parsed["groupby"][0]
    #     code += f"\nresult = df.groupby('{group_col}').agg({agg_dict}).reset_index()"
    # else:
    #     code += f"\nresult = df.agg({agg_dict})"
        
    # code += "\nif isinstance(result.columns, pd.MultiIndex):\n    result.columns = [col[0] for col in result.columns.values]"
    
    if not parsed.get("groupby") and "groupby" in code:
        return {
            "code": "",
            "error": "Invalid groupby generated"
        }
    return {
        "code": code
    }
    

