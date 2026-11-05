"""epic10 diagram visual review result on diagram_assets

Revision ID: 0009_diagram_review
Revises: 0008_run_usage
Create Date: 2026-11-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '0009_diagram_review'
down_revision: Union[str, Sequence[str], None] = '0008_run_usage'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('diagram_assets', sa.Column('review', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('diagram_assets', sa.Column('review_rounds', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('diagram_assets', 'review_rounds')
    op.drop_column('diagram_assets', 'review')
