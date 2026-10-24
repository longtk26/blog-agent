"""epic5 publications

Revision ID: 0005_publications
Revises: 0004_approvals
Create Date: 2026-10-24 02:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = '0005_publications'
down_revision: Union[str, Sequence[str], None] = '0004_approvals'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'publications',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('task_id', sa.Uuid(), nullable=False),
        sa.Column('article_revision_id', sa.Uuid(), nullable=False),
        sa.Column('destination', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column('remote_document_id', sqlmodel.sql.sqltypes.AutoString(length=128), nullable=True),
        sa.Column('remote_url', sqlmodel.sql.sqltypes.AutoString(length=512), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rendered_content_hash', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['article_revision_id'], ['article_revisions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['writing_tasks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_publications_article_revision_id'), 'publications', ['article_revision_id'], unique=False)
    op.create_index(op.f('ix_publications_task_id'), 'publications', ['task_id'], unique=False)
    op.create_index('uq_publications_task_destination', 'publications', ['task_id', 'destination'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_publications_task_destination', table_name='publications')
    op.drop_index(op.f('ix_publications_task_id'), table_name='publications')
    op.drop_index(op.f('ix_publications_article_revision_id'), table_name='publications')
    op.drop_table('publications')
