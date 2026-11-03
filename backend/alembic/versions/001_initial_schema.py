"""Initial schema migration with 9 core tables and pgvector extension

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-11-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 0. Enable pgvector extension if PostgreSQL
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)
    op.create_index(op.f('ix_users_created_at'), 'users', ['created_at'], unique=False)

    # 2. cameras
    op.create_table(
        'cameras',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('rtsp_url', sa.String(length=512), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cameras_id'), 'cameras', ['id'], unique=False)
    op.create_index(op.f('ix_cameras_name'), 'cameras', ['name'], unique=False)
    op.create_index(op.f('ix_cameras_status'), 'cameras', ['status'], unique=False)
    op.create_index(op.f('ix_cameras_created_at'), 'cameras', ['created_at'], unique=False)

    # 3. videos
    op.create_table(
        'videos',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('camera_id', sa.Uuid(), nullable=True),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=512), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('duration', sa.Float(), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('fps', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('thumbnail_path', sa.String(length=512), nullable=True),
        sa.Column('video_metadata', sa.JSON().with_variant(JSONB, 'postgresql'), nullable=True),
        sa.Column('uploaded_by', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['camera_id'], ['cameras.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_videos_id'), 'videos', ['id'], unique=False)
    op.create_index(op.f('ix_videos_camera_id'), 'videos', ['camera_id'], unique=False)
    op.create_index(op.f('ix_videos_uploaded_by'), 'videos', ['uploaded_by'], unique=False)
    op.create_index(op.f('ix_videos_status'), 'videos', ['status'], unique=False)
    op.create_index(op.f('ix_videos_created_at'), 'videos', ['created_at'], unique=False)

    # 4. tracks
    op.create_table(
        'tracks',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('video_id', sa.Uuid(), nullable=False),
        sa.Column('track_id', sa.Integer(), nullable=False),
        sa.Column('object_class', sa.String(length=100), nullable=False),
        sa.Column('start_time', sa.Float(), nullable=False),
        sa.Column('end_time', sa.Float(), nullable=False),
        sa.Column('start_frame', sa.Integer(), nullable=False),
        sa.Column('end_frame', sa.Integer(), nullable=False),
        sa.Column('confidence_avg', sa.Float(), nullable=False),
        sa.Column('attributes', sa.JSON().with_variant(JSONB, 'postgresql'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tracks_id'), 'tracks', ['id'], unique=False)
    op.create_index(op.f('ix_tracks_video_id'), 'tracks', ['video_id'], unique=False)
    op.create_index(op.f('ix_tracks_track_id'), 'tracks', ['track_id'], unique=False)
    op.create_index(op.f('ix_tracks_object_class'), 'tracks', ['object_class'], unique=False)
    op.create_index(op.f('ix_tracks_created_at'), 'tracks', ['created_at'], unique=False)

    # 5. events
    op.create_table(
        'events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('video_id', sa.Uuid(), nullable=False),
        sa.Column('camera_id', sa.Uuid(), nullable=True),
        sa.Column('track_id', sa.Uuid(), nullable=True),
        sa.Column('timestamp', sa.Float(), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('bounding_box', sa.JSON().with_variant(JSONB, 'postgresql'), nullable=True),
        sa.Column('frame_path', sa.String(length=512), nullable=True),
        sa.Column('clip_start_time', sa.Float(), nullable=True),
        sa.Column('clip_end_time', sa.Float(), nullable=True),
        sa.Column('clip_path', sa.String(length=512), nullable=True),
        sa.Column('attributes', sa.JSON().with_variant(JSONB, 'postgresql'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['camera_id'], ['cameras.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_events_id'), 'events', ['id'], unique=False)
    op.create_index(op.f('ix_events_video_id'), 'events', ['video_id'], unique=False)
    op.create_index(op.f('ix_events_camera_id'), 'events', ['camera_id'], unique=False)
    op.create_index(op.f('ix_events_track_id'), 'events', ['track_id'], unique=False)
    op.create_index(op.f('ix_events_timestamp'), 'events', ['timestamp'], unique=False)
    op.create_index(op.f('ix_events_event_type'), 'events', ['event_type'], unique=False)
    op.create_index(op.f('ix_events_created_at'), 'events', ['created_at'], unique=False)
    op.create_index('ix_events_video_timestamp', 'events', ['video_id', 'timestamp'], unique=False)
    op.create_index('ix_events_type_timestamp', 'events', ['event_type', 'timestamp'], unique=False)

    # 6. embeddings
    op.create_table(
        'embeddings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('event_id', sa.Uuid(), nullable=False),
        sa.Column('video_id', sa.Uuid(), nullable=False),
        sa.Column('embedding_type', sa.String(length=50), nullable=False),
        sa.Column('embedding', Vector(512), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_embeddings_id'), 'embeddings', ['id'], unique=False)
    op.create_index(op.f('ix_embeddings_event_id'), 'embeddings', ['event_id'], unique=False)
    op.create_index(op.f('ix_embeddings_video_id'), 'embeddings', ['video_id'], unique=False)
    op.create_index(op.f('ix_embeddings_embedding_type'), 'embeddings', ['embedding_type'], unique=False)
    op.create_index('ix_embeddings_event_type', 'embeddings', ['event_id', 'embedding_type'], unique=False)

    # 7. investigations
    op.create_table(
        'investigations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('priority', sa.String(length=50), nullable=False),
        sa.Column('lead_investigator_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['lead_investigator_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_investigations_id'), 'investigations', ['id'], unique=False)
    op.create_index(op.f('ix_investigations_title'), 'investigations', ['title'], unique=False)
    op.create_index(op.f('ix_investigations_status'), 'investigations', ['status'], unique=False)
    op.create_index(op.f('ix_investigations_priority'), 'investigations', ['priority'], unique=False)
    op.create_index(op.f('ix_investigations_lead_investigator_id'), 'investigations', ['lead_investigator_id'], unique=False)
    op.create_index(op.f('ix_investigations_created_at'), 'investigations', ['created_at'], unique=False)

    # 8. investigation_messages
    op.create_table(
        'investigation_messages',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('investigation_id', sa.Uuid(), nullable=False),
        sa.Column('sender_type', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('references', sa.JSON().with_variant(JSONB, 'postgresql'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['investigation_id'], ['investigations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_investigation_messages_id'), 'investigation_messages', ['id'], unique=False)
    op.create_index(op.f('ix_investigation_messages_investigation_id'), 'investigation_messages', ['investigation_id'], unique=False)
    op.create_index(op.f('ix_investigation_messages_sender_type'), 'investigation_messages', ['sender_type'], unique=False)
    op.create_index(op.f('ix_investigation_messages_created_at'), 'investigation_messages', ['created_at'], unique=False)

    # 9. reports
    op.create_table(
        'reports',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('investigation_id', sa.Uuid(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('executive_summary', sa.Text(), nullable=False),
        sa.Column('findings', sa.JSON().with_variant(JSONB, 'postgresql'), nullable=True),
        sa.Column('evidence_timeline', sa.JSON().with_variant(JSONB, 'postgresql'), nullable=True),
        sa.Column('generated_by_ai', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('pdf_path', sa.String(length=512), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['investigation_id'], ['investigations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reports_id'), 'reports', ['id'], unique=False)
    op.create_index(op.f('ix_reports_investigation_id'), 'reports', ['investigation_id'], unique=False)
    op.create_index(op.f('ix_reports_title'), 'reports', ['title'], unique=False)
    op.create_index(op.f('ix_reports_status'), 'reports', ['status'], unique=False)
    op.create_index(op.f('ix_reports_created_by'), 'reports', ['created_by'], unique=False)
    op.create_index(op.f('ix_reports_created_at'), 'reports', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('reports')
    op.drop_table('investigation_messages')
    op.drop_table('investigations')
    op.drop_table('embeddings')
    op.drop_table('events')
    op.drop_table('tracks')
    op.drop_table('videos')
    op.drop_table('cameras')
    op.drop_table('users')

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP EXTENSION IF EXISTS vector")
