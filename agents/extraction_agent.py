"""
Extraction Agent - PAUL Skill-Based Agent for Document Parsing

Responsibilities:
- OCR extraction from PDFs and images
- Layout analysis for structured data
- Email attachment parsing
- CSV/XLS reading
- Confidence scoring for extracted text
"""

import asyncio
import csv
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from agents.base_agent import SkillAgent
from agents.models import ExtractedCompany
from config.constants import (
    CompanyColumnNames,
    ConfidenceThresholds,
    DocType,
    TEXT_TRUNCATION_SIZE,
)

logger = logging.getLogger(__name__)

# Pre-compile regex patterns to avoid recompilation overhead
_COMPANY_PATTERNS = [
    re.compile(r"(?i)\b([A-Z][A-Za-z\s&\.\-]+(?:Inc|Corp|Ltd|LLC|Bank|Fund|Group|Holdings))\b"),
    re.compile(r"(?i)\b([A-Z]{2,})\s+(?:Bank|Capital|Fund|Group|Holdings)\b"),
]


class ExtractionAgent(SkillAgent):
    """
    PAUL Skill-based agent for extracting companies from documents

    Implements:
    - Core Skill: OCR and text extraction
    - Validation Skill: Check extraction quality
    - Explanation Skill: Document reasoning about extraction
    - Fallback Skill: Return low-confidence extraction
    """

    def __init__(self, llm_config: "LLMConfig", name: str = "ExtractionAgent"):
        """Initialize extraction agent"""
        super().__init__(llm_config, name)

        # Import OCR tools lazily to avoid hard dependencies
        self.pytesseract = None
        self.pdf2image = None
        self._init_ocr_tools()

    def _init_ocr_tools(self):
        """Initialize OCR tools if available"""
        try:
            import pytesseract
            self.pytesseract = pytesseract
            self.logger.info("pytesseract initialized for OCR")
        except ImportError:
            self.logger.warning("pytesseract not available - OCR will be limited")

        try:
            import pdf2image
            self.pdf2image = pdf2image
            self.logger.info("pdf2image initialized for PDF processing")
        except ImportError:
            self.logger.warning("pdf2image not available - PDF processing limited")

    async def core_skill(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract companies from document

        Input:
            {
                "file_path": "/path/to/document.pdf",
                "doc_type": DocType enum value,
                "content": optional raw content,
                "source_doc": "filename.pdf"
            }

        Output:
            {
                "companies": [ExtractedCompany...],
                "total_extracted": int,
                "extraction_method": "ocr|text|parsing",
                "raw_text_sample": str
            }
        """
        file_path = input_data.get("file_path", "")
        doc_type = input_data.get("doc_type")

        if isinstance(doc_type, str):
            doc_type = doc_type.lower()

        source_doc = input_data.get("source_doc", file_path)

        self.logger.info(f"Extracting from {doc_type}: {file_path}")

        # Route to appropriate extraction method based on doc type
        if doc_type in (DocType.PDF, "pdf"):
            return await self._extract_from_pdf(file_path, source_doc)
        elif doc_type in (DocType.EMAIL, "email"):
            return await self._extract_from_email(file_path, input_data.get("content", ""))
        elif doc_type in (DocType.CSV, "csv"):
            return await self._extract_from_csv(file_path, source_doc)
        elif doc_type in (DocType.XLS, DocType.XLSX, "xls", "xlsx"):
            return await self._extract_from_xls(file_path, source_doc)
        elif doc_type in (DocType.TEXT, DocType.TXT, "text", "txt"):
            return await self._extract_from_text(input_data.get("content", ""), source_doc)
        else:
            raise ValueError(f"Unsupported doc_type: {doc_type}")

    async def _extract_from_pdf(self, file_path: str, source_doc: str) -> Dict[str, Any]:
        """Extract companies from PDF via OCR"""
        companies = []

        try:
            if not self.pdf2image or not self.pytesseract:
                raise ImportError("pdf2image and pytesseract required for PDF extraction")

            # Convert PDF pages to images
            from pdf2image import convert_from_path

            images = convert_from_path(file_path)
            text_lines = []  # Use list for O(1) append instead of string concatenation

            for page_num, image in enumerate(images):
                # OCR each page
                text = self.pytesseract.image_to_string(image)
                text_lines.append(f"\n--- PAGE {page_num + 1} ---\n{text}")

                # Extract companies from page
                page_companies = await self._extract_company_names(text, page_num + 1, source_doc)
                companies.extend(page_companies)

            all_text = "".join(text_lines)  # Join once at the end

            return self._build_extraction_result(
                companies,
                extraction_method="ocr",
                raw_text_sample=all_text[:TEXT_TRUNCATION_SIZE],
                pages_processed=len(images),
            )

        except Exception as e:
            self.logger.error(f"PDF extraction failed: {str(e)}")
            raise

    def _build_extraction_result(
        self,
        companies: List[ExtractedCompany],
        extraction_method: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Helper to standardize extraction result format

        Args:
            companies: List of extracted companies
            extraction_method: OCR, text, parsing, etc
            **kwargs: Additional fields (raw_text_sample, pages_processed, etc)

        Returns:
            Standardized extraction result dictionary
        """
        return {
            "companies": [c.model_dump() for c in companies],
            "total_extracted": len(companies),
            "extraction_method": extraction_method,
            **kwargs,
        }

    async def _extract_from_email(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Extract companies from email body/attachments

        TODO: Implement email parsing with email library for:
        - Extract MIME parts
        - Parse attachments (PDF, XLS, etc)
        - Process email headers and body separately
        """
        # For MVP: treat as text extraction
        return await self._extract_from_text(content, file_path)

    async def _extract_from_csv(self, file_path: str, source_doc: str) -> Dict[str, Any]:
        """Extract companies from CSV file"""
        companies = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_num, row in enumerate(reader, start=1):
                    # Look for company_name or similar columns
                    company_name = next(
                        (row.get(col) for col in CompanyColumnNames.STANDARD if row.get(col)),
                        None,
                    )

                    if company_name and company_name.strip():
                        company = ExtractedCompany(
                            raw_name=company_name.strip(),
                            ocr_confidence=ConfidenceThresholds.CSV_STRUCTURED,
                            extraction_source=f"csv_row_{row_num}",
                            source_doc=source_doc,
                        )
                        companies.append(company)

            return self._build_extraction_result(
                companies,
                extraction_method="parsing",
            )

        except Exception as e:
            self.logger.error(f"CSV extraction failed: {str(e)}")
            raise

    async def _extract_from_xls(self, file_path: str, source_doc: str) -> Dict[str, Any]:
        """
        Extract companies from XLS/XLSX file

        TODO: Implement with openpyxl or pandas:
        - Read structured cells
        - Map to company_name or similar columns
        - Return as ExtractedCompany objects
        """
        self.logger.warning("XLS extraction not yet implemented")
        raise NotImplementedError(
            "XLS extraction not yet implemented. "
            "Install openpyxl for XLS support."
        )

    async def _extract_from_text(self, content: str, source_doc: str) -> Dict[str, Any]:
        """Extract companies from plain text"""
        companies = await self._extract_company_names(content, 1, source_doc)

        return self._build_extraction_result(
            companies,
            extraction_method="text",
            raw_text_sample=content[:TEXT_TRUNCATION_SIZE],
        )

    async def _extract_company_names(
        self, text: str, page_num: int = 1, source_doc: str = ""
    ) -> List[ExtractedCompany]:
        """
        Extract company names from text using pre-compiled regex patterns

        Uses simple patterns for common financial entities.
        TODO: Could use Claude for advanced entity extraction with semantic understanding
        """
        # Use pre-compiled patterns to avoid recompilation overhead
        companies = []
        seen = {}  # Dict to deduplicate while preserving first occurrence

        for pattern in _COMPANY_PATTERNS:
            for match in pattern.finditer(text):
                name = match.group(1).strip()
                # Filter: must be > 2 chars and not all caps
                if len(name) > 2 and name.upper() != name:
                    if name not in seen:  # Deduplicate efficiently
                        company = ExtractedCompany(
                            raw_name=name,
                            ocr_confidence=ConfidenceThresholds.REGEX_EXTRACTION,
                            extraction_source=f"text_page_{page_num}",
                            source_doc=source_doc,
                        )
                        companies.append(company)
                        seen[name] = True

        return companies

    async def validation_skill(
        self, input_data: Dict[str, Any], output: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Validate extraction output

        Checks:
        - At least 1 company extracted
        - Confidence scores are valid (0-1)
        - No empty names
        - Confidence scores match field constraints

        Returns:
            (is_valid, validation_message)
        """
        companies = output.get("companies", [])

        if not companies:
            return (False, "No companies extracted from document")

        # Single pass validation of all companies
        for i, company in enumerate(companies):
            raw_name = company.get("raw_name", "").strip()
            if not raw_name:
                return (False, f"Company {i} has empty name")

            conf = company.get("ocr_confidence", 0)
            if not isinstance(conf, (int, float)) or not (0 <= conf <= 1):
                return (False, f"Company {i} has invalid confidence: {conf}")

        return (True, f"Validated: {len(companies)} companies extracted")

    async def explanation_skill(
        self, input_data: Dict[str, Any], output: Dict[str, Any]
    ) -> str:
        """
        Generate explanation of extraction decision

        Uses LLM to create human-readable summary
        """
        doc_type = input_data.get("doc_type", "unknown")
        num_companies = len(output.get("companies", []))
        extraction_method = output.get("extraction_method", "unknown")

        explanation = (
            f"Extracted {num_companies} companies from {doc_type} document "
            f"using {extraction_method} method. "
            f"Confidence scores reflect extraction quality - higher scores indicate "
            f"clearer source text."
        )

        return explanation
