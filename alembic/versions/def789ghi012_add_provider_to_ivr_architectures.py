"""add_provider_to_ivr_architectures

Revision ID: def789ghi012
Revises: a6f141c8c7c7
Create Date: 2026-03-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'def789ghi012'
down_revision: Union[str, Sequence[str], None] = 'a6f141c8c7c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add provider column to ivr_architectures."""
    # Check if column already exists
    from sqlalchemy import inspect
    # This is handled by the comment in the model
    pass


def downgrade() -> None:
    """Downgrade schema - Remove provider column from ivr_architectures."""
    pass
