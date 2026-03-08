"""
Constants and Enums for Aladdin Exclusion Parser
Centralizes stringly-typed values and magic numbers
"""

from enum import Enum


class DocType(str, Enum):
    """Document type enumeration"""

    PDF = "pdf"
    EMAIL = "email"
    CSV = "csv"
    XLS = "xls"
    XLSX = "xlsx"
    TEXT = "text"
    TXT = "txt"


class MatchType(str, Enum):
    """Company match type enumeration"""

    EXACT = "exact"
    FUZZY = "fuzzy"
    PARTIAL = "partial"
    MANUAL_REQUIRED = "manual_required"


class ExclusionStatus(str, Enum):
    """Exclusion processing status"""

    PENDING = "pending"
    AUTO_APPROVED = "auto_approved"
    APPROVED = "approved"
    REJECTED = "rejected"
    SYNCED = "synced"


class ProcessingStatus(str, Enum):
    """Background job processing status"""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ConfidenceThresholds:
    """Confidence score constants"""

    # Extraction confidence
    CSV_STRUCTURED = 0.95  # CSV data is structured, high confidence
    OCR_DEFAULT = 0.75  # OCR-extracted text, moderate confidence
    REGEX_EXTRACTION = 0.75  # Regex-based extraction
    TEXT_DEFAULT = 0.80  # Plain text extraction

    # Entity resolution confidence
    ENTITY_EXACT_MATCH = 0.99  # Exact company name match
    ENTITY_FUZZY_HIGH = 0.85  # High fuzzy match score
    ENTITY_FUZZY_MEDIUM = 0.70  # Medium fuzzy match

    # Aladdin API match confidence
    ALADDIN_EXACT = 1.0  # Exact ISIN match
    ALADDIN_FUZZY = 0.85  # Fuzzy entity name match
    ALADDIN_PARTIAL = 0.60  # Partial match

    # Aggregated thresholds
    AUTO_APPROVAL_THRESHOLD = 0.90  # Auto-approve if confidence >= 90%
    MANUAL_REVIEW_THRESHOLD = 0.60  # Flag for manual review if < 60%

    # Confidence scoring weights (must sum to 1.0)
    WEIGHT_OCR = 0.20  # Weight for OCR/extraction confidence
    WEIGHT_ENTITY = 0.30  # Weight for entity resolution confidence
    WEIGHT_ALADDIN = 0.50  # Weight for Aladdin match confidence


class CompanyColumnNames:
    """Common column name variations for company data"""

    STANDARD = [
        "company_name",
        "company",
        "name",
        "entity",
        "entity_name",
        "fund_name",
        "issuer",
        "counterparty",
    ]


class ConstitutionalPrinciples:
    """PAUL Framework constitutional principles"""

    HELPFUL = "Actively assist with exclusion parsing; provide clear explanations"
    HARMLESS = "Never corrupt data; flag uncertainties; require human approval before Aladdin push"
    HONEST = "Explain confidence scores transparently; audit all decisions; admit limitations"


# Sample data for OCR/text extraction
TEXT_TRUNCATION_SIZE = 500  # Characters to include in raw_text_sample
DEFAULT_TIMEOUT = 30  # seconds
