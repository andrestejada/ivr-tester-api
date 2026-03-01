"""Profile model — extended user data linked to Supabase auth.users."""

import uuid
from datetime import datetime

from sqlalchemy import VARCHAR, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.base import Base


class ProfileModel(Base):
    """Extended user profile linked to Supabase auth.users.

    The primary key matches auth.users.id so that a single JOIN is enough
    to relate any application record back to the authenticated user.
    The row is created automatically by the handle_new_user DB trigger.
    """

    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        comment="Matches auth.users.id — set by the handle_new_user trigger",
    )
    email: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(VARCHAR(255), nullable=True)
    company_name: Mapped[str | None] = mapped_column(VARCHAR(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    ivr_architectures: Mapped[list["IVRArchitectureModel"]] = relationship(  # noqa: F821
        back_populates="owner", cascade="all, delete-orphan"
    )
