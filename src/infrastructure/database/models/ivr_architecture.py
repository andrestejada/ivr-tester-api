"""IVR Architecture model — an IVR system owned by a user."""

import uuid
from datetime import datetime

from sqlalchemy import TEXT, VARCHAR, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.base import Base


class IVRArchitectureModel(Base):
    """An IVR system owned by a user.

    Groups test cases that target the same phone system, enabling
    per-architecture metrics (e.g. success rate of 'Sales IVR').
    """

    __tablename__ = "ivr_architectures"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    phone_number: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    description: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    owner: Mapped["ProfileModel"] = relationship(  # noqa: F821
        back_populates="ivr_architectures"
    )
    test_cases: Mapped[list["TestCaseModel"]] = relationship(  # noqa: F821
        back_populates="ivr_architecture", cascade="all, delete-orphan"
    )
