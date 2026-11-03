"""Allow nullable event_id and add frame_path, timestamp, crop_path to embeddings table

Revision ID: 003_add_embedding_fields
Revises: 002_add_processing_progress
Create Date: 2026-11-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003_add_embedding_fields'
down_revision: Union[str, None] = '002_add_processing_progress'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('embeddings', schema=None) as batch_op:
        batch_op.alter_column('event_id', existing_type=sa.Uuid(), nullable=True)
        batch_op.add_column(sa.Column('frame_path', sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column('timestamp', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('crop_path', sa.String(length=512), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('embeddings', schema=None) as batch_op:
        batch_op.drop_column('crop_path')
        batch_op.drop_column('timestamp')
        batch_op.drop_column('frame_path')
        batch_op.alter_column('event_id', existing_type=sa.Uuid(), nullable=False)
