"""Test Case model — a test script (flow) for a specific IVR architecture."""

import uuid
from datetime import datetime

from sqlalchemy import VARCHAR, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.base import Base


class TestCaseModel(Base):
    """A test script (flow) for a specific IVR architecture.

    The flow_script JSONB column stores the ordered list of steps the
    test engine must execute during the call, for example:
        [{"step": 1, "listen": "Bienvenido", "action": "send_dtmf_1"}]
    """

    __tablename__ = "test_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ivr_architecture_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ivr_architectures.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    flow_script: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment='Array of steps, e.g. [{"step":1,"listen":"Bienvenido","action":"send_dtmf_1"}]',
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    ivr_architecture: Mapped["IVRArchitectureModel"] = relationship(  # noqa: F821
        back_populates="test_cases"
    )
    executions: Mapped[list["TestExecutionModel"]] = relationship(  # noqa: F821
        back_populates="test_case", cascade="all, delete-orphan"
    )
