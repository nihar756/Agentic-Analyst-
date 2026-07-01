# create_tables.py

from database.db import engine
from database.models import Base

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

print("tables dropped and created")