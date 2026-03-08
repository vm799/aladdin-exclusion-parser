"""
Data Models for Agent Pipeline
Using Pydantic for validation and serialization
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ExtractedCompany(BaseModel):
    """Company extracted from document"""

    raw_name: str = Field(..., description="Raw company name as extracted")
    aliases: List[str] = Field(default_factory=list, description="Alternative names/abbreviations")
    ocr_confidence: float = Field(..., description="OCR confidence 0.0-1.0")
    extraction_source: str = Field(default="", description="Where extracted (e.g., 'pdf_page_1')")
    source_doc: str = Field(default="", description="Source document filename")


class NormalizedCompany(BaseModel):
    """Normalized company name with metadata"""

    canonical_name: str = Field(..., description="Standardized company name")
    extracted_from: ExtractedCompany = Field(..., description="Original extraction")
    normalization_confidence: float = Field(..., description="Entity resolution confidence 0.0-1.0")
    normalization_notes: str = Field(default="", description="Explanation of normalization")
    entity_type: Optional[str] = Field(default=None, description="Company, Fund, Bank, etc")


class AladdinMatch(BaseModel):
    """Match result from Aladdin API"""

    aladdin_id: Optional[str] = Field(default=None, description="Aladdin entity ID")
    isin: Optional[str] = Field(default=None, description="ISIN identifier")
    entity_name: Optional[str] = Field(default=None, description="Aladdin entity name")
    match_confidence: float = Field(default=0.0, description="Match confidence 0.0-1.0")
    match_type: str = Field(
        default="manual_required",
        description="exact | fuzzy | partial | manual_required",
    )
    asset_classes: List[str] = Field(default_factory=list, description="Asset classes (Equities, etc)")
    alternative_matches: List[Dict] = Field(
        default_factory=list, description="Other possible matches"
    )
    api_response_time_ms: Optional[float] = Field(default=None)


class ConfidenceScore(BaseModel):
    """Aggregated confidence score from all agents"""

    overall_confidence: float = Field(..., description="Final confidence 0.0-1.0")
    ocr_confidence: float = Field(default=0.0, description="Extraction confidence")
    entity_resolution_confidence: float = Field(default=0.0, description="Entity normalization confidence")
    aladdin_match_confidence: float = Field(default=0.0, description="Aladdin API match confidence")
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
    status: str = Field(
        default="pending", description="pending | auto_approved | approved | rejected | synced"
    )
    agent_version: str = Field(default="v1", description="Agent version that processed this")
    processing_time_ms: float = Field(default=0.0)


class AuditLogEntry(BaseModel):
    """Immutable audit log entry"""

    timestamp: str = Field(..., description="ISO timestamp")
    agent_name: str = Field(..., description="Which agent made decision")
    action: str = Field(..., description="extract | resolve | match | aggregate | approve | override | sync")
    input_data: Dict = Field(..., description="What was the input")
    output_data: Dict = Field(..., description="What was the output")
    confidence_score: Optional[float] = Field(default=None)
    user_id: Optional[str] = Field(default=None, description="If human-reviewed")
    audit_explanation: str = Field(..., description="Why this decision was made")


class ProcessingJob(BaseModel):
    """Background processing job"""

    job_id: str = Field(..., description="Unique job ID")
    status: str = Field(default="queued", description="queued | processing | completed | failed")
    source_doc: str = Field(..., description="Document being processed")
    doc_type: str = Field(..., description="pdf | email | csv | xls")
    exclusions_found: int = Field(default=0)
    error_message: Optional[str] = Field(default=None)
    progress_percent: int = Field(default=0, ge=0, le=100)
