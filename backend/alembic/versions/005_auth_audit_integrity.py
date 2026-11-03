"""Add authentication, case ownership, evidence integrity hashes, audit logs, and revoked tokens

Revision ID: 005_auth_audit_integrity
Revises: 004_add_investigation_evidence
Create Date: 2026-11-04
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = '005_auth_audit_integrity'
down_revision: Union[str, None] = '004_add_investigation_evidence'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

json_type = sa.JSON().with_variant(JSONB, 'postgresql')


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Create revoked_tokens table if not exists
    if 'revoked_tokens' not in existing_tables:
        op.create_table(
            'revoked_tokens',
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('jti', sa.String(64), nullable=False),
            sa.Column('user_id', sa.Uuid(), nullable=False),
            sa.Column('revoked_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_revoked_tokens_jti', 'revoked_tokens', ['jti'], unique=True)
        op.create_index('ix_revoked_tokens_user_id', 'revoked_tokens', ['user_id'])
        op.create_index('ix_revoked_tokens_expires_at', 'revoked_tokens', ['expires_at'])

    # 2. Create audit_logs table if not exists
    if 'audit_logs' not in existing_tables:
        op.create_table(
            'audit_logs',
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('actor_id', sa.Uuid(), nullable=True),
            sa.Column('actor_email', sa.String(255), nullable=True),
            sa.Column('action', sa.String(100), nullable=False),
            sa.Column('target_type', sa.String(50), nullable=False),
            sa.Column('target_id', sa.String(255), nullable=True),
            sa.Column('outcome', sa.String(50), server_default='success', nullable=False),
            sa.Column('client_ip', sa.String(64), nullable=True),
            sa.Column('details', json_type, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_audit_logs_actor_id', 'audit_logs', ['actor_id'])
        op.create_index('ix_audit_logs_actor_email', 'audit_logs', ['actor_email'])
        op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
        op.create_index('ix_audit_logs_target_type', 'audit_logs', ['target_type'])
        op.create_index('ix_audit_logs_target_id', 'audit_logs', ['target_id'])
        op.create_index('ix_audit_logs_outcome', 'audit_logs', ['outcome'])
        op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])

    # 3. Add ownership and reviewer columns to investigations
    inv_cols = {c['name'] for c in inspector.get_columns('investigations')}
    with op.batch_alter_table('investigations', schema=None) as batch_op:
        if 'owner_id' not in inv_cols:
            batch_op.add_column(sa.Column('owner_id', sa.Uuid(), nullable=True))
            batch_op.create_foreign_key('fk_investigations_owner', 'users', ['owner_id'], ['id'], ondelete='SET NULL')
            batch_op.create_index('ix_investigations_owner_id', ['owner_id'])
        if 'reviewer_id' not in inv_cols:
            batch_op.add_column(sa.Column('reviewer_id', sa.Uuid(), nullable=True))
            batch_op.create_foreign_key('fk_investigations_reviewer', 'users', ['reviewer_id'], ['id'], ondelete='SET NULL')
            batch_op.create_index('ix_investigations_reviewer_id', ['reviewer_id'])

    # Backfill owner_id from lead_investigator_id where available (defensible legacy mapping)
    op.execute(
        "UPDATE investigations SET owner_id = lead_investigator_id WHERE lead_investigator_id IS NOT NULL AND owner_id IS NULL"
    )

    # 4. Add integrity hash columns to videos
    vid_cols = {c['name'] for c in inspector.get_columns('videos')}
    with op.batch_alter_table('videos', schema=None) as batch_op:
        if 'file_hash' not in vid_cols:
            batch_op.add_column(sa.Column('file_hash', sa.String(64), nullable=True))
            batch_op.add_column(sa.Column('hash_algorithm', sa.String(32), server_default='sha256', nullable=True))
            batch_op.add_column(sa.Column('hashed_at', sa.DateTime(timezone=True), nullable=True))

    # 5. Add integrity hash columns to investigation_evidence
    ev_cols = {c['name'] for c in inspector.get_columns('investigation_evidence')}
    with op.batch_alter_table('investigation_evidence', schema=None) as batch_op:
        if 'evidence_hash' not in ev_cols:
            batch_op.add_column(sa.Column('evidence_hash', sa.String(64), nullable=True))
            batch_op.add_column(sa.Column('hash_algorithm', sa.String(32), server_default='sha256', nullable=True))
            batch_op.add_column(sa.Column('hashed_at', sa.DateTime(timezone=True), nullable=True))

    # 6. Add integrity hash columns to reports
    rep_cols = {c['name'] for c in inspector.get_columns('reports')}
    with op.batch_alter_table('reports', schema=None) as batch_op:
        if 'pdf_hash' not in rep_cols:
            batch_op.add_column(sa.Column('pdf_hash', sa.String(64), nullable=True))
            batch_op.add_column(sa.Column('hash_algorithm', sa.String(32), server_default='sha256', nullable=True))
            batch_op.add_column(sa.Column('hashed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.drop_column('hashed_at')
        batch_op.drop_column('hash_algorithm')
        batch_op.drop_column('pdf_hash')

    with op.batch_alter_table('investigation_evidence', schema=None) as batch_op:
        batch_op.drop_column('hashed_at')
        batch_op.drop_column('hash_algorithm')
        batch_op.drop_column('evidence_hash')

    with op.batch_alter_table('videos', schema=None) as batch_op:
        batch_op.drop_column('hashed_at')
        batch_op.drop_column('hash_algorithm')
        batch_op.drop_column('file_hash')

    with op.batch_alter_table('investigations', schema=None) as batch_op:
        batch_op.drop_index('ix_investigations_reviewer_id')
        batch_op.drop_index('ix_investigations_owner_id')
        batch_op.drop_constraint('fk_investigations_reviewer', type_='foreignkey')
        batch_op.drop_constraint('fk_investigations_owner', type_='foreignkey')
        batch_op.drop_column('reviewer_id')
        batch_op.drop_column('owner_id')

    op.drop_table('audit_logs')
    op.drop_table('revoked_tokens')
