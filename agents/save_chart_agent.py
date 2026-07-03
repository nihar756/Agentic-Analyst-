from database.crud import save_chart

def save_chart_agent(state):

    if state.get("chart_path"):

        save_chart(
            state["conversation_id"],
            state["chart_path"]
        )

    return {}