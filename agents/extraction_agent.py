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
import json
import logging
import re
from typing import Any, Dict, List, Optional

from agents.base_agent import SkillAgent
from agents.models import ExtractedCompany

logger = logging.getLogger(__name__)


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
                "doc_type": "pdf|email|csv|xls|text",
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
        doc_type = input_data.get("doc_type", "").lower()
        source_doc = input_data.get("source_doc", file_path)

        self.logger.info(f"Extracting from {doc_type}: {file_path}")

        # Route to appropriate extraction method
        if doc_type == "pdf":
            return await self._extract_from_pdf(file_path, source_doc)
        elif doc_type == "email":
            return await self._extract_from_email(file_path, input_data.get("content", ""))
        elif doc_type == "csv":
            return await self._extract_from_csv(file_path, source_doc)
        elif doc_type == "xls" or doc_type == "xlsx":
            return await self._extract_from_xls(file_path, source_doc)
        elif doc_type == "text" or doc_type == "txt":
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
            all_text = ""

            for page_num, image in enumerate(images):
                # OCR each page
                text = self.pytesseract.image_to_string(image)
                all_text += f"\n--- PAGE {page_num + 1} ---\n{text}"

                # Extract companies from page
                page_companies = await self._extract_company_names(text, page_num + 1, source_doc)
                companies.extend(page_companies)

            return {
                "companies": [c.model_dump() for c in companies],
                "total_extracted": len(companies),
                "extraction_method": "ocr",
                "raw_text_sample": all_text[:500],
                "pages_processed": len(images),
            }

        except Exception as e:
            self.logger.error(f"PDF extraction failed: {str(e)}")
            raise

    async def _extract_from_email(self, file_path: str, content: str) -> Dict[str, Any]:
        """Extract companies from email body/attachments"""
        # TODO: Implement email parsing with eml library
        # For now, treat as text extraction
        return await self._extract_from_text(content, file_path)

    async def _extract_from_csv(self, file_path: str, source_doc: str) -> Dict[str, Any]:
        """Extract companies from CSV file"""
        import csv

        companies = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Look for company_name or similar columns
                    company_name = (
                        row.get("company_name")
                        or row.get("company")
                        or row.get("name")
                        or row.get("entity")
                    )

                    if company_name and company_name.strip():
                        company = ExtractedCompany(
                            raw_name=company_name.strip(),
                            ocr_confidence=0.95,  # CSV data is structured
                            extraction_source="csv_row",
                            source_doc=source_doc,
                        )
                        companies.append(company)

            return {
                "companies": [c.model_dump() for c in companies],
                "total_extracted": len(companies),
                "extraction_method": "parsing",
            }

        except Exception as e:
            self.logger.error(f"CSV extraction failed: {str(e)}")
            raise

    async def _extract_from_xls(self, file_path: str, source_doc: str) -> Dict[str, Any]:
        """Extract companies from XLS/XLSX file"""
        # TODO: Implement with openpyxl or pandas
        # For now, return empty list
        self.logger.warning("XLS extraction not yet implemented")
        return {
            "companies": [],
            "total_extracted": 0,
            "extraction_method": "parsing",
            "error": "Not yet implemented",
        }

    async def _extract_from_text(self, content: str, source_doc: str) -> Dict[str, Any]:
        """Extract companies from plain text"""
        companies = await self._extract_company_names(content, 1, source_doc)

        return {
            "companies": [c.model_dump() for c in companies],
            "total_extracted": len(companies),
            "extraction_method": "text",
            "raw_text_sample": content[:500],
        }

    async def _extract_company_names(
        self, text: str, page_num: int = 1, source_doc: str = ""
    ) -> List[ExtractedCompany]:
        """
        Extract company names from text

        Uses simple patterns and NER-like approach
        TODO: Could use spaCy or Claude for advanced entity extraction
        """
        companies = []

        # Simple patterns for common financial entities
        patterns = [
            r"(?i)\b([A-Z][A-Za-z\s&\.\-]+(?:Inc|Corp|Ltd|LLC|Bank|Fund|Group|Holdings))\b",
            r"(?i)\b([A-Z]{2,})\s+(?:Bank|Capital|Fund|Group|Holdings)\b",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                name = match.group(1).strip()
                if len(name) > 2 and name.upper() != name:  # Not all caps
                    company = ExtractedCompany(
                        raw_name=name,
                        ocr_confidence=0.75,  # Regex-based extraction
                        extraction_source=f"text_page_{page_num}",
                        source_doc=source_doc,
                    )
                    companies.append(company)

        # Remove duplicates while preserving order
        seen = set()
        unique_companies = []
        for company in companies:
            if company.raw_name not in seen:
                seen.add(company.raw_name)
                unique_companies.append(company)

        return unique_companies

    async def validation_skill(
        self, input_data: Dict[str, Any], output: Dict[str, Any]
    ) -> tuple:
        """
        Validate extraction output

        Checks:
        - At least 1 company extracted
        - Confidence scores are valid (0-1)
        - No empty names
        """
        companies = output.get("companies", [])

        if not companies:
            return (False, "No companies extracted from document")

        for company in companies:
            if not company.get("raw_name") or not company["raw_name"].strip():
                return (False, "Found empty company name in extraction")

            conf = company.get("ocr_confidence", 0)
            if not (0 <= conf <= 1):
                return (False, f"Invalid confidence score: {conf}")

        return (True, f"Extraction validated: {len(companies)} companies extracted")

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
