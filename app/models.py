from sqlalchemy import Column, Integer, String, Text, Float, JSON, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
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

    assessments = relationship("Assessment", back_populates="item")
    hint_drafts = relationship("HintDraft", back_populates="item")

class Attempt(Base):
    __tablename__ = "attempts"
    id = Column(Integer, primary_key=True)
    learner_id = Column(String, index=True, nullable=False)
    item_id = Column(String, ForeignKey("items.id"), nullable=False)
    correct = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (
        CheckConstraint("status IN ('pending','needs_human','approved','overridden')",
                        name="ck_assessment_status"),
    )
    id = Column(Integer, primary_key=True)
    item_id = Column(String, ForeignKey("items.id"), nullable=False)
    learner_id = Column(String, index=True, nullable=False)
    answer = Column(Text)
    status = Column(String, default="pending", nullable=False)
    ai_breakdown = Column(JSON)
    ai_total = Column(Integer)
    ai_max = Column(Integer)
    ai_confidence = Column(Float)
    final_total = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    item = relationship("Item", back_populates="assessments")

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    actor = Column(String, nullable=False)  # "ollama:llama3.2:3b" | "professor" | "system"
    action = Column(String, nullable=False)       # grade_drafted | approved | overridden | hint_approved ...
    target = Column(String, nullable=False)
    detail = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class HintDraft(Base):
    __tablename__ = "hint_drafts"
    __table_args__ = (
        CheckConstraint("status IN ('draft','approved','rejected')",
                        name="ck_hint_draft_status"),
    )
    id = Column(Integer, primary_key=True)
    item_id = Column(String, ForeignKey("items.id"), nullable=False)
    text = Column(Text)
    status = Column(String, default="draft", nullable=False)

    item = relationship("Item", back_populates="hint_drafts")