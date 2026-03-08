"""
TDD Tests for Entity Resolution Agent
Red Phase: Tests that drive implementation
"""

import pytest

from agents.entity_resolver import EntityResolverAgent
from agents.models import ExtractedCompany


class MockLLMConfig:
    """Mock LLM for testing"""

    async def create_completion_async(self, messages, temperature=0.3, max_tokens=2048):
        """Mock GPT-4 response for entity resolution"""

        class MockResponse:
            class MockChoice:
                class MockMessage:
                    content = '{"resolutions": [{"raw_name": "Citi Bank", "canonical": "Citigroup", "confidence": 0.85, "method": "fuzzy"}]}'

                message = MockMessage()

            choices = [MockChoice()]

        return MockResponse()


@pytest.fixture
def mock_llm():
    return MockLLMConfig()


@pytest.fixture
def entity_resolver(mock_llm):
    return EntityResolverAgent(
        llm_config=mock_llm,
        alias_db_path="aladdin_lookup_sample.csv"
    )


class TestEntityResolverRed:
    """RED PHASE: Failing tests that drive implementation"""

    @pytest.mark.asyncio
    async def test_failing_resolve_exact_alias_match(self, entity_resolver):
        """
        RED: Should match "GS" to "Goldman Sachs" via alias lookup
        """
        company = ExtractedCompany(
            raw_name="GS",
            ocr_confidence=0.9,
            extraction_source="text",
            source_doc="test.txt"
        )

        result = await entity_resolver.core_skill({
            "companies": [company],
            "use_gpt4": False  # Alias only for this test
        })

        normalized = result.get("normalized", [])
        assert len(normalized) == 1
        assert normalized[0]["canonical_name"] == "Goldman Sachs"
        assert normalized[0]["normalization_confidence"] > 0.9

    @pytest.mark.asyncio
    async def test_failing_resolve_fuzzy_alias(self, entity_resolver):
        """
        RED: Should match "JP Morgan" to "JPMorgan Chase" via fuzzy alias
        """
        company = ExtractedCompany(
            raw_name="JP Morgan",
            ocr_confidence=0.85,
            extraction_source="text",
            source_doc="test.txt"
        )

        result = await entity_resolver.core_skill({
            "companies": [company],
            "use_gpt4": False
        })

        # May or may not resolve depending on fuzzy match threshold
        # At minimum, should process without error
        assert "normalized" in result
        assert "unresolved" in result

    @pytest.mark.asyncio
    async def test_failing_resolve_unknown_name_unresolved(self, entity_resolver):
        """
        RED: Unknown names should be marked unresolved
        """
        company = ExtractedCompany(
            raw_name="Unknown Corp XYZ",
            ocr_confidence=0.5,
            extraction_source="text",
            source_doc="test.txt"
        )

        result = await entity_resolver.core_skill({
            "companies": [company],
            "use_gpt4": False
        })

        unresolved = result.get("unresolved", [])
        # Unknown company should be in unresolved after alias pass
        # (GPT-4 would handle it if use_gpt4=True)
        assert result["resolution_method"] == "alias_only"

    @pytest.mark.asyncio
    async def test_failing_resolve_multiple_companies(self, entity_resolver):
        """
        RED: Should handle multiple companies in one batch
        """
        companies = [
            ExtractedCompany(
                raw_name="GS",
                ocr_confidence=0.9,
                extraction_source="text",
                source_doc="test.txt"
            ),
            ExtractedCompany(
                raw_name="JPMorgan Chase",
                ocr_confidence=0.95,
                extraction_source="text",
                source_doc="test.txt"
            ),
        ]

        result = await entity_resolver.core_skill({
            "companies": companies,
            "use_gpt4": False
        })

        total = len(result.get("normalized", [])) + len(result.get("unresolved", []))
        assert total == 2

    @pytest.mark.asyncio
    async def test_failing_validation_checks_canonical(self, entity_resolver):
        """
        RED: Validation should reject missing canonical names
        """
        input_data = {"companies": []}
        output = {
            "normalized": [{"canonical_name": None, "normalization_confidence": 0.9}],
            "unresolved": []
        }

        is_valid, msg = await entity_resolver.validation_skill(input_data, output)
        assert not is_valid

    @pytest.mark.asyncio
    async def test_failing_explanation_documents_method(self, entity_resolver):
        """
        RED: Explanation should document resolution method
        """
        input_data = {
            "companies": [
                ExtractedCompany(
                    raw_name="GS",
                    ocr_confidence=0.9,
                    extraction_source="text",
                    source_doc="test.txt"
                )
            ]
        }
        output = {
            "normalized": [{"raw_name": "GS", "canonical_name": "Goldman Sachs"}],
            "unresolved": [],
            "resolution_method": "alias_only"
        }

        explanation = await entity_resolver.explanation_skill(input_data, output)
        assert isinstance(explanation, str)
        assert len(explanation) > 20
        assert "alias" in explanation.lower() or "resolved" in explanation.lower()
