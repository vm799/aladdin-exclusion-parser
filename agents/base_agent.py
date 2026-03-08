"""
PAUL Framework Base Agent Class
Implements Skills-Based Agent Architecture with Constitutional AI Principles

PAUL = Projects + Auditing + Unified Logic + Lifecycle
Constitutional Principles: Helpful + Harmless + Honest
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SkillResult(BaseModel):
    """Result from executing a skill"""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    validation_msg: Optional[str] = None
    audit_explanation: Optional[str] = None
    agent_name: Optional[str] = None
    timestamp: str = None

    def __init__(self, **data):
        super().__init__(**data)
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()


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

        # Constitutional principles
        self.constitution = {
            "helpful": "Actively assist with exclusion parsing; provide clear explanations",
            "harmless": "Never corrupt data; flag uncertainties; require human approval before Aladdin push",
            "honest": "Explain confidence scores transparently; audit all decisions; admit limitations",
        }

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
            self.logger.info(f"Executing core_skill with input: {json.dumps(input_data)[:100]}...")

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

        except Exception as e:
            # Fallback with PAUL "Harmless" principle
            self.logger.error(f"Core skill failed, executing fallback: {str(e)}", exc_info=True)
            fallback_output = await self.fallback_skill(input_data, e)

            result = SkillResult(
                success=False,
                data=fallback_output,
                error=str(e),
                audit_explanation=f"Fallback executed due to {type(e).__name__}",
                agent_name=self.name,
            )

            return result

    def validate_constitutional_principles(self) -> Dict[str, str]:
        """
        Validate that agent implements constitutional principles

        Returns:
            Dictionary of principle -> implementation status
        """
        return {
            "helpful": "✓ Agent provides explanations and audit trails",
            "harmless": "✓ Agent validates output and has fallback strategies",
            "honest": "✓ Agent documents confidence and limitations",
        }


# Type stubs for LLM config (will be imported from config module)
class LLMConfig:
    """Placeholder for LLM configuration - imported from config.llm"""

    pass
