"""
Pydantic Models for Request/Response Validation

Schemas for:
- ExclusionCandidate input from orchestrator
- API responses with audit metadata
- Approval workflow requests
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ConfidenceBreakdownSchema(BaseModel):
    """Confidence score breakdown explanation"""

    ocr_weight: float = Field(..., ge=0.0, le=1.0)
    entity_weight: float = Field(..., ge=0.0, le=1.0)
    aladdin_weight: float = Field(..., ge=0.0, le=1.0)

    ocr_contribution: float = Field(..., ge=0.0, le=1.0)
    entity_contribution: float = Field(..., ge=0.0, le=1.0)
    aladdin_contribution: float = Field(..., ge=0.0, le=1.0)

    calculation: str  # Formula explanation

    class Config:
        json_schema_extra = {
            "example": {
                "ocr_weight": 0.20,
                "entity_weight": 0.30,
                "aladdin_weight": 0.50,
                "ocr_contribution": 0.15,
                "entity_contribution": 0.27,
                "aladdin_contribution": 0.45,
                "calculation": "(0.75 * 0.20) + (0.90 * 0.30) + (0.90 * 0.50) = 0.87"
            }
        }


class ExtractedCompanySchema(BaseModel):
    """Extracted company data"""

    raw_name: str
    aliases: Optional[List[str]] = []
    ocr_confidence: float = Field(..., ge=0.0, le=1.0)
    extraction_source: str  # pdf, email, csv, text
    source_doc: str


class NormalizedCompanySchema(BaseModel):
    """Normalized/canonical company data"""

    canonical_name: str
    normalization_confidence: float = Field(..., ge=0.0, le=1.0)
    normalization_notes: Optional[str] = None


class AladdinMatchSchema(BaseModel):
    """Aladdin match result"""

    aladdin_id: Optional[str] = None
    isin: Optional[str] = None
    entity_name: Optional[str] = None
    match_confidence: float = Field(..., ge=0.0, le=1.0)
    match_type: str  # exact, fuzzy, manual_required
    api_response_time_ms: Optional[float] = None


class ExclusionCandidateCreate(BaseModel):
    """Input from orchestrator: Create new exclusion"""

    # Metadata
    source_doc: str
    company_name: str

    # Extracted data
    extracted_company: Dict[str, Any]
    normalized_company: Dict[str, Any]
    aladdin_match: Dict[str, Any]

    # Confidence scores
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    ocr_confidence: float = Field(..., ge=0.0, le=1.0)
    entity_resolution_confidence: float = Field(..., ge=0.0, le=1.0)
    aladdin_match_confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_breakdown: Dict[str, Any]

    # Agent metadata
    agent_version: Optional[str] = None
    processing_time_ms: Optional[float] = None

    class Config:
        json_schema_extra = {
            "example": {
                "source_doc": "example.pdf",
                "company_name": "Goldman Sachs",
                "extracted_company": {"raw_name": "GS", "ocr_confidence": 0.95},
                "normalized_company": {"canonical_name": "Goldman Sachs", "normalization_confidence": 0.99},
                "aladdin_match": {"aladdin_id": "GS001", "match_confidence": 1.0},
                "overall_confidence": 0.98,
                "ocr_confidence": 0.95,
                "entity_resolution_confidence": 0.99,
                "aladdin_match_confidence": 1.0,
                "confidence_breakdown": {"ocr_weight": 0.20, "entity_weight": 0.30, "aladdin_weight": 0.50},
                "agent_version": "v1-orchestrator"
            }
        }


class ExclusionCandidateResponse(BaseModel):
    """Response with full exclusion data and metadata"""

    id: UUID
    source_doc: str
    company_name: str

    # Confidence scores
    overall_confidence: float
    ocr_confidence: float
    entity_resolution_confidence: float
    aladdin_match_confidence: float
    confidence_breakdown: Dict[str, Any]

    # Status
    status: str  # pending, auto_approved, approved, rejected, synced

    # Agent metadata
    agent_version: Optional[str] = None
    processing_time_ms: Optional[float] = None

    # Review metadata
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "source_doc": "example.pdf",
                "company_name": "Goldman Sachs",
                "overall_confidence": 0.98,
                "ocr_confidence": 0.95,
                "entity_resolution_confidence": 0.99,
                "aladdin_match_confidence": 1.0,
                "confidence_breakdown": {},
                "status": "auto_approved",
                "reviewed_at": None,
                "created_at": "2026-03-08T10:00:00Z",
                "updated_at": "2026-03-08T10:00:00Z"
            }
        }


class ApprovalRequest(BaseModel):
    """Request to approve an exclusion"""

    user_id: str = Field(..., min_length=1)
    reason: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "analyst@company.com",
                "reason": "Verified against company records"
            }
        }


class RejectRequest(BaseModel):
    """Request to reject an exclusion"""

    user_id: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "analyst@company.com",
                "reason": "Not a direct business counterparty"
            }
        }


class OverrideRequest(BaseModel):
    """Request to override human decision with training feedback"""

    user_id: str = Field(..., min_length=1)
    new_status: str = Field(..., pattern="^(approved|rejected)$")
    override_reason: str = Field(..., min_length=1)
    training_feedback: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "supervisor@company.com",
                "new_status": "approved",
                "override_reason": "Agent confidence too conservative, verified externally",
                "training_feedback": "Increase entity matching confidence threshold"
            }
        }


class AuditLogResponse(BaseModel):
    """Single audit log entry"""

    id: UUID
    exclusion_id: UUID
    action: str
    agent_name: Optional[str] = None
    user_id: Optional[str] = None
    username: Optional[str] = None
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    confidence_score: Optional[float] = None
    audit_explanation: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    """Paginated list response"""

    items: List[ExclusionCandidateResponse]
    total: int
    skip: int
    limit: int

    class Config:
        json_schema_extra = {
            "example": {
                "items": [],
                "total": 42,
                "skip": 0,
                "limit": 100
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""

    status: str = "healthy"
    version: str
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Error response"""

    detail: str
    status_code: int
    timestamp: datetime
    trace_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "detail": "Exclusion not found",
                "status_code": 404,
                "timestamp": "2026-03-08T10:00:00Z"
            }
        }
