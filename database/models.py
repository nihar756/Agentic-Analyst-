from sqlalchemy.orm import declarative_base
from sqlalchemy import *
from sqlalchemy.sql import func

Base = declarative_base()
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String, unique=True)
    password_hash = Column(String)
    salt = Column(String)
    
class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True)
    token = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime)
    
class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True)
    filename = Column(String)
    filepath = Column(String)
    uploaded_at = Column(DateTime, default=func.now())
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    title = Column(String)
    dataset_id = Column(
        Integer,
        ForeignKey("datasets.id")
    )
    filepath = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
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
    chart_path = Column(String, nullable=True)
    result = Column(Text, nullable=True)
    
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