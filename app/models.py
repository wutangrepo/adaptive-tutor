from sqlalchemy import Column, Integer, String, Text, JSON, DateTime
from datetime import datetime, timezone
from .db import Base

class Item(Base):
    __tablename__ = "items"
    id = Column(String, primary_key=True)
    source = Column(String)
    type = Column(String)
    grading_mode = Column(String)
    concepts = Column(JSON)
    difficulty = Column(Integer, default=1)
    stem = Column(Text)
    payload = Column(JSON)

class Attempt(Base):
    __tablename__ = "attempts"
    id = Column(Integer, primary_key=True)
    learner_id = Column(String, index=True)
    item_id = Column(String)
    correct = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))