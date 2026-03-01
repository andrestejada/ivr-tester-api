"""Test Execution model — a single run of a test case."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.base import Base


class TestStatus(str, enum.Enum):
    """Possible outcomes of a test execution.

    Maps to the PostgreSQL ENUM type 'test_status' created in the migration.
    """

    PASSED = "PASSED"
    FAILED = "FAILED"
    ERROR = "ERROR"


class TestExecutionModel(Base):
    """A single run of a test case.

    Stores the outcome (PASSED / FAILED / ERROR) and call metadata.
    This is the primary table for dashboard metrics and trend analysis.
    """

    __tablename__ = "test_executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    test_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[TestStatus] = mapped_column(
        Enum(TestStatus, name="test_status", create_type=False),
        nullable=False,
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    twilio_call_sid: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Twilio CallSid for cross-referencing in Twilio Console",
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    test_case: Mapped["TestCaseModel"] = relationship(  # noqa: F821
        back_populates="executions"
    )
    logs: Mapped[list["ExecutionLogModel"]] = relationship(  # noqa: F821
        back_populates="execution", cascade="all, delete-orphan"
    )
