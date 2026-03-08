"""
PAUL Framework Base Agent Class
Implements Skills-Based Agent Architecture with Constitutional AI Principles

PAUL = Projects + Auditing + Unified Logic + Lifecycle
Constitutional Principles: Helpful + Harmless + Honest
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from pydantic import BaseModel, Field

from config.constants import ConstitutionalPrinciples

if TYPE_CHECKING:
    from config.llm import LLMConfig

logger = logging.getLogger(__name__)


class SkillResult(BaseModel):
    """Result from executing a skill"""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    validation_msg: Optional[str] = None
    audit_explanation: Optional[str] = None
    agent_name: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class SkillAgent(ABC):
    """
    Base agent implementing PAUL constitutional principles

    Each agent is a Skill Cluster with:
    - Core Skill: Primary responsibility
    - Validation Skill: Self-check output quality
    - Explanation Skill: Audit trail reasoning
    - Fallback Skill: Graceful degradation
    """

    def __init__(self, llm_config: "LLMConfig", name: str, agent_id: Optional[str] = None):
        """
        Initialize PAUL agent

        Args:
            llm_config: OpenAI LLM configuration
            name: Agent name (e.g., "ExtractionAgent")
            agent_id: Optional unique agent identifier
        """
        self.llm = llm_config
        self.name = name
        self.agent_id = agent_id or f"{name}_{datetime.utcnow().isoformat()}"
        self.logger = logging.getLogger(f"agent.{name}")

        self.logger.info(f"Initialized {self.name} with agent_id={self.agent_id}")

    @abstractmethod
    async def core_skill(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Primary responsibility - implement this in subclasses

        Returns:
            Dictionary with skill results
        """
        pass

    async def validation_skill(
        self, input_data: Dict[str, Any], output: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Self-check: Is output quality sufficient?

        Args:
            input_data: Original input to core_skill
            output: Result from core_skill

        Returns:
            (is_valid, validation_message)
        """
        # Override in subclasses for specific validation
        return (True, "Passed basic validation")

    async def explanation_skill(
        self, input_data: Dict[str, Any], output: Dict[str, Any]
    ) -> str:
        """
        Generate audit trail explanation of decision

        Implements PAUL "Honest" principle by documenting reasoning

        Args:
            input_data: Original input
            output: Result from core_skill

        Returns:
            Human-readable explanation of the decision
        """
        # Override in subclasses to use LLM for explanation
        # Default: return basic summary
        return f"{self.name} processed input and returned result"

    async def fallback_skill(
        self, input_data: Dict[str, Any], error: Exception
    ) -> Dict[str, Any]:
        """
        Graceful degradation when primary skill fails

        Implements PAUL "Harmless" principle by failing safely

        Args:
            input_data: Original input
            error: Exception that occurred

        Returns:
            Safe fallback result
        """
        # Override in subclasses for specific fallback behavior
        self.logger.error(f"Fallback executed: {str(error)}", exc_info=True)
        return {
            "status": "fallback",
            "error": str(error),
            "error_type": type(error).__name__,
            "recommendation": "manual_review",
            "requires_human_intervention": True,
        }

    async def execute(self, input_data: Dict[str, Any]) -> SkillResult:
        """
        Main execution loop with PAUL principles

        Flow:
        1. Execute core skill (primary responsibility)
        2. Validate output (self-check quality)
        3. Generate explanation (audit trail)
        4. Return result or fallback on error

        Args:
            input_data: Input to process

        Returns:
            SkillResult with data, validation, and audit trail
        """
        try:
            # Only log large payloads at debug level to avoid hot-path overhead
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(f"Executing {self.name} with input keys: {list(input_data.keys())}")

            # Execute core skill
            output = await self.core_skill(input_data)

            # Validate output (PAUL "Harmless" principle)
            is_valid, validation_msg = await self.validation_skill(input_data, output)
            validation_status = "PASS" if is_valid else "WARN"
            self.logger.info(f"Validation {validation_status}: {validation_msg}")

            # Generate explanation (PAUL "Honest" principle)
            explanation = await self.explanation_skill(input_data, output)

            # Build result
            result = SkillResult(
                success=True,
                data=output,
                validation_msg=validation_msg,
                audit_explanation=explanation,
                agent_name=self.name,
            )

            self.logger.info(f"Execution completed successfully: {self.agent_id}")
            return result

        except ValueError as e:
            # Expected validation errors
            self.logger.warning(f"Validation failed: {str(e)}")
            fallback_output = await self.fallback_skill(input_data, e)
            return SkillResult(
                success=False,
                data=fallback_output,
                error=str(e),
                audit_explanation=f"Validation error: {type(e).__name__}",
                agent_name=self.name,
            )
        except Exception as e:
            # Unexpected errors - execute fallback
            self.logger.error(f"Unexpected error, executing fallback: {str(e)}", exc_info=True)
            fallback_output = await self.fallback_skill(input_data, e)
            return SkillResult(
                success=False,
                data=fallback_output,
                error=str(e),
                audit_explanation=f"Fallback executed due to {type(e).__name__}",
                agent_name=self.name,
            )

    def get_constitutional_principles(self) -> Dict[str, str]:
        """
        Get PAUL constitutional principles for this agent

        Returns:
            Dictionary of principle -> description
        """
        return {
            "helpful": ConstitutionalPrinciples.HELPFUL,
            "harmless": ConstitutionalPrinciples.HARMLESS,
            "honest": ConstitutionalPrinciples.HONEST,
        }
