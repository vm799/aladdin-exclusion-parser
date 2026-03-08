"""
Data Models for Agent Pipeline
Using Pydantic for validation and serialization
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from config.constants import DocType, ExclusionStatus, MatchType, ProcessingStatus


class ExtractedCompany(BaseModel):
    """Company extracted from document"""

    raw_name: str = Field(..., description="Raw company name as extracted")
    aliases: List[str] = Field(default_factory=list, max_length=50, description="Alternative names/abbreviations")
    ocr_confidence: float = Field(..., ge=0.0, le=1.0, description="OCR confidence 0.0-1.0")
    extraction_source: str = Field(default="", description="Where extracted (e.g., 'pdf_page_1')")
    source_doc: str = Field(default="", description="Source document filename")


class NormalizedCompany(BaseModel):
    """Normalized company name with metadata"""

    canonical_name: str = Field(..., description="Standardized company name")
    extracted_from: ExtractedCompany = Field(..., description="Original extraction")
    normalization_confidence: float = Field(..., ge=0.0, le=1.0, description="Entity resolution confidence 0.0-1.0")
    normalization_notes: str = Field(default="", description="Explanation of normalization")
    entity_type: Optional[str] = Field(default=None, description="Company, Fund, Bank, etc")


class AladdinMatch(BaseModel):
    """Match result from Aladdin API"""

    aladdin_id: Optional[str] = Field(default=None, description="Aladdin entity ID")
    isin: Optional[str] = Field(default=None, description="ISIN identifier")
    entity_name: Optional[str] = Field(default=None, description="Aladdin entity name")
    match_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Match confidence 0.0-1.0")
    match_type: MatchType = Field(
        default=MatchType.MANUAL_REQUIRED,
        description="Match type classification",
    )
    asset_classes: List[str] = Field(default_factory=list, max_length=20, description="Asset classes (Equities, etc)")
    alternative_matches: List[Dict[str, Any]] = Field(
        default_factory=list, max_items=10, description="Other possible matches"
    )
    api_response_time_ms: Optional[float] = Field(default=None, ge=0.0)


class ConfidenceScore(BaseModel):
    """Aggregated confidence score from all agents"""

    overall_confidence: float = Field(..., ge=0.0, le=1.0, description="Final confidence 0.0-1.0")
    ocr_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Extraction confidence")
    entity_resolution_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Entity normalization confidence")
    aladdin_match_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Aladdin API match confidence")
    requires_human_review: bool = Field(
        default=False, description="Flag for human review threshold"
    )
    review_reason: str = Field(default="", description="Why manual review is needed")
    confidence_breakdown: Dict[str, float] = Field(
        default_factory=dict, description="Detailed score components"
    )


class ExclusionCandidate(BaseModel):
    """Complete exclusion candidate ready for review"""

    id: str = Field(..., description="Unique ID")
    source_doc: str = Field(..., description="Source document")
    company_name: str = Field(..., description="Canonical company name")
    extracted_company: ExtractedCompany
    normalized_company: NormalizedCompany
    aladdin_match: AladdinMatch
    confidence_score: ConfidenceScore
    status: ExclusionStatus = Field(
        default=ExclusionStatus.PENDING, description="Processing status"
    )
    agent_version: str = Field(default="v1", description="Agent version that processed this")
    processing_time_ms: float = Field(default=0.0, ge=0.0)


class AuditLogEntry(BaseModel):
    """Immutable audit log entry"""

    timestamp: str = Field(..., description="ISO timestamp")
    agent_name: str = Field(..., description="Which agent made decision")
    action: str = Field(..., description="extract | resolve | match | aggregate | approve | override | sync")
    input_data: Dict[str, Any] = Field(..., description="What was the input")
    output_data: Dict[str, Any] = Field(..., description="What was the output")
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    user_id: Optional[str] = Field(default=None, description="If human-reviewed")
    audit_explanation: str = Field(..., description="Why this decision was made")


class ProcessingJob(BaseModel):
    """Background processing job"""

    job_id: str = Field(..., description="Unique job ID")
    status: ProcessingStatus = Field(default=ProcessingStatus.QUEUED, description="Job processing status")
    source_doc: str = Field(..., description="Document being processed")
    doc_type: DocType = Field(..., description="Document type")
    exclusions_found: int = Field(default=0, ge=0)
    error_message: Optional[str] = Field(default=None)
    progress_percent: int = Field(default=0, ge=0, le=100)
