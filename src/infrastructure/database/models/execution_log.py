"""Execution Log model — step-by-step forensic log of a test execution."""

import uuid
from datetime import datetime

from sqlalchemy import DECIMAL, TEXT, VARCHAR, DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.base import Base


class ExecutionLogModel(Base):
    """Step-by-step forensic log for a single test execution.

    Stores what was expected vs. what Deepgram actually transcribed at
    each step, allowing precise post-mortem analysis of failures.
    """

    __tablename__ = "execution_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_text: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    actual_transcription: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(
        DECIMAL(5, 2),
        nullable=True,
        comment="Similarity/confidence percentage from Deepgram (0.00 – 100.00)",
    )
    action_taken: Mapped[str | None] = mapped_column(
        VARCHAR(255),
        nullable=True,
        comment='e.g. "Sent DTMF: 2" or "Call terminated"',
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    execution: Mapped["TestExecutionModel"] = relationship(  # noqa: F821
        back_populates="logs"
    )
