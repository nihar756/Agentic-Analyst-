import pandas as pd
import json
import os
import re
import sys
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def execution_agent(state):
    df = state["df"]
    code = state["code"]

    if not code:
        return {
            "result": None,
            "error": state.get("error", "No code generated"),
            "df": df
        }

    local_vars = {"df": df, "pd": pd}

    try:
        exec(code, {}, local_vars)
        result = local_vars.get("result", None)
        updated_df = local_vars.get("df", df)
        print(f"Execution result: {result}")
        
        # Check if this is a mutation operation
        parsed = state.get("parsed_query", {})
        query = state.get("query", "").lower()
        mutation_keywords = ["add", "update", "delete", "remove", "fill", "drop", "change", "replace", "insert", "clean", "modify"]
        is_mutation = False
        
        if parsed and isinstance(parsed, dict):
            task = parsed.get("task", "")
            if task in ["drop_nulls", "fill_nulls_mean", "fill_nulls_value", "drop_duplicates", "convert_type", "add_row", "delete_row", "update_cell", "drop_column"]:
                is_mutation = True
                
        if any(kw in query for kw in mutation_keywords):
            is_mutation = True

        if is_mutation and isinstance(result, pd.DataFrame):
            updated_df = result

        if isinstance(result, pd.DataFrame):
            state["df"] = result
            
        return {
            "result": result,
            "error": None,
            "df": updated_df
        }

    except Exception as e:
        print(f"Execution error: {str(e)}")
        return {
            "result": None,
            "error": str(e),
            "df": df
        }