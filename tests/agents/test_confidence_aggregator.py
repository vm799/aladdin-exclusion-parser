"""
TDD Tests for Confidence Aggregator Agent
Red Phase: Tests that drive implementation
"""

import pytest

from agents.confidence_aggregator import ConfidenceAggregatorAgent


class MockLLMConfig:
    """Mock LLM for testing"""
    pass


@pytest.fixture
def mock_llm():
    return MockLLMConfig()


@pytest.fixture
def confidence_aggregator(mock_llm):
    return ConfidenceAggregatorAgent(llm_config=mock_llm)


class TestConfidenceAggregatorRed:
    """RED PHASE: Failing tests that drive implementation"""

    @pytest.mark.asyncio
    async def test_failing_high_confidence_auto_approved(self, confidence_aggregator):
        """
        RED: All high scores should auto-approve (confidence >= 0.90)
        """
        result = await confidence_aggregator.core_skill({
            "ocr_confidence": 0.95,
            "entity_confidence": 0.95,
            "aladdin_confidence": 0.95,
            "company_name": "Goldman Sachs",
            "aladdin_match": True
        })

        assert result["overall_confidence"] > 0.90
        assert not result["requires_human_review"]
        assert result["auto_approved"] is True

    @pytest.mark.asyncio
    async def test_failing_low_confidence_requires_review(self, confidence_aggregator):
        """
        RED: Low overall confidence should require review
        """
        result = await confidence_aggregator.core_skill({
            "ocr_confidence": 0.5,
            "entity_confidence": 0.4,
            "aladdin_confidence": 0.0,
            "company_name": "Unknown Corp",
            "aladdin_match": False
        })

        assert result["overall_confidence"] < 0.70
        assert result["requires_human_review"] is True

    @pytest.mark.asyncio
    async def test_failing_weighted_calculation(self, confidence_aggregator):
        """
        RED: Confidence = (OCR * 0.20) + (Entity * 0.30) + (Aladdin * 0.50)
        """
        # Test case: OCR=1.0, Entity=0.0, Aladdin=0.0
        # Expected: (1.0 * 0.20) + (0.0 * 0.30) + (0.0 * 0.50) = 0.20
        result = await confidence_aggregator.core_skill({
            "ocr_confidence": 1.0,
            "entity_confidence": 0.0,
            "aladdin_confidence": 0.0,
            "company_name": "Test"
        })

        # Allow small rounding error
        assert abs(result["overall_confidence"] - 0.20) < 0.01

    @pytest.mark.asyncio
    async def test_failing_breakdown_sums_correctly(self, confidence_aggregator):
        """
        RED: Breakdown components should sum to overall confidence
        """
        result = await confidence_aggregator.core_skill({
            "ocr_confidence": 0.8,
            "entity_confidence": 0.7,
            "aladdin_confidence": 0.9,
            "company_name": "Test Company"
        })

        breakdown = result["confidence_breakdown"]
        total = (
            breakdown["ocr_contribution"] +
            breakdown["entity_contribution"] +
            breakdown["aladdin_contribution"]
        )

        assert abs(total - result["overall_confidence"]) < 0.01

    @pytest.mark.asyncio
    async def test_failing_validation_checks_scores(self, confidence_aggregator):
        """
        RED: Validation should reject invalid confidence scores
        """
        input_data = {}
        output = {
            "overall_confidence": 1.5,  # Invalid
            "ocr_confidence": 0.8,
            "entity_resolution_confidence": 0.7,
            "aladdin_match_confidence": 0.9,
            "confidence_breakdown": {}
        }

        is_valid, msg = await confidence_aggregator.validation_skill(input_data, output)
        assert not is_valid

    @pytest.mark.asyncio
    async def test_failing_explanation_documents_score(self, confidence_aggregator):
        """
        RED: Explanation should document why item needs review
        """
        input_data = {"company_name": "Test Corp"}
        output = {
            "overall_confidence": 0.5,
            "requires_human_review": True,
            "review_reason": "overall confidence 0.5 < 0.6"
        }

        explanation = await confidence_aggregator.explanation_skill(input_data, output)
        assert isinstance(explanation, str)
        assert "review" in explanation.lower()
        assert "0.5" in explanation or "review" in explanation

    @pytest.mark.asyncio
    async def test_failing_no_aladdin_match_low_confidence(self, confidence_aggregator):
        """
        RED: No Aladdin match should result in low confidence
        """
        result = await confidence_aggregator.core_skill({
            "ocr_confidence": 0.95,
            "entity_confidence": 0.95,
            "aladdin_confidence": 0.0,  # No match
            "company_name": "Unknown Company",
            "aladdin_match": False
        })

        # (0.95 * 0.20) + (0.95 * 0.30) + (0.0 * 0.50) = 0.19 + 0.285 = 0.475
        assert result["overall_confidence"] < 0.50
        assert result["requires_human_review"] is True
