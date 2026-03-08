"""
SQLAlchemy Database Models and Session Management

Implements ORM models for:
- exclusions: Main ExclusionCandidate records
- audit_log: Immutable decision trail
- approval_overrides: Human override decisions with training data
- processing_jobs: Background job tracking
"""

import os
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    create_engine,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://aladdin:password@localhost:5432/aladdin_parser"
)

# Create async engine for FastAPI
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
    future=True,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=20,
    max_overflow=0,
)

# Async session factory
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, future=True
)

# Base class for all models
Base = declarative_base()


# Dependency for FastAPI routes
async def get_async_session() -> AsyncSession:
    """Get async database session for FastAPI routes"""
    async with AsyncSessionLocal() as session:
        yield session


class ExclusionDB(Base):
    """Main exclusion candidate records from orchestrator"""

    __tablename__ = "exclusions"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Document metadata
    source_doc = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=False, index=True)

    # Extracted/normalized company data (stored as JSONB for flexibility)
    extracted_company = Column(JSON, nullable=False)  # ExtractedCompany dict
    normalized_company = Column(JSON, nullable=False)  # NormalizedCompany dict
    aladdin_match = Column(JSON, nullable=False)  # AladdinMatch dict

    # Confidence scores (individual components)
    overall_confidence = Column(Float, nullable=False)
    ocr_confidence = Column(Float, default=0.0)
    entity_resolution_confidence = Column(Float, default=0.0)
    aladdin_match_confidence = Column(Float, default=0.0)

    # Confidence breakdown (detailed explanation)
    confidence_breakdown = Column(JSON, nullable=False)

    # Status & workflow
    status = Column(String(50), nullable=False, default="pending", index=True)
    # Values: pending, auto_approved, approved, rejected, synced

    # Agent metadata
    agent_version = Column(String(50))
    processing_time_ms = Column(Float)

    # Human review metadata
    reviewed_by = Column(String(255))
    reviewed_at = Column(DateTime)

    # Audit timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes for common queries
    __table_args__ = (
        Index("idx_exclusions_status", "status"),
        Index("idx_exclusions_created_at", "created_at"),
        Index("idx_exclusions_company_name", "company_name"),
    )

    def __repr__(self):
        return f"<ExclusionDB id={self.id} company={self.company_name} status={self.status}>"


class AuditLogDB(Base):
    """Immutable append-only decision trail for each exclusion"""

    __tablename__ = "audit_log"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Reference to exclusion
    exclusion_id = Column(
        UUID(as_uuid=True),
        ForeignKey("exclusions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Action details
    action = Column(String(50), nullable=False)
    # Values: extract, resolve, match, aggregate, approve, override, reject, sync

    # Who made the decision
    agent_name = Column(String(100))  # Agent that performed action
    user_id = Column(String(255))  # Human user (if manual action)
    username = Column(String(255))

    # What happened
    input_data = Column(JSON, nullable=False)  # Input to the agent/action
    output_data = Column(JSON, nullable=False)  # Output/result

    # Why (audit explanation)
    confidence_score = Column(Float)
    audit_explanation = Column(Text)

    # Timestamp (immutable)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Indexes
    __table_args__ = (
        Index("idx_audit_exclusion_id", "exclusion_id"),
        Index("idx_audit_timestamp", "timestamp"),
    )

    def __repr__(self):
        return f"<AuditLogDB exclusion={self.exclusion_id} action={self.action}>"


class ApprovalOverrideDB(Base):
    """Human override decisions with training data for model improvement"""

    __tablename__ = "approval_overrides"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Reference to exclusion
    exclusion_id = Column(
        UUID(as_uuid=True),
        ForeignKey("exclusions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Status transition
    original_status = Column(String(50), nullable=False)
    new_status = Column(String(50), nullable=False)

    # Who and when
    approved_by = Column(String(255), nullable=False)
    approved_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Why (reason for override)
    override_reason = Column(Text, nullable=False)
    confidence_override_justification = Column(Text)

    # Training data for future model improvement
    training_feedback = Column(Text)

    # Indexes
    __table_args__ = (
        Index("idx_override_exclusion_id", "exclusion_id"),
        Index("idx_override_approved_at", "approved_at"),
    )

    def __repr__(self):
        return f"<ApprovalOverrideDB exclusion={self.exclusion_id} override_by={self.approved_by}>"


class ProcessingJobDB(Base):
    """Background job tracking for document processing"""

    __tablename__ = "processing_jobs"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Job metadata
    file_path = Column(String(500), nullable=False)
    doc_type = Column(String(50))

    # Status
    status = Column(String(50), default="queued", nullable=False, index=True)
    # Values: queued, processing, completed, failed

    # Progress tracking
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    processing_time_ms = Column(Float)

    # Results
    total_candidates = Column(String(50), default=0)
    auto_approved = Column(String(50), default=0)
    pending_review = Column(String(50), default=0)

    # Error tracking
    error_message = Column(Text)

    # Audit timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Indexes
    __table_args__ = (
        Index("idx_processing_jobs_status", "status"),
        Index("idx_processing_jobs_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<ProcessingJobDB id={self.id} file={self.file_path} status={self.status}>"


async def init_db():
    """Create all tables (async version)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections"""
    await engine.dispose()
