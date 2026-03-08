"""Create initial database schema

Revision ID: 001
Revises:
Create Date: 2026-03-08

Creates all Phase 3 tables:
- exclusions: Main exclusion candidate records
- audit_log: Immutable append-only decision trail
- approval_overrides: Human override decisions with training data
- processing_jobs: Background job tracking
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create exclusions table
    op.create_table(
        'exclusions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_doc', sa.String(255), nullable=False),
        sa.Column('company_name', sa.String(255), nullable=False),
        sa.Column('extracted_company', postgresql.JSON(), nullable=False),
        sa.Column('normalized_company', postgresql.JSON(), nullable=False),
        sa.Column('aladdin_match', postgresql.JSON(), nullable=False),
        sa.Column('overall_confidence', sa.Float(), nullable=False),
        sa.Column('ocr_confidence', sa.Float(), server_default='0.0'),
        sa.Column('entity_resolution_confidence', sa.Float(), server_default='0.0'),
        sa.Column('aladdin_match_confidence', sa.Float(), server_default='0.0'),
        sa.Column('confidence_breakdown', postgresql.JSON(), nullable=False),
        sa.Column('status', sa.String(50), server_default='pending', nullable=False),
        sa.Column('agent_version', sa.String(50)),
        sa.Column('processing_time_ms', sa.Float()),
        sa.Column('reviewed_by', sa.String(255)),
        sa.Column('reviewed_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_status', 'status'),
        sa.Index('idx_created_at', 'created_at'),
        sa.Index('idx_company_name', 'company_name'),
    )

    # Create audit_log table
    op.create_table(
        'audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('exclusion_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('agent_name', sa.String(100)),
        sa.Column('user_id', sa.String(255)),
        sa.Column('username', sa.String(255)),
        sa.Column('input_data', postgresql.JSON(), nullable=False),
        sa.Column('output_data', postgresql.JSON(), nullable=False),
        sa.Column('confidence_score', sa.Float()),
        sa.Column('audit_explanation', sa.Text()),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['exclusion_id'], ['exclusions.id'], ondelete='CASCADE'),
        sa.Index('idx_exclusion_id', 'exclusion_id'),
        sa.Index('idx_timestamp', 'timestamp'),
    )

    # Create approval_overrides table
    op.create_table(
        'approval_overrides',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('exclusion_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('original_status', sa.String(50), nullable=False),
        sa.Column('new_status', sa.String(50), nullable=False),
        sa.Column('approved_by', sa.String(255), nullable=False),
        sa.Column('approved_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('override_reason', sa.Text(), nullable=False),
        sa.Column('confidence_override_justification', sa.Text()),
        sa.Column('training_feedback', sa.Text()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['exclusion_id'], ['exclusions.id'], ondelete='CASCADE'),
        sa.Index('idx_exclusion_id_override', 'exclusion_id'),
        sa.Index('idx_approved_at', 'approved_at'),
    )

    # Create processing_jobs table
    op.create_table(
        'processing_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('doc_type', sa.String(50)),
        sa.Column('status', sa.String(50), server_default='queued', nullable=False),
        sa.Column('started_at', sa.DateTime()),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('processing_time_ms', sa.Float()),
        sa.Column('total_candidates', sa.String(50), server_default='0'),
        sa.Column('auto_approved', sa.String(50), server_default='0'),
        sa.Column('pending_review', sa.String(50), server_default='0'),
        sa.Column('error_message', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_status_job', 'status'),
        sa.Index('idx_created_at_job', 'created_at'),
    )


def downgrade() -> None:
    # Drop tables in reverse order of creation
    op.drop_table('processing_jobs')
    op.drop_table('approval_overrides')
    op.drop_table('audit_log')
    op.drop_table('exclusions')
