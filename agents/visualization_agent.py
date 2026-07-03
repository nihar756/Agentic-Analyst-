import pandas as pd
import json
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from utils.llm import get_llm

def visualization_agent(state):
    query = state.get("query", "").lower()
    parsed = state.get("parsed_query", {})
    
    # Check if visualization is requested either in parsed query or keywords in original query
    vis_requested = False
    vis_details = {}
    
    if parsed and isinstance(parsed, dict) and parsed.get("visualization"):
        vis_details = parsed["visualization"]
        if isinstance(vis_details, dict) and vis_details.get("type"):
            vis_requested = True
            
    vis_keywords = ["plot", "chart", "graph", "visualize", "bar", "line", "hist", "scatter", "pie", "heatmap"]
    if any(k in query for k in vis_keywords):
        vis_requested = True

    if not vis_requested:
        print("No visualization requested.")
        return {}

    # Determine which DataFrame/Series to plot
    df_to_plot = state.get("result")
    if not isinstance(df_to_plot, (pd.DataFrame, pd.Series)) or (isinstance(df_to_plot, pd.DataFrame) and df_to_plot.empty):
        df_to_plot = state.get("df")

    if df_to_plot is None or (isinstance(df_to_plot, pd.DataFrame) and df_to_plot.empty):
        print("No data available to plot.")
        return {"error": "No data available to plot."}

    llm = get_llm()
    
    # Ensure columns list/index is extracted cleanly
    cols_description = ""
    if isinstance(df_to_plot, pd.DataFrame):
        cols_description = f"Columns: {list(df_to_plot.columns)}"
        sample_dict = df_to_plot.head(5).to_dict(orient="records")
    else:
        cols_description = f"Series index: {list(df_to_plot.index)}"
        sample_dict = df_to_plot.head(5).to_dict()
    
    prompt = f"""
    You are a data visualization assistant. Determine the best chart configuration for this dataset based on the user's query.
    
    User Query: "{state['query']}"
    Parsed Config: {json.dumps(vis_details)}
    
    Data info to plot (stored in variable `df_to_plot`):
    - {cols_description}
    - Sample/Head of data:
    {sample_dict}
    
    Choose:
    1. Chart Type: "bar", "line", "pie", "doughnut", "radar", "polarArea" (standard Chart.js types).
    2. X-axis Column: Must be a column name from the list above.
    3. Y-axis Column: Must be a column name from the list above.
    4. Chart Title: A concise, descriptive title.
    
    Output ONLY a JSON block like this:
    {{
      "type": "bar",
      "x": "column_name",
      "y": "column_name",
      "title": "Chart Title"
    }}
    Do not output any markdown or explanation.
    """
    
    try:
        response = llm.invoke(prompt)
        content = response.content.strip()
        
        # Clean any markdown packaging (e.g. ```json ... ```)
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()
            
        config = json.loads(content)
        
        # Convert df_to_plot to DataFrame if it's a Series
        if isinstance(df_to_plot, pd.Series):
            name = df_to_plot.name or 'value'
            df = df_to_plot.reset_index()
            df.columns = ['index', name]
            x_col = 'index'
            y_col = name
        else:
            df = df_to_plot
            x_col = config.get("x")
            y_col = config.get("y")
            
        # Fallback/validation: make sure x_col and y_col exist in df
        if x_col not in df.columns:
            x_col = df.columns[0]
        if y_col not in df.columns:
            y_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
            
        # Extract data rows limit to head(50) for performance
        data_records = df[[x_col, y_col]].head(50).to_dict(orient="records")
        
        # Convert data types for JSON compatibility
        import numpy as np
        import datetime
        def clean_val(v):
            if v is None:
                return None
            if isinstance(v, float):
                if np.isnan(v) or np.isinf(v):
                    return None
            if isinstance(v, (np.integer, np.int64, np.int32, np.int16, np.int8)):
                return int(v)
            if isinstance(v, (np.floating, np.float64, np.float32, np.float16)):
                return float(v)
            if isinstance(v, np.bool_):
                return bool(v)
            if isinstance(v, (datetime.date, datetime.datetime)):
                return v.isoformat()
            return v

        cleaned_records = []
        for row in data_records:
            cleaned_row = {}
            for k, val in row.items():
                cleaned_row[k] = clean_val(val)
            cleaned_records.append(cleaned_row)

        # Build specification
        chart_spec = {
            "type": config.get("type", "bar"),
            "x": x_col,
            "y": y_col,
            "title": config.get("title", "Data Visualization"),
            "data": cleaned_records
        }
        
        chart_path = json.dumps(chart_spec)
        print("Chart specification successfully generated.")
        return {
            "chart_path": chart_path
        }
            
    except Exception as e:
        print(f"Error in visualization agent: {str(e)}")
        return {
            "error": f"Failed to generate visualization: {str(e)}"
        }
