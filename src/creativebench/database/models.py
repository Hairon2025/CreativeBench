"""Relational models for imported Prompts and duplicate relations."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from creativebench.database.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class PromptStatus(StrEnum):
    READY_FOR_LABELING = "ready_for_labeling"
    DUPLICATE = "duplicate"
    PENDING_REVIEW = "pending_review"
    LABELED = "labeled"


class ClassificationDecision(StrEnum):
    AUTO_ACCEPTED = "auto_accepted"
    REVIEW_PENDING = "review_pending"
    HUMAN_APPROVED = "human_approved"
    HUMAN_CORRECTED = "human_corrected"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


class PromptORM(Base):
    __tablename__ = "prompts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_reference: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=PromptStatus.READY_FOR_LABELING.value,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    ingestion: Mapped["PromptIngestionORM"] = relationship(
        back_populates="prompt",
        cascade="all, delete-orphan",
        uselist=False,
    )
    duplicate_match: Mapped["DuplicateMatchORM | None"] = relationship(
        back_populates="duplicate_prompt",
        cascade="all, delete-orphan",
        foreign_keys="DuplicateMatchORM.duplicate_prompt_id",
        uselist=False,
    )
    represented_duplicates: Mapped[list["DuplicateMatchORM"]] = relationship(
        back_populates="representative_prompt",
        foreign_keys="DuplicateMatchORM.representative_prompt_id",
    )
    classification_runs: Mapped[list["ClassificationRunORM"]] = relationship(
        back_populates="prompt",
        cascade="all, delete-orphan",
    )


class PromptIngestionORM(Base):
    __tablename__ = "prompt_ingestions"
    __table_args__ = (
        CheckConstraint("original_length >= 0", name="ck_ingestion_original_length"),
        CheckConstraint("cleaned_length >= 0", name="ck_ingestion_cleaned_length"),
    )

    prompt_id: Mapped[str] = mapped_column(
        ForeignKey("prompts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    original_length: Mapped[int] = mapped_column(Integer, nullable=False)
    cleaned_length: Mapped[int] = mapped_column(Integer, nullable=False)
    cleaning_operations: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    prompt: Mapped[PromptORM] = relationship(back_populates="ingestion")


class DuplicateMatchORM(Base):
    __tablename__ = "duplicate_matches"
    __table_args__ = (
        UniqueConstraint("duplicate_prompt_id", name="uq_duplicate_prompt"),
        CheckConstraint(
            "duplicate_prompt_id <> representative_prompt_id",
            name="ck_duplicate_not_self",
        ),
        CheckConstraint("score >= 0 AND score <= 1", name="ck_duplicate_score"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    duplicate_prompt_id: Mapped[str] = mapped_column(
        ForeignKey("prompts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    representative_prompt_id: Mapped[str] = mapped_column(
        ForeignKey("prompts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    method: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    duplicate_prompt: Mapped[PromptORM] = relationship(
        back_populates="duplicate_match",
        foreign_keys=[duplicate_prompt_id],
    )
    representative_prompt: Mapped[PromptORM] = relationship(
        back_populates="represented_duplicates",
        foreign_keys=[representative_prompt_id],
    )


class ClassificationRunORM(Base):
    """Immutable model prediction plus its current review decision."""

    __tablename__ = "classification_runs"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_run_confidence"),
        CheckConstraint(
            "review_threshold >= 0 AND review_threshold <= 1",
            name="ck_run_review_threshold",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_id: Mapped[str] = mapped_column(
        ForeignKey("prompts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    review_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    prediction: Mapped[dict] = mapped_column(JSON, nullable=False)
    retrieved_document_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    decision: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    prompt: Mapped[PromptORM] = relationship(back_populates="classification_runs")
    review_task: Mapped["ReviewTaskORM | None"] = relationship(
        back_populates="classification_run",
        cascade="all, delete-orphan",
        uselist=False,
    )


class ReviewTaskORM(Base):
    """One human-review task; final_prediction preserves any correction."""

    __tablename__ = "review_tasks"
    __table_args__ = (
        UniqueConstraint("classification_run_id", name="uq_review_classification_run"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    classification_run_id: Mapped[int] = mapped_column(
        ForeignKey("classification_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=ReviewStatus.PENDING.value,
        index=True,
    )
    reviewer: Mapped[str | None] = mapped_column(String(128))
    notes: Mapped[str | None] = mapped_column(Text)
    final_prediction: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    classification_run: Mapped[ClassificationRunORM] = relationship(
        back_populates="review_task"
    )
