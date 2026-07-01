import pandas as pd
import json
import os
import re
import sys
import matplotlib
matplotlib.use('Agg') # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from utils.llm import get_llm
from agents.code_agent import clean_code

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
        sample_dict = df_to_plot.head(5).to_dict()
    else:
        cols_description = f"Series index: {list(df_to_plot.index)}"
        sample_dict = df_to_plot.head(5).to_dict()
    
    # Generate prompt to write the plotting code
    prompt = f"""
    Generate Python code using matplotlib and seaborn to create a beautiful chart.
    
    The user query is: "{state['query']}"
    The parsed query visualization config is: {json.dumps(vis_details)}
    
    Data info to plot (stored in variable `df_to_plot`):
    - {cols_description}
    - Sample/Head of data:
    {sample_dict}
    
    STRICT RULES:
    1. Generate ONLY executable Python code. No markdown (like ```python or ```), no explanations.
    2. The input dataframe is ALREADY loaded and available as the variable `df_to_plot` in the execution context.
       - CRITICAL: DO NOT redefine `df_to_plot` (e.g., NEVER write `df_to_plot = pd.DataFrame(...)` or `df_to_plot = pd.read_csv(...)`).
       - CRITICAL: DO NOT copy or paste any sample data from this prompt into your python code.
       - Directly plot using the existing `df_to_plot` variable.
    3. DO NOT use ellipsis (`...`) or placeholders. All code must be complete and valid Python.
    4. DO NOT call `plt.savefig(...)` or `plt.show()`. The platform handles rendering automatically.
    5. Clean any existing plots before starting with `plt.close('all')`.
    6. Design styling rules to make it look premium:
       - Use a professional style/theme (e.g. `sns.set_theme(style="whitegrid")`).
       - CRITICAL: Do not blindly use `config['x']` and `config['y']`. You MUST map them to the exact column names present in the `df_to_plot` Columns list (e.g., if config says 'total_revenue' but column is 'revenue', use 'revenue').
       - If using `df_to_plot.plot(kind=...)`, ensure the kind is valid (e.g., 'bar' instead of 'bar chart'). Alternatively, use seaborn directly (e.g. `sns.barplot(data=df_to_plot, x='actual_x_col', y='actual_y_col')`).
       - Use a curated color palette (like "muted", "viridis", "coolwarm", or professional colors).
       - Rotate x-axis labels if they are categorical or dates and might overlap (e.g., `plt.xticks(rotation=45)`).
       - Add clear title, xlabel, and ylabel.
       - Use `plt.tight_layout()`.
    7. Only output the Python code. Stop after writing it.
    """
    
    try:
        response = llm.invoke(prompt)
        code = clean_code(response.content)
        print(f"Generated visualization code:\n{code}")
        
        # Execute the generated code
        local_vars = {
            "df_to_plot": df_to_plot,
            "plt": plt,
            "sns": sns,
            "pd": pd
        }
        exec(code, {}, local_vars)
        
        # Capture the current figure from plt to a BytesIO stream
        import io
        import base64
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=300)
        buf.seek(0)
        base64_data = base64.b64encode(buf.read()).decode('utf-8')
        plt.close('all')
        
        chart_path = f"data:image/png;base64,{base64_data}"
        print("Chart successfully generated in memory as Base64.")
        return {
            "chart_path": chart_path
        }
            
    except Exception as e:
        print(f"Error in visualization agent: {str(e)}")
        return {
            "error": f"Failed to generate visualization: {str(e)}"
        }
