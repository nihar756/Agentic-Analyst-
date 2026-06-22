from database.crud import save_message

def save_assistant_agent(state):

    save_message(
        conversation_id=state["conversation_id"],
        role="assistant",
        content=state["insights"]
    )

    return {}