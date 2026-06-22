from database.db import SessionLocal
from database.models import Conversation
from database.models import Dataset
from database.models import Message
from database.models import Chart
from database.models import QueryHistory
import json

def create_conversation(title="New Chat"):
    db = SessionLocal()

    conv = Conversation(title=title)

    db.add(conv)
    db.commit()
    db.refresh(conv)

    db.close()

    return conv.id

def save_dataset(filename, filepath):
    db = SessionLocal()

    dataset = Dataset(
        filename=filename,
        filepath=filepath
    )

    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    db.close()

    return dataset.id


def save_message(conversation_id, role, content):
    db = SessionLocal()

    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content
    )

    db.add(message)
    db.commit()

    db.close()
    
# from database.models import Chart

def save_chart(conversation_id, path):
    db = SessionLocal()

    chart = Chart(
        conversation_id=conversation_id,
        chart_path=path
    )

    db.add(chart)
    db.commit()

    db.close()
    


def save_query_history(
        query,
        parsed_query,
        generated_code
):
    db = SessionLocal()

    q = QueryHistory(
        query=query,
        parsed_query=json.dumps(parsed_query),
        generated_code=generated_code
    )

    db.add(q)
    db.commit()

    db.close()
    

def create_conversation(title="New Chat"):
    db = SessionLocal()

    conv = Conversation(
        title=title
    )

    db.add(conv)
    db.commit()
    db.refresh(conv)

    db.close()

    return conv.id