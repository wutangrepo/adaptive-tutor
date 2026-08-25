from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from .db import Base


class Item(Base):
    __tablename__ = "items"
    id = Column(String, primary_key=True)
    source = Column(String, nullable=False)
    type = Column(String, nullable=False)  # logic_eval | tautology_check | equivalence_check | mcq
    grading_mode = Column(String, nullable=False, default="deterministic")
    concepts = Column(JSON, nullable=False)
    difficulty = Column(Integer, nullable=False, default=1)
    stem = Column(Text, nullable=False)
    payload = Column(JSON, nullable=False)

    __table_args__ = (CheckConstraint("difficulty IN (1,2,3)", name="ck_item_difficulty"),)

    hint_drafts = relationship("HintDraft", back_populates="item", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Item {self.id} [{self.type}]>"


class Attempt(Base):
    __tablename__ = "attempts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    learner_id = Column(String, index=True, nullable=False)
    item_id = Column(String, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    correct = Column(Integer, nullable=False)  # 0/1
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("correct IN (0,1)", name="ck_attempt_correct"),
        Index("ix_attempt_learner_item", "learner_id", "item_id"),
    )

    def __repr__(self):
        return f"<Attempt {self.learner_id}:{self.item_id}={self.correct}>"


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    actor = Column(String, nullable=False)  # ollama:* | professor | system
    action = Column(String, nullable=False)  # hint_drafted | hint_approved | ...
    target = Column(String, nullable=False)
    detail = Column(JSON)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (Index("ix_audit_created", "created_at"),)


class HintDraft(Base):
    __tablename__ = "hint_drafts"
    __table_args__ = (CheckConstraint("status IN ('draft','approved','rejected')", name="ck_hint_draft_status"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(String, ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="draft")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    item = relationship("Item", back_populates="hint_drafts")

    def __repr__(self):
        return f"<Hint {self.id} {self.status} for {self.item_id}>"
