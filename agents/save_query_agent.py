from database.crud import save_query_history

def save_query_agent(state):

    save_query_history(
        query=state["query"],
        parsed_query=state["parsed_query"],
        generated_code=state["code"]
    )

    return {}