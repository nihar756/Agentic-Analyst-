import json
import datetime
import numpy as np
import pandas as pd
from database.crud import save_message

def make_json_serializable_scalar(val):
    if val is None:
        return None
    if isinstance(val, float):
        if np.isnan(val) or np.isinf(val):
            return None
    if isinstance(val, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(val)
    if isinstance(val, (np.floating, np.float64, np.float32, np.float16)):
        return float(val)
    if isinstance(val, np.bool_):
        return bool(val)
    if isinstance(val, (pd.Timestamp, datetime.date, datetime.datetime)):
        return val.isoformat()
    return val

def make_json_serializable(val):
    if val is None:
        return {
            "type": "scalar",
            "data": "None"
        }
    if isinstance(val, pd.DataFrame):
        return {
            "type": "dataframe",
            "columns": [str(c) for c in val.columns],
            "data": [[make_json_serializable_scalar(cell) for cell in row] for row in val.head(50).values.tolist()],
            "total_rows": len(val)
        }
    elif isinstance(val, pd.Series):
        return {
            "type": "series",
            "index": [str(idx) for idx in val.index],
            "data": [make_json_serializable_scalar(item) for item in val.values.tolist()]
        }
    else:
        return {
            "type": "scalar",
            "data": str(make_json_serializable_scalar(val))
        }

def save_assistant_agent(state):
    # Serialize result
    result_val = make_json_serializable(state.get("result"))
    result_json = json.dumps(result_val) if result_val else None

    save_message(
        conversation_id=state["conversation_id"],
        role="assistant",
        content=state["insights"],
        chart_path=state.get("chart_path"),
        result=result_json
    )

    return {}