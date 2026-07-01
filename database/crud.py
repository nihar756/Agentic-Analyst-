from database.db import SessionLocal
from database.models import Conversation, Dataset, Message, Chart, QueryHistory
import json

def create_conversation(title="New Chat", dataset_id=None, user_id=None):
    db = SessionLocal()
    conv = Conversation(title=title, dataset_id=dataset_id, user_id=user_id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    db.close()
    return conv.id

def get_conversations(user_id=None):
    db = SessionLocal()
    query = db.query(Conversation)
    if user_id is not None:
        query = query.filter(Conversation.user_id == user_id)
    conversations = query.order_by(Conversation.id.desc()).all()
    # Serialize to dicts
    result = []
    for c in conversations:
        result.append({
            "id": c.id,
            "title": c.title,
            "dataset_id": c.dataset_id,
            "filepath": c.filepath
        })
    db.close()
    return result

def get_messages(conversation_id):
    db = SessionLocal()
    messages = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()).all()
    result = []
    for m in messages:
        result.append({
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "chart_path": m.chart_path,
            "result": json.loads(m.result) if m.result else None
        })
    db.close()
    return result

def save_dataset(filename, filepath, user_id=None):
    db = SessionLocal()
    dataset = Dataset(filename=filename, filepath=filepath, user_id=user_id)
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    db.close()
    return dataset.id

def get_datasets(user_id=None):
    db = SessionLocal()
    query = db.query(Dataset)
    if user_id is not None:
        query = query.filter(Dataset.user_id == user_id)
    datasets = query.order_by(Dataset.uploaded_at.desc()).all()
    result = []
    for d in datasets:
        result.append({
            "id": d.id,
            "filename": d.filename,
            "filepath": d.filepath,
            "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None
        })
    db.close()
    return result

def get_dataset(dataset_id, user_id=None):
    db = SessionLocal()
    query = db.query(Dataset).filter(Dataset.id == dataset_id)
    if user_id is not None:
        query = query.filter(Dataset.user_id == user_id)
    dataset = query.first()
    result = None
    if dataset:
        result = {
            "id": dataset.id,
            "filename": dataset.filename,
            "filepath": dataset.filepath,
            "uploaded_at": dataset.uploaded_at.isoformat() if dataset.uploaded_at else None
        }
    db.close()
    return result

def delete_dataset(dataset_id, user_id=None):
    db = SessionLocal()
    # Get dataset details to delete file
    query = db.query(Dataset).filter(Dataset.id == dataset_id)
    if user_id is not None:
        query = query.filter(Dataset.user_id == user_id)
    dataset = query.first()
    filepath = None
    if dataset:
        filepath = dataset.filepath
        # Delete related conversations / messages / charts to avoid constraint issues
        conversations = db.query(Conversation).filter(Conversation.dataset_id == dataset_id).all()
        for conv in conversations:
            db.query(Message).filter(Message.conversation_id == conv.id).delete()
            db.query(Chart).filter(Chart.conversation_id == conv.id).delete()
            db.query(QueryHistory).filter(QueryHistory.conversation_id == conv.id).delete()
            db.delete(conv)
        db.delete(dataset)
        db.commit()
    db.close()
    return filepath

def update_dataset_name(dataset_id, new_filename, user_id=None):
    db = SessionLocal()
    query = db.query(Dataset).filter(Dataset.id == dataset_id)
    if user_id is not None:
        query = query.filter(Dataset.user_id == user_id)
    dataset = query.first()
    if dataset:
        dataset.filename = new_filename
        db.commit()
    db.close()

def delete_conversation(conversation_id, user_id=None):
    import os
    db = SessionLocal()
    query = db.query(Conversation).filter(Conversation.id == conversation_id)
    if user_id is not None:
        query = query.filter(Conversation.user_id == user_id)
    conv = query.first()
    if conv:
        # Delete local copy of the dataset if it exists
        if conv.filepath and os.path.exists(conv.filepath):
            try:
                os.remove(conv.filepath)
            except Exception as e:
                print(f"Error removing conversation file {conv.filepath}: {str(e)}")
        
        # Delete chart files associated with the conversation
        charts = db.query(Chart).filter(Chart.conversation_id == conversation_id).all()
        for chart in charts:
            if chart.chart_path and os.path.exists(chart.chart_path):
                try:
                    os.remove(chart.chart_path)
                except Exception as e:
                    print(f"Error removing chart file {chart.chart_path}: {str(e)}")
        
        # Delete related DB records
        db.query(Message).filter(Message.conversation_id == conversation_id).delete()
        db.query(Chart).filter(Chart.conversation_id == conversation_id).delete()
        db.query(QueryHistory).filter(QueryHistory.conversation_id == conversation_id).delete()
        
        db.delete(conv)
        db.commit()
        db.close()
        return True
    db.close()
    return False

def save_message(conversation_id, role, content, chart_path=None, result=None):
    db = SessionLocal()
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        chart_path=chart_path,
        result=result
    )
    db.add(message)
    db.commit()
    db.close()

def save_chart(conversation_id, path):
    db = SessionLocal()
    chart = Chart(conversation_id=conversation_id, chart_path=path)
    db.add(chart)
    db.commit()
    db.close()

def save_query_history(query, parsed_query, generated_code):
    db = SessionLocal()
    q = QueryHistory(
        query=query,
        parsed_query=json.dumps(parsed_query),
        generated_code=generated_code
    )
    db.add(q)
    db.commit()
    db.close()

def link_dataset_to_conversation(conversation_id, dataset_id):
    import shutil
    import os
    db = SessionLocal()
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conv:
        conv.dataset_id = dataset_id
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if dataset:
            src_filepath = dataset.filepath
            filename = os.path.basename(src_filepath)
            dest_filename = f"conv_{conversation_id}_{filename}"
            dest_filepath = os.path.join("public", dest_filename).replace('\\', '/')
            
            try:
                shutil.copy2(src_filepath, dest_filepath)
                conv.filepath = dest_filepath
            except Exception as e:
                print(f"Error copying dataset for conversation: {str(e)}")
                
            if conv.title == "New Analysis" or conv.title == "New Chat" or conv.title.startswith("Chat on"):
                base_title = f"Chat on {dataset.filename}"
                existing_count = db.query(Conversation).filter(
                    Conversation.user_id == conv.user_id,
                    Conversation.dataset_id == dataset_id,
                    Conversation.id != conversation_id
                ).count()
                
                if existing_count > 0:
                    conv.title = f"{base_title} ({existing_count + 1})"
                else:
                    conv.title = base_title
        db.commit()
    db.close()