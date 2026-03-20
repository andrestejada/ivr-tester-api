"""add RUNNING to test_status enum

Revision ID: 040f82a2dd0b
Revises: def789ghi012
Create Date: 2026-03-18 22:01:47.340116

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '040f82a2dd0b'
down_revision: Union[str, Sequence[str], None] = 'def789ghi012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE test_status ADD VALUE 'RUNNING'")

def downgrade() -> None:
    """Downgrade schema."""
    # Note: PostgreSQL does not support dropping a value from an enum type easily.
    pass
