from sqlalchemy.orm import declarative_base
from sqlalchemy import *
from sqlalchemy.sql import func

Base = declarative_base()
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    name = Column(String)

    email = Column(String, unique=True)
    
class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True)

    filename = Column(String)

    filepath = Column(String)

    uploaded_at = Column(DateTime, default=func.now())
    
class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)

    title = Column(String)

    dataset_id = Column(
        Integer,
        ForeignKey("datasets.id")
    )
    
class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)

    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id")
    )

    role = Column(String)
    created_at = Column(DateTime, default=func.now())
    content = Column(Text)
    
class Chart(Base):
    __tablename__ = "charts"

    id = Column(Integer, primary_key=True)

    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id")
    )
    query = Column(Text)
    chart_path = Column(String)
    created_at = Column(DateTime, default=func.now())
    
class QueryHistory(Base):
    __tablename__ = "query_history"

    id = Column(Integer, primary_key=True)

    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id")
    )

    query = Column(Text)

    parsed_query = Column(Text)

    generated_code = Column(Text)
    created_at = Column(DateTime, default=func.now())