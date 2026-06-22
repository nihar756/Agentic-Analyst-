from database.crud import save_message

def save_user_message_agent(state):

    save_message(
        conversation_id=state["conversation_id"],
        role="user",
        content=state["query"]
    )

    return {}