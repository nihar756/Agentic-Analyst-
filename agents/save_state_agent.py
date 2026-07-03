import pandas as pd
import os

def save_state_agent(state):
    df = state.get("df")
    file_path = state.get("file_path")
    parsed = state.get("parsed_query", {})
    query = state.get("query", "").lower()
    
    # We save the state if df exists, file_path exists, and it's a mutation operation.
    # Tasks related to mutation: drop_nulls, fill_nulls_mean, fill_nulls_value, drop_duplicates, convert_type
    # Or query keywords like: add, update, delete, remove, fill, drop, change, replace
    mutation_keywords = ["add", "update", "delete", "remove", "fill", "drop", "change", "replace", "insert", "clean", "modify"]
    is_mutation = False
    
    if parsed and isinstance(parsed, dict):
        task = parsed.get("task", "")
        if task in ["drop_nulls", "fill_nulls_mean", "fill_nulls_value", "drop_duplicates", "convert_type", "add_row", "delete_row", "update_cell", "drop_column"]:
            is_mutation = True
            
    if any(kw in query for kw in mutation_keywords):
        is_mutation = True
        
    if is_mutation and df is not None and file_path:
        try:
            from utils.s3_helper import get_s3_client, save_dataframe_to_s3
            s3_client = get_s3_client()
            
            if s3_client and not file_path.startswith("public/"):
                print(f"Data state changed. Saving state to Cloudflare R2: {file_path}...")
                save_dataframe_to_s3(df, file_path)
                print("Successfully saved state to Cloudflare R2.")
            else:
                # Save locally if R2 not configured or it's a local public/ path
                if os.path.exists(file_path) or file_path.startswith("public/"):
                    print(f"Data state changed. Saving state to local file: {file_path}")
                    df.to_csv(file_path, index=False)
                    print("Successfully saved state to local disk.")
                else:
                    print(f"Warning: File path {file_path} does not exist locally and R2 is not configured.")
        except Exception as e:
            print(f"Error saving data state: {str(e)}")
            return {"error": f"Failed to save modified dataset state: {str(e)}"}
            
    return {}
