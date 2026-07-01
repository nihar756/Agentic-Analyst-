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
    if isinstance(parsed, list):
        if len(parsed) > 0:
            parsed = parsed[0]
        else:
            parsed = {}
            
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

    # Check if task is a data mutation
    task = parsed.get("task", "").lower()
    is_mutation = any(m_task in task for m_task in ["update", "delete", "add", "drop", "fill", "convert", "insert", "replace", "clean", "modify"])
    if is_mutation:
        return parsed


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
                # If it represents an update or delete, reclassify task as update and bypass error
                if op in ["update", "delete", "add", "insert", "replace", "clean", "modify"]:
                    parsed["task"] = "update"
                    return parsed
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
        stripped = line.strip()
        if stripped.lower().startswith("here is"):
            continue

        if stripped.lower().startswith("let me know"):
            continue

        cleaned.append(line)

    code = "\n".join(cleaned).strip()

    # --- POST-PROCESSING & FIXING COMMON SYNTAX/SEMANTIC ERRORS ---
    
    # 1. Fix assignment to .values[0] or .values
    # e.g., df.loc[cond, 'col'].values[0] = val -> df.loc[cond, 'col'] = val
    # OR df.loc[cond, 'col'].values = val -> df.loc[cond, 'col'] = val
    code = re.sub(r"\.loc\[(.*?)\]\.values(?:\[\d+\])?\s*=\s*(.*)", r".loc[\1] = \2", code)
    
    # 2. Fix chain assignment df.loc[cond]['col'] = val -> df.loc[cond, 'col'] = val
    code = re.sub(r"\.loc\[(.*?)\]\s*\['(.*?)'\]\s*=\s*(.*)", r".loc[\1, '\2'] = \3", code)
    code = re.sub(r"\.loc\[(.*?)\]\s*\[\"(.*?)\"\]\s*=\s*(.*)", r".loc[\1, '\2'] = \3", code)
    
    # 3. Fix chain assignment df[cond]['col'] = val -> df.loc[cond, 'col'] = val
    # Match when there is a condition inside df[...]
    code = re.sub(r"df\[(df\[.*?\]\s*(?:==|!=|>=|<=|>|<|=)\s*.*?)\]\s*\['(.*?)'\]\s*=\s*(.*)", r"df.loc[\1, '\2'] = \3", code)
    code = re.sub(r"df\[(df\[.*?\]\s*(?:==|!=|>=|<=|>|<|=)\s*.*?)\]\s*\[\"(.*?)\"\]\s*=\s*(.*)", r"df.loc[\1, '\2'] = \3", code)
    
    # 4. Fix assignment chain e.g. result = df.loc[...] = val
    lines = code.split("\n")
    processed_lines = []
    for line in lines:
        if line.strip().startswith("result = df.loc") and line.count("=") >= 2:
            parts = line.split("=", 1)
            rhs = parts[1].strip()
            processed_lines.append(rhs)
        else:
            processed_lines.append(line)
    code = "\n".join(processed_lines)
    
    return code.strip()


def get_chat_history_str(conversation_id):
    if not conversation_id:
        return ""
    try:
        from database.crud import get_messages
        msgs = get_messages(conversation_id)
        history = []
        for m in msgs[-10:]:
            history.append(f"{m['role'].capitalize()}: {m['content']}")
        return "\n".join(history)
    except Exception as e:
        print(f"Error loading chat history: {str(e)}")
        return ""

