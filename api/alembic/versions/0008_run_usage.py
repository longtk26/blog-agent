"""epic9 run_usage table for token, cost and latency tracking

Revision ID: 0008_run_usage
Revises: 0007_diagram_assets
Create Date: 2026-10-25 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0008_run_usage'
down_revision: Union[str, Sequence[str], None] = '0007_diagram_assets'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'run_usage',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('task_id', sa.Uuid(), nullable=False),
        sa.Column('run_id', sa.Uuid(), nullable=True),
        sa.Column('node', sa.String(length=64), nullable=False),
        sa.Column('model', sa.String(length=128), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cached_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('latency_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cost_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['task_id'], ['writing_tasks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_run_usage_task_id'), 'run_usage', ['task_id'], unique=False)
    op.create_index(op.f('ix_run_usage_run_id'), 'run_usage', ['run_id'], unique=False)
    op.create_index(op.f('ix_run_usage_node'), 'run_usage', ['node'], unique=False)
    op.create_index(op.f('ix_run_usage_model'), 'run_usage', ['model'], unique=False)
    op.create_index(op.f('ix_run_usage_created_at'), 'run_usage', ['created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_run_usage_created_at'), table_name='run_usage')
    op.drop_index(op.f('ix_run_usage_model'), table_name='run_usage')
    op.drop_index(op.f('ix_run_usage_node'), table_name='run_usage')
    op.drop_index(op.f('ix_run_usage_run_id'), table_name='run_usage')
    op.drop_index(op.f('ix_run_usage_task_id'), table_name='run_usage')
    op.drop_table('run_usage')
