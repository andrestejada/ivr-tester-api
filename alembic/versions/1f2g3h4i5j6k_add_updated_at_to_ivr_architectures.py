"""add updated_at to ivr_architectures

Revision ID: 1f2g3h4i5j6k
Revises: 7a8c9d0e1f2g
Create Date: 2026-04-08 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1f2g3h4i5j6k'
down_revision: Union[str, Sequence[str], None] = '7a8c9d0e1f2g'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('ivr_architectures', 
                  sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('ivr_architectures', 'updated_at')
