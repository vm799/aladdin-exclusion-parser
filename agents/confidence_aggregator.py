"""
Confidence Aggregator Agent - PAUL Skill-Based Agent for Multi-Source Scoring

Responsibilities:
- Combine confidence scores from extraction, entity resolution, and Aladdin matching
- Apply weighted scoring algorithm: OCR (20%) + Entity (30%) + Aladdin (50%)
- Flag items for auto-approval (>= 0.90) or manual review (< 0.60)
- Generate audit trail explaining score composition
"""

import logging
from typing import Any, Dict, Tuple

from agents.base_agent import SkillAgent
from agents.models import ConfidenceScore
from config.constants import ConfidenceThresholds

logger = logging.getLogger(__name__)


class ConfidenceAggregatorAgent(SkillAgent):
    """
    PAUL Skill-based agent for aggregating multi-source confidence scores

    Weighted Scoring Algorithm:
    - OCR confidence: 20% (quality of text extraction)
    - Entity resolution: 30% (quality of name normalization)
    - Aladdin match: 50% (quality of ID matching - most important)

    Overall Score:
        confidence = (ocr * 0.20) + (entity * 0.30) + (aladdin * 0.50)

    Thresholds:
    - >= 0.90: Auto-approved (high confidence, no review needed)
    - 0.60-0.89: Pending review (medium confidence, human judgment)
    - < 0.60: Requires manual review (low confidence or no match)

    Implements:
    - Core Skill: Calculate weighted scores, determine status
    - Validation Skill: Check score components are valid 0.0-1.0
    - Explanation Skill: Justify score breakdown and weights
    - Fallback Skill: Return all zeros on calculation error
    """

    # Scoring weights - configurable for different use cases
    WEIGHT_OCR = 0.20
    WEIGHT_ENTITY = 0.30
    WEIGHT_ALADDIN = 0.50

    def __init__(self, llm_config: "LLMConfig", name: str = "ConfidenceAggregatorAgent"):
        """Initialize confidence aggregator agent"""
        super().__init__(llm_config, name)

        # Verify weights sum to 1.0
        total_weight = self.WEIGHT_OCR + self.WEIGHT_ENTITY + self.WEIGHT_ALADDIN
        if abs(total_weight - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total_weight}")

    async def core_skill(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aggregate confidence scores from all sources

        Input:
            {
                "ocr_confidence": 0.0-1.0,
                "entity_confidence": 0.0-1.0,
                "aladdin_confidence": 0.0-1.0,
                "company_name": str,
                "aladdin_match": bool (optional)
            }

        Output:
            {
                "overall_confidence": 0.0-1.0,
                "ocr_confidence": 0.0-1.0,
                "entity_confidence": 0.0-1.0,
                "aladdin_confidence": 0.0-1.0,
                "requires_human_review": bool,
                "review_reason": str,
                "confidence_breakdown": {
                    "ocr_weight": 0.20,
                    "entity_weight": 0.30,
                    "aladdin_weight": 0.50,
                    "ocr_contribution": 0.20 * score,
                    "entity_contribution": 0.30 * score,
                    "aladdin_contribution": 0.50 * score
                }
            }
        """
        ocr = input_data.get("ocr_confidence", 0.0)
        entity = input_data.get("entity_confidence", 0.0)
        aladdin = input_data.get("aladdin_confidence", 0.0)
        company_name = input_data.get("company_name", "Unknown")
        aladdin_match = input_data.get("aladdin_match", aladdin > 0)

        # Calculate weighted overall confidence
        overall = (ocr * self.WEIGHT_OCR) + (
            entity * self.WEIGHT_ENTITY
        ) + (aladdin * self.WEIGHT_ALADDIN)

        # Determine if human review is required
        requires_review = overall < ConfidenceThresholds.AUTO_APPROVAL_THRESHOLD
        review_reason = self._determine_review_reason(
            overall, ocr, entity, aladdin, aladdin_match
        )

        # Build detailed breakdown
        breakdown = {
            "ocr_weight": self.WEIGHT_OCR,
            "entity_weight": self.WEIGHT_ENTITY,
            "aladdin_weight": self.WEIGHT_ALADDIN,
            "ocr_contribution": round(ocr * self.WEIGHT_OCR, 4),
            "entity_contribution": round(entity * self.WEIGHT_ENTITY, 4),
            "aladdin_contribution": round(aladdin * self.WEIGHT_ALADDIN, 4),
            "calculation": f"({ocr:.2f} * {self.WEIGHT_OCR}) + ({entity:.2f} * {self.WEIGHT_ENTITY}) + ({aladdin:.2f} * {self.WEIGHT_ALADDIN}) = {overall:.4f}",
        }

        self.logger.info(
            f"Confidence for '{company_name}': {overall:.2f} "
            f"(OCR: {ocr:.2f}, Entity: {entity:.2f}, Aladdin: {aladdin:.2f}) "
            f"→ {'auto-approve' if not requires_review else 'requires review'}"
        )

        return {
            "overall_confidence": round(overall, 4),
            "ocr_confidence": ocr,
            "entity_resolution_confidence": entity,
            "aladdin_match_confidence": aladdin,
            "requires_human_review": requires_review,
            "review_reason": review_reason,
            "confidence_breakdown": breakdown,
            "auto_approved": not requires_review,
        }

    @staticmethod
    def _determine_review_reason(
        overall: float, ocr: float, entity: float, aladdin: float, aladdin_match: bool
    ) -> str:
        """Determine detailed reason why item needs review"""
        reasons = []

        if overall < ConfidenceThresholds.MANUAL_REVIEW_THRESHOLD:
            reasons.append(f"overall confidence {overall:.2f} < {ConfidenceThresholds.MANUAL_REVIEW_THRESHOLD}")

        if ocr < ConfidenceThresholds.OCR_DEFAULT:
            reasons.append(f"OCR quality poor ({ocr:.2f})")

        if entity < ConfidenceThresholds.ENTITY_FUZZY_MEDIUM:
            reasons.append(f"entity resolution uncertain ({entity:.2f})")

        if aladdin == 0:
            reasons.append("no Aladdin match found")
        elif aladdin < ConfidenceThresholds.ALADDIN_FUZZY:
            reasons.append(f"weak Aladdin match ({aladdin:.2f})")

        if reasons:
            return "; ".join(reasons)
        else:
            return "review threshold not met despite valid scores"

    async def validation_skill(
        self, input_data: Dict[str, Any], output: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Validate confidence score output

        Checks:
        - All component scores are 0.0-1.0
        - Overall confidence is 0.0-1.0
        - Overall is weighted average of components
        - Breakdown sums correctly
        """
        components = [
            ("ocr_confidence", output.get("ocr_confidence", 0)),
            ("entity_resolution_confidence", output.get("entity_resolution_confidence", 0)),
            ("aladdin_match_confidence", output.get("aladdin_match_confidence", 0)),
        ]

        # Check all components are valid
        for name, score in components:
            if not isinstance(score, (int, float)) or not (0 <= score <= 1):
                return (False, f"Invalid {name}: {score}")

        # Check overall is valid
        overall = output.get("overall_confidence", 0)
        if not isinstance(overall, (int, float)) or not (0 <= overall <= 1):
            return (False, f"Invalid overall_confidence: {overall}")

        # Verify breakdown sums correctly (within floating point rounding)
        breakdown = output.get("confidence_breakdown", {})
        ocr_contrib = breakdown.get("ocr_contribution", 0)
        entity_contrib = breakdown.get("entity_contribution", 0)
        aladdin_contrib = breakdown.get("aladdin_contribution", 0)

        calculated_overall = ocr_contrib + entity_contrib + aladdin_contrib
        if abs(calculated_overall - overall) > 0.01:  # Allow 0.01 rounding error
            return (
                False,
                f"Breakdown sums to {calculated_overall:.4f}, but overall is {overall:.4f}",
            )

        return (True, f"Confidence score valid: {overall:.2f} (auto_approved: {not output.get('requires_human_review')})")

    async def explanation_skill(
        self, input_data: Dict[str, Any], output: Dict[str, Any]
    ) -> str:
        """Generate explanation of confidence scoring decision"""
        company_name = input_data.get("company_name", "Unknown")
        overall = output.get("overall_confidence", 0)
        requires_review = output.get("requires_human_review", False)
        reason = output.get("review_reason", "")

        if not requires_review:
            explanation = (
                f"'{company_name}' auto-approved with confidence {overall:.2f}. "
                f"Strong signals across OCR, entity resolution, and Aladdin matching. "
                f"No human review required."
            )
        else:
            explanation = (
                f"'{company_name}' flagged for human review (confidence {overall:.2f}). "
                f"Reason(s): {reason}. "
                f"Please verify Aladdin ID match and company identity before approval."
            )

        return explanation
