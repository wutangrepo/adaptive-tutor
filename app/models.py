from sqlalchemy import Column, Integer, String, Text, JSON
from .db import Base

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    source = Column(String)
    type = (Column)(String)
    grading_mode = Column(String)
    concepts = Column(JSON)
    difficulty = Column(Integer, default=1)
    stem = Column(Text)
    payload = Column(JSON)