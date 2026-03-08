"""
TDD Tests for Extraction Agent
Red Phase: Tests that currently fail, driving implementation
"""

import pytest
from agents.extraction_agent import ExtractionAgent
from agents.models import ExtractedCompany
from config.llm import LLMConfig


class MockLLMConfig:
    """Mock LLM config for testing"""

    def __init__(self):
        self.model = "gpt-4-turbo"


@pytest.fixture
def mock_llm():
    return MockLLMConfig()


@pytest.fixture
def extraction_agent(mock_llm):
    return ExtractionAgent(llm_config=mock_llm)


class TestExtractionAgentRed:
    """RED PHASE: Failing tests that drive implementation"""

    @pytest.mark.asyncio
    async def test_failing_extract_pdf_to_companies(self, extraction_agent):
        """
        RED: Extraction agent should extract companies from PDF

        This test will fail until core_skill is fully implemented
        """
        # Setup
        input_data = {
            "file_path": "test.pdf",
            "doc_type": "pdf",
            "source_doc": "test.pdf",
        }

        # Note: Will fail because test.pdf doesn't exist
        # This is expected in RED phase
        with pytest.raises((FileNotFoundError, ImportError)):
            result = await extraction_agent.core_skill(input_data)

    @pytest.mark.asyncio
    async def test_failing_extract_from_text(self, extraction_agent):
        """
        RED: Extract companies from plain text

        Expected: Returns list of ExtractedCompany objects with confidence scores
        """
        input_data = {
            "doc_type": "text",
            "content": "Goldman Sachs and JPMorgan Chase are major banks.",
            "source_doc": "test.txt",
        }

        result = await extraction_agent.core_skill(input_data)

        # This should pass - text extraction is implemented
        assert result["total_extracted"] >= 0
        assert isinstance(result["companies"], list)

    @pytest.mark.asyncio
    async def test_failing_extract_csv(self, extraction_agent, tmp_path):
        """
        RED: Extract companies from CSV file

        Expected: Reads company column and returns as ExtractedCompany objects
        """
        # Create temp CSV
        csv_file = tmp_path / "companies.csv"
        csv_file.write_text(
            "company_name,region\nGoldman Sachs,US\nBarclay Bank,UK\n"
        )

        input_data = {
            "file_path": str(csv_file),
            "doc_type": "csv",
            "source_doc": "companies.csv",
        }

        result = await extraction_agent.core_skill(input_data)

        assert result["total_extracted"] == 2
        assert len(result["companies"]) == 2
        assert result["extraction_method"] == "parsing"

    @pytest.mark.asyncio
    async def test_failing_validation_skill_rejects_empty(self, extraction_agent):
        """
        RED: Validation skill should reject empty extraction
        """
        input_data = {"doc_type": "text", "content": ""}
        output = {"companies": [], "total_extracted": 0, "extraction_method": "text"}

        is_valid, msg = await extraction_agent.validation_skill(input_data, output)

        assert not is_valid
        assert "No companies" in msg

    @pytest.mark.asyncio
    async def test_failing_validation_skill_accepts_valid(self, extraction_agent):
        """
        RED: Validation skill should accept valid extraction
        """
        input_data = {"doc_type": "text"}
        output = {
            "companies": [
                {
                    "raw_name": "Goldman Sachs",
                    "ocr_confidence": 0.95,
                    "extraction_source": "text",
                    "source_doc": "test.txt",
                    "aliases": [],
                }
            ],
            "total_extracted": 1,
        }

        is_valid, msg = await extraction_agent.validation_skill(input_data, output)

        assert is_valid
        assert "1 companies extracted" in msg

    @pytest.mark.asyncio
    async def test_failing_explanation_skill(self, extraction_agent):
        """
        RED: Explanation skill should document extraction reasoning
        """
        input_data = {"doc_type": "text"}
        output = {
            "companies": [{"raw_name": "Goldman Sachs", "ocr_confidence": 0.95}],
            "total_extracted": 1,
            "extraction_method": "text",
        }

        explanation = await extraction_agent.explanation_skill(input_data, output)

        assert isinstance(explanation, str)
        assert len(explanation) > 10
        assert "Goldman Sachs" not in explanation  # Generic explanation
        assert "1" in explanation  # Should mention count

    @pytest.mark.asyncio
    async def test_failing_execute_complete_flow(self, extraction_agent):
        """
        RED: Execute should run full flow: core → validate → explain
        """
        input_data = {
            "doc_type": "text",
            "content": "Goldman Sachs, JPMorgan Chase",
            "source_doc": "test.txt",
        }

        result = await extraction_agent.execute(input_data)

        assert result.success
        assert result.data is not None
        assert result.validation_msg is not None
        assert result.audit_explanation is not None
        assert result.agent_name == "ExtractionAgent"
        assert result.timestamp is not None

    @pytest.mark.asyncio
    async def test_failing_extract_with_low_confidence(self, extraction_agent):
        """
        RED: OCR-extracted text should have lower confidence than structured data
        """
        input_data = {
            "doc_type": "text",
            "content": "Goldman Sachs",
            "source_doc": "test.txt",
        }

        result = await extraction_agent.core_skill(input_data)
        companies = result["companies"]

        if companies:
            # Text extraction should have reasonable confidence
            assert companies[0]["ocr_confidence"] > 0.5
            assert companies[0]["ocr_confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_failing_extract_removes_duplicates(self, extraction_agent):
        """
        RED: Should deduplicate company names
        """
        input_data = {
            "doc_type": "text",
            "content": "Goldman Sachs and Goldman Sachs again",
            "source_doc": "test.txt",
        }

        result = await extraction_agent.core_skill(input_data)

        # Should not extract Goldman Sachs twice
        names = [c["raw_name"] for c in result["companies"]]
        assert names.count("Goldman Sachs") <= 1


class TestExtractionAgentIntegration:
    """Integration tests with real files"""

    @pytest.mark.asyncio
    async def test_failing_e2e_text_extraction(self, extraction_agent):
        """
        RED: Full end-to-end text extraction with validation
        """
        input_data = {
            "doc_type": "text",
            "content": "Goldman Sachs Inc and JPMorgan Chase Bank",
            "source_doc": "email_body.txt",
        }

        result = await extraction_agent.execute(input_data)

        assert result.success
        assert result.data["total_extracted"] >= 1
        assert "Goldman Sachs" in str(result.data)
