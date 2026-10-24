"""epic7 editable diagrams and diagram assets

Revision ID: 0007_diagram_assets
Revises: 0006_style_knowledge
Create Date: 2026-10-24 07:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0007_diagram_assets'
down_revision: Union[str, Sequence[str], None] = '0006_style_knowledge'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add diagram_format to writing_tasks
    op.add_column('writing_tasks', sa.Column('diagram_format', sa.String(length=16), nullable=False, server_default='auto'))

    # 2. Create diagram_assets table
    op.create_table(
        'diagram_assets',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('task_id', sa.Uuid(), nullable=False),
        sa.Column('article_revision_id', sa.Uuid(), nullable=True),
        sa.Column('slot_id', sa.String(length=64), nullable=False),
        sa.Column('format', sa.String(length=16), nullable=False),
        sa.Column('spec', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('source_path', sa.Text(), nullable=False),
        sa.Column('svg_path', sa.Text(), nullable=True),
        sa.Column('png_path', sa.Text(), nullable=True),
        sa.Column('sha256', sa.String(length=64), nullable=False, server_default=''),
        sa.Column('validation_status', sa.String(length=16), nullable=False, server_default='valid'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['task_id'], ['writing_tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['article_revision_id'], ['article_revisions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_diagram_assets_task_id'), 'diagram_assets', ['task_id'], unique=False)
    op.create_index(op.f('ix_diagram_assets_article_revision_id'), 'diagram_assets', ['article_revision_id'], unique=False)
    op.create_index(op.f('ix_diagram_assets_slot_id'), 'diagram_assets', ['slot_id'], unique=False)
    op.create_index(op.f('ix_diagram_assets_sha256'), 'diagram_assets', ['sha256'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_diagram_assets_sha256'), table_name='diagram_assets')
    op.drop_index(op.f('ix_diagram_assets_slot_id'), table_name='diagram_assets')
    op.drop_index(op.f('ix_diagram_assets_article_revision_id'), table_name='diagram_assets')
    op.drop_index(op.f('ix_diagram_assets_task_id'), table_name='diagram_assets')
    op.drop_table('diagram_assets')
    op.drop_column('writing_tasks', 'diagram_format')
