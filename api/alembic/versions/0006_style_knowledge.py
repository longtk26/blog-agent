"""epic6 style and knowledge base

Revision ID: 0006_style_knowledge
Revises: 0005_publications
Create Date: 2026-10-24 06:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sqlmodel

from src.configs.config import config

# revision identifiers, used by Alembic.
revision: str = '0006_style_knowledge'
down_revision: Union[str, Sequence[str], None] = '0005_publications'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # Add use_style_examples to writing_tasks
    op.add_column('writing_tasks', sa.Column('use_style_examples', sa.Boolean(), nullable=False, server_default='true'))

    # 2. writing_samples table
    op.create_table(
        'writing_samples',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('origin', sa.String(length=32), nullable=False),
        sa.Column('remote_id', sa.String(length=256), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_as_style_example', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_writing_samples_origin'), 'writing_samples', ['origin'], unique=False)
    op.create_index(op.f('ix_writing_samples_remote_id'), 'writing_samples', ['remote_id'], unique=False)
    op.create_index(op.f('ix_writing_samples_published_at'), 'writing_samples', ['published_at'], unique=False)
    op.create_index(op.f('ix_writing_samples_approved_as_style_example'), 'writing_samples', ['approved_as_style_example'], unique=False)
    op.create_index(op.f('ix_writing_samples_content_hash'), 'writing_samples', ['content_hash'], unique=False)
    op.create_index('uq_writing_samples_origin_remote_id', 'writing_samples', ['origin', 'remote_id'], unique=True)

    # 3. owner_notes table
    op.create_table(
        'owner_notes',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('citable_url', sa.Text(), nullable=True),
        sa.Column('quality_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # 4. sample_chunks table
    embedding_dim = config.embedding_dim or 768
    op.create_table(
        'sample_chunks',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('sample_id', sa.Uuid(), nullable=True),
        sa.Column('note_id', sa.Uuid(), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('heading_path', sa.Text(), nullable=False, server_default=''),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('chunk_type', sa.String(length=32), nullable=False, server_default='section'),
        sa.Column('embedding', Vector(embedding_dim), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['sample_id'], ['writing_samples.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['note_id'], ['owner_notes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_sample_chunks_sample_id'), 'sample_chunks', ['sample_id'], unique=False)
    op.create_index(op.f('ix_sample_chunks_note_id'), 'sample_chunks', ['note_id'], unique=False)
    op.create_index(op.f('ix_sample_chunks_chunk_type'), 'sample_chunks', ['chunk_type'], unique=False)
    op.execute(
        "CREATE INDEX IF NOT EXISTS sample_chunks_embedding_hnsw_idx ON sample_chunks USING hnsw (embedding vector_cosine_ops);"
    )

    # 5. style_profiles table
    op.create_table(
        'style_profiles',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('name', sa.String(length=128), nullable=False, server_default='Default Profile'),
        sa.Column('profile_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('markdown_content', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_style_profiles_version'), 'style_profiles', ['version'], unique=False)
    op.create_index(op.f('ix_style_profiles_is_active'), 'style_profiles', ['is_active'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_style_profiles_is_active'), table_name='style_profiles')
    op.drop_index(op.f('ix_style_profiles_version'), table_name='style_profiles')
    op.drop_table('style_profiles')

    op.execute("DROP INDEX IF EXISTS sample_chunks_embedding_hnsw_idx;")
    op.drop_index(op.f('ix_sample_chunks_chunk_type'), table_name='sample_chunks')
    op.drop_index(op.f('ix_sample_chunks_note_id'), table_name='sample_chunks')
    op.drop_index(op.f('ix_sample_chunks_sample_id'), table_name='sample_chunks')
    op.drop_table('sample_chunks')

    op.drop_table('owner_notes')

    op.drop_index('uq_writing_samples_origin_remote_id', table_name='writing_samples')
    op.drop_index(op.f('ix_writing_samples_content_hash'), table_name='writing_samples')
    op.drop_index(op.f('ix_writing_samples_approved_as_style_example'), table_name='writing_samples')
    op.drop_index(op.f('ix_writing_samples_published_at'), table_name='writing_samples')
    op.drop_index(op.f('ix_writing_samples_remote_id'), table_name='writing_samples')
    op.drop_index(op.f('ix_writing_samples_origin'), table_name='writing_samples')
    op.drop_table('writing_samples')

    op.drop_column('writing_tasks', 'use_style_examples')
