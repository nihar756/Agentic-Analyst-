import pandas as pd
import json
import os
import re

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


# ================= AGENTS =================

# 1. Schema Agent
def schema_agent(state):
    file_path = state["file_path"]
    
    from utils.s3_helper import get_s3_client, read_dataframe_from_s3
    
    s3_client = get_s3_client()
    # If R2 client is initialized and it's not a local public/ path
    if s3_client and not file_path.startswith("public/"):
        try:
            print(f"Loading dataframe from Cloudflare R2: {file_path}")
            df = read_dataframe_from_s3(file_path)
        except Exception as e:
            print(f"Error loading from R2, trying local fallback: {str(e)}")
            df = pd.read_csv(file_path)
    else:
        df = pd.read_csv(file_path)

    schema = {
    "columns": list(df.columns),
    "dtypes": df.dtypes.astype(str).to_dict(),
    "sample": df.head(3).to_dict(),

    # ✅ NEW ADDITIONS
    "date_columns": [
        col for col in df.columns
        if "date" in col.lower() or "time" in col.lower()
    ],
    "shape": {
        "rows": df.shape[0],
        "columns": df.shape[1]
        },
    "missing_values": df.isnull().sum().to_dict(),
    "unique_values": df.nunique().to_dict(),
    "column_types": {
        "numerical": list(df.select_dtypes(include=['int64', 'float64']).columns),
        "categorical": list(df.select_dtypes(include=['object']).columns)
        }
    }
    print(f"Schema extracted: {schema}")
    print(f"DataFrame head:\n{df.head()}")
    return {
        "df": df,
        "schema": schema
    }