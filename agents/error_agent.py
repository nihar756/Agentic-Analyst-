def error_agent(state):
    return {
        "insights": f"Error occurred: {state['error']}"
    }