def code_agent(state):
    llm = get_llm()
    conversation_id = state.get("conversation_id")
    history_str = get_chat_history_str(conversation_id)
    
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

    # Bypass LLM for simple non-mutation queries without aggregation or groupby
    is_mutation = any(m_task in task.lower() for m_task in ["update", "delete", "add", "drop", "fill", "convert", "insert", "replace", "clean", "modify"])
    if not is_mutation and not parsed.get("aggregation") and not parsed.get("groupby"):
        code = ""
        for col_name in state["schema"].get("date_columns", []):
            code += f"df['{col_name}'] = pd.to_datetime(df['{col_name}'], errors='coerce')\n"
            
        for f in parsed.get("filters", []):
            if not f.get("column"):
                continue
            col_name = f["column"]
            op = f.get("operator") or f.get("operation") or "=="
            val = f.get("value")
            if op == "=":
                op = "=="
            if col_name in state["schema"].get("date_columns", []):
                val = f"pd.to_datetime('{val}')"
            elif isinstance(val, str):
                val = f"'{val}'"
            code += f"df = df[df['{col_name}'] {op} {val}]\n"
            
        if parsed.get("sort_by"):
            order = parsed.get("order", "asc")
            ascending = (order == "asc")
            code += f"if '{parsed['sort_by']}' in df.columns:\n    df = df.sort_values(by='{parsed['sort_by']}', ascending={ascending})\n"
            
        if parsed.get("limit", 0) > 0:
            code += f"df = df.head({parsed['limit']})\n"
            
        code += "result = df"
        print(f"Bypassed LLM. Auto-generated simple code:\n{code}")
        return {
            "code": code
        }

    is_mutation = any(m_task in task.lower() for m_task in ["update", "delete", "add", "drop", "fill", "convert", "insert", "replace", "clean", "modify"])
    
    if is_mutation:
        prompt = f"""
        You are an expert Python data engineer.
        Generate Python code using the pandas library to modify the dataframe `df` based on the user's request.
        
        CONVERSATION HISTORY:
        {history_str}
        
        STRICT RULES:
        1. Output ONLY raw Python code. No markdown code blocks (no ```python), no comments, no explanations.
        2. The input dataframe is already loaded as `df`. Do NOT load any files or redefine `df` (do NOT write `df = pd.read_csv(...)`).
        3. Modify `df` in-place or assign the modified dataframe back to `df`.
        4. Store the final modified dataframe in the variable `result` (i.e. `result = df`).
        5. Columns in the dataset: {state["schema"]["columns"]}
        6. Dtypes in the dataset: {state["schema"]["dtypes"]}
        7. Sample data:
        {state["df"].head(3).to_dict()}
        
        STRICT MUTATION RULES (UPDATES/DELETIONS/CREATIONS):
        - DO NOT slice the dataframe columns (e.g., NEVER write `df = df[['price', 'revenue']]` or `df = df.loc[:, ['price', 'revenue']]`). Doing so deletes other columns and will break the application!
        - DO NOT filter out other rows of the main dataframe permanently unless you are deleting them. For updates, use `.loc[condition, column] = value` on the original `df`. Do NOT do `df = df.loc[condition]` and then update, as this deletes all other rows from the dataset!
        
        SYNTAX RULES:
        - ALWAYS parenthesize individual conditions when combining them with logical operators like `&` or `|`.
          Correct: df.loc[(df['date'] == '2024-01-01') & (df['product_name'] == 'Laptop'), 'price'] = 45000
          Incorrect: df.loc[df['date'] == '2024-01-01' & df['product_name'] == 'Laptop', 'price'] = 45000
        - ALWAYS use `.loc[row_condition, column_name] = value` to update values.
          Correct: df.loc[df['product_name'] == 'Laptop', 'price'] = 45000
          Incorrect: df.loc[df['product_name'] == 'Laptop', 'price'].values[0] = 45000
        - If you update a price or units column, make sure to also update the corresponding `revenue` column accordingly (revenue = price * units_sold).
          Example:
          mask = (df['date'] == '2024-01-01') & (df['product_name'] == 'Laptop')
          df.loc[mask, 'price'] = 45000
          df.loc[mask, 'revenue'] = df.loc[mask, 'price'] * df.loc[mask, 'units_sold']
          result = df
        
        User Query: {state['query']}
        Parsed Query Info: {parsed}
        """
    else:
        prompt = f"""
        Generate python pandas code to query, filter, aggregate, or modify (create, update, delete) the dataframe `df`.
        No explanation or comments needed.

        CONVERSATION HISTORY (Use this to resolve context for follow-up queries or data edits):
        {history_str}

        STRICT Rules:
        - Output ONLY raw Python code. No explanations, no markdown block, no comments, no text before or after the code.
        - Use `df` as input. Do not redefine or reload `df`.
        - NEVER call pd.read_csv() or try to load any CSV file (e.g., do NOT write `df = pd.read_csv('data.csv')`). The dataframe `df` is already available in the execution context.
        - Store the final output in the variable `result`.
        - For any data mutation (Create, Update, Delete), ALWAYS preserve all original columns of the dataframe. Do NOT slice the columns of the main dataframe (e.g. do NOT write `df = df[['col1', 'col2']]`) as this deletes other required columns and will cause errors.
        - If the user wants to add a row/record (Create): append it to `df` (e.g. using concat or loc) and set `result = df`.
          Example:
          df = pd.concat([df, pd.DataFrame([{{\"col1\": \"val1\", \"col2\": 300}}])], ignore_index=True)
          result = df
        - If the user wants to edit a value/column (Update): apply the operation to `df` and set `result = df`.
          STRICT UPDATE RULES:
          - ALWAYS use `.loc[row_condition, col_name] = new_value` directly to modify columns in-place.
            Example: df.loc[(df['date'] == '2024-01-01') & (df['product_name'] == 'Laptop'), 'price'] = 45000
          - NEVER assign values using `.values[0] = ...`, `.iloc[0] = ...` or `.loc[...].values[0] = ...` because this modifies a temporary copy and does not update the original dataframe!
          - If you update a price or units column, make sure to also update the corresponding `revenue` column accordingly (e.g., `df.loc[condition, 'revenue'] = df.loc[condition, 'price'] * df.loc[condition, 'units_sold']`).
          result = df
    - If the user wants to remove rows/columns (Delete): apply the deletion to `df` and set `result = df`.
      Example:
      df = df[df['col2'] >= 100]
      result = df
    - If the user wants to filter/query: apply filters and assign the filtered dataframe or aggregation to `result`.
    - The first character of your response must be valid Python.
    - The last character of your response must be valid Python.
    - Any non-Python text will cause execution failure.
    - Generate ONLY ONE valid solution.
    - Read the user query and schema carefully.
    - Store final output in variable `result`.
    - Only Python code.
    - No explanation.
    - No markdown.
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
    task = parsed.get("task", "").lower()
    is_mutation = any(m_task in task for m_task in ["update", "delete", "add", "drop", "fill", "convert", "insert", "replace", "clean", "modify"])
    
    if is_mutation:
        # Prepend date column conversions so that the mutation code can safely compare dates
        prepended = ""
        for col in state["schema"].get("date_columns", []):
            prepended += f"df['{col}'] = pd.to_datetime(df['{col}'], errors='coerce')\n"
        code = prepended + code
        
        # Ensure result = df is assigned
        if "result =" not in code:
            code += "\nresult = df"
            
        return {
            "code": code
        }
    
    # Prepend date conversions for non-mutation queries too
    prepended = ""
    for col in state["schema"].get("date_columns", []):
        prepended += f"df['{col}'] = pd.to_datetime(df['{col}'], errors='coerce')\n"
    code = prepended + code
    
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
        
    for f in parsed.get("filters", []):
        if not f.get("column"):
            continue
        col = f["column"]
        op = f.get("operator") or f.get("operation") or "=="
        val = f.get("value")
        if op == "=":
            op = "=="
            
        if col in state["schema"].get("date_columns", []):
            val = f"pd.to_datetime('{val}')"
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
        for col in state["schema"].get("date_columns", []):
            code += f"\ndf['{col}'] = pd.to_datetime(df['{col}'], errors='coerce')"

        for f in parsed["filters"]:
            if not f.get("column"):
                continue
            col = f["column"]
            op = f.get("operator") or f.get("operation") or "=="
            val = f.get("value")

            if op == "=":
                op = "=="

            if col in state["schema"].get("date_columns", []):
                val = f"pd.to_datetime('{val}')"
            elif isinstance(val, str):
                val = f"'{val}'"

            code += f"\ndf = df[df['{col}'] {op} {val}]"

        code += "\nresult = df"
    
    if not parsed.get("groupby") and "groupby" in code:
        return {
            "code": "",
            "error": "Invalid groupby generated"
        }
    return {
        "code": code
    }
    

