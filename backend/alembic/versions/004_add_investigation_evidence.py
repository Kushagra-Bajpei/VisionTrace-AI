"""Add investigation_evidence table and tags to investigations

Revision ID: 004_add_investigation_evidence
Revises: 003_add_embedding_fields
Create Date: 2026-11-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = '004_add_investigation_evidence'
down_revision: Union[str, None] = '003_add_embedding_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

json_type = sa.JSON().with_variant(JSONB, 'postgresql')


def upgrade() -> None:
    # 1. Add tags column to investigations
    with op.batch_alter_table('investigations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tags', json_type, nullable=True))

    # 2. Create investigation_evidence table
    op.create_table(
        'investigation_evidence',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('investigation_id', sa.Uuid(), nullable=False),
        sa.Column('video_id', sa.Uuid(), nullable=False),
        sa.Column('timestamp', sa.Float(), nullable=False),
        sa.Column('event_id', sa.Uuid(), nullable=True),
        sa.Column('track_id', sa.Uuid(), nullable=True),
        sa.Column('evidence_type', sa.String(length=50), nullable=False, server_default='detection'),
        sa.Column('frame_path', sa.String(length=512), nullable=True),
        sa.Column('crop_path', sa.String(length=512), nullable=True),
        sa.Column('object_class', sa.String(length=100), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('visual_similarity_score', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('sequence_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('custom_metadata', json_type, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['investigation_id'], ['investigations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_investigation_evidence_id'), 'investigation_evidence', ['id'], unique=False)
    op.create_index(op.f('ix_investigation_evidence_investigation_id'), 'investigation_evidence', ['investigation_id'], unique=False)
    op.create_index(op.f('ix_investigation_evidence_video_id'), 'investigation_evidence', ['video_id'], unique=False)
    op.create_index(op.f('ix_investigation_evidence_timestamp'), 'investigation_evidence', ['timestamp'], unique=False)
    op.create_index(op.f('ix_investigation_evidence_event_id'), 'investigation_evidence', ['event_id'], unique=False)
    op.create_index(op.f('ix_investigation_evidence_track_id'), 'investigation_evidence', ['track_id'], unique=False)
    op.create_index(op.f('ix_investigation_evidence_evidence_type'), 'investigation_evidence', ['evidence_type'], unique=False)


def downgrade() -> None:
    op.drop_table('investigation_evidence')
    with op.batch_alter_table('investigations', schema=None) as batch_op:
        batch_op.drop_column('tags')
