"""
Orchestrator Agent - PAUL Agent Coordinator for Full Exclusion Pipeline

Responsibilities:
- Coordinate all agents in sequence: Extract → Resolve → Match → Aggregate
- Handle errors and fallbacks at each stage
- Produce ExclusionCandidate objects ready for dashboard review
- Track processing time and audit trail
"""

import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from agents.aladdin_client import AladdinClientAgent
from agents.base_agent import SkillAgent
from agents.confidence_aggregator import ConfidenceAggregatorAgent
from agents.entity_resolver import EntityResolverAgent
from agents.extraction_agent import ExtractionAgent
from agents.models import ExclusionCandidate, ExclusionStatus

logger = logging.getLogger(__name__)


class OrchestratorAgent(SkillAgent):
    """
    PAUL Agent that orchestrates the full exclusion parsing pipeline

    Pipeline Flow:
    1. Extract companies from document (ExtractionAgent)
    2. Normalize names to canonical forms (EntityResolverAgent)
    3. Match to Aladdin IDs (AladdinClientAgent)
    4. Aggregate confidence scores (ConfidenceAggregatorAgent)
    5. Create ExclusionCandidate objects for review

    Error Handling:
    - If extraction fails: entire document fails
    - If entity resolution fails: use raw name, proceed with low confidence
    - If Aladdin lookup fails: flag for manual review
    - If confidence aggregation fails: mark as manual_required

    Implements:
    - Core Skill: Chain all agents, produce ExclusionCandidate list
    - Validation Skill: Check output contains valid candidates
    - Explanation Skill: Document which agents contributed to each candidate
    - Fallback Skill: Return empty list with error explanation
    """

    def __init__(
        self,
        llm_config: "LLMConfig",
        name: str = "OrchestratorAgent",
        alias_db_path: Optional[str] = None,
        csv_fallback_path: Optional[str] = None,
    ):
        """
        Initialize orchestrator agent with sub-agents

        Args:
            llm_config: OpenAI LLM configuration
            name: Agent name
            alias_db_path: Path to alias database for entity resolver
            csv_fallback_path: Path to CSV fallback for Aladdin client
        """
        super().__init__(llm_config, name)

        # Initialize sub-agents
        self.extraction_agent = ExtractionAgent(llm_config, "ExtractionAgent")
        self.entity_resolver = EntityResolverAgent(
            llm_config, "EntityResolverAgent", alias_db_path
        )
        self.aladdin_client = AladdinClientAgent(
            llm_config, "AladdinClientAgent", csv_fallback_path
        )
        self.confidence_aggregator = ConfidenceAggregatorAgent(
            llm_config, "ConfidenceAggregatorAgent"
        )

        self.logger.info("Orchestrator initialized with 4 sub-agents")

    async def core_skill(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute full pipeline: Extract → Resolve → Match → Aggregate

        Input:
            {
                "file_path": str,
                "doc_type": DocType,
                "content": optional raw content,
                "source_doc": str,
                "use_gpt4": bool (optional, default True for entity resolution)
            }

        Output:
            {
                "candidates": [ExclusionCandidate...],
                "total_documents": 1,
                "total_candidates": int,
                "processing_time_ms": float,
                "agents_executed": ["extract", "resolve", "match", "aggregate"],
                "errors": []
            }
        """
        start_time = time.time()
        candidates = []
        errors = []
        agents_executed = []

        try:
            # Stage 1: Extract companies from document
            self.logger.info("Stage 1: Extracting companies from document")
            extraction_result = await self.extraction_agent.execute(input_data)

            if not extraction_result.success:
                raise RuntimeError(
                    f"Extraction failed: {extraction_result.error}"
                )

            agents_executed.append("extract")
            extracted_companies = extraction_result.data.get("companies", [])
            self.logger.info(f"Extracted {len(extracted_companies)} companies")

            if not extracted_companies:
                self.logger.warning("No companies extracted from document")
                return self._build_result(
                    candidates,
                    0,
                    time.time() - start_time,
                    agents_executed,
                    ["No companies found in document"],
                )

            # Stage 2: Entity resolution (normalize company names)
            self.logger.info(
                f"Stage 2: Resolving {len(extracted_companies)} company names"
            )
            use_gpt4 = input_data.get("use_gpt4", True)
            resolution_result = await self.entity_resolver.execute(
                {"companies": extracted_companies, "use_gpt4": use_gpt4}
            )

            if not resolution_result.success:
                self.logger.warning(f"Entity resolution warning: {resolution_result.error}")
                # Continue with extracted companies (not ideal but fallback)
                normalized_companies = extracted_companies
            else:
                agents_executed.append("resolve")
                normalized_companies = resolution_result.data.get("normalized", [])
                unresolved = resolution_result.data.get("unresolved", [])
                self.logger.info(
                    f"Resolved {len(normalized_companies)} companies, "
                    f"{len(unresolved)} unresolved"
                )

            # Stage 3: Aladdin matching (parallel execution for speed)
            self.logger.info(
                f"Stage 3: Matching {len(normalized_companies)} to Aladdin IDs"
            )
            match_tasks = [
                self.aladdin_client.execute({"company": company})
                for company in normalized_companies
            ]
            match_results = await asyncio.gather(*match_tasks, return_exceptions=True)
            agents_executed.append("match")

            # Process match results
            matches = []
            for i, result in enumerate(match_results):
                if isinstance(result, Exception):
                    self.logger.error(f"Aladdin match error for company {i}: {str(result)}")
                    matches.append(None)
                elif hasattr(result, "success") and result.success:
                    matches.append(result.data)
                else:
                    self.logger.warning(f"Aladdin match failed for company {i}")
                    matches.append(None)

            # Stage 4: Confidence aggregation and candidate creation
            self.logger.info(f"Stage 4: Aggregating confidence scores")
            source_doc = input_data.get("source_doc", "unknown")

            for idx, (extracted, match) in enumerate(
                zip(extracted_companies, matches)
            ):
                try:
                    # Extract company name (from normalized if available)
                    company_name = extracted.get("raw_name", "Unknown")

                    # Get confidence scores from match
                    aladdin_conf = (
                        match.get("match_confidence", 0.0)
                        if match
                        else 0.0
                    )

                    # Aggregate confidence
                    agg_result = await self.confidence_aggregator.execute(
                        {
                            "ocr_confidence": extracted.get("ocr_confidence", 0.0),
                            "entity_confidence": extracted.get("ocr_confidence", 0.6),
                            "aladdin_confidence": aladdin_conf,
                            "company_name": company_name,
                            "aladdin_match": aladdin_conf > 0,
                        }
                    )

                    if not agg_result.success:
                        raise RuntimeError(f"Confidence aggregation failed: {agg_result.error}")

                    agents_executed.append("aggregate")

                    confidence_score_data = agg_result.data
                    status = (
                        ExclusionStatus.AUTO_APPROVED
                        if not confidence_score_data.get("requires_human_review")
                        else ExclusionStatus.PENDING
                    )

                    # Create ExclusionCandidate
                    candidate = ExclusionCandidate(
                        id=str(uuid.uuid4()),
                        source_doc=source_doc,
                        company_name=company_name,
                        extracted_company=extracted,
                        normalized_company=extracted,  # Use as-is for now
                        aladdin_match=match or {},
                        confidence_score=confidence_score_data,
                        status=status,
                        agent_version="v1-orchestrator",
                        processing_time_ms=(time.time() - start_time) * 1000,
                    )

                    candidates.append(candidate)
                    self.logger.info(
                        f"Created candidate {idx+1}/{len(extracted_companies)}: "
                        f"{company_name} (confidence: {confidence_score_data.get('overall_confidence', 0):.2f})"
                    )

                except Exception as e:
                    self.logger.error(f"Failed to create candidate {idx}: {str(e)}")
                    errors.append(f"Candidate {idx}: {str(e)}")

        except Exception as e:
            self.logger.error(f"Pipeline failed at stage: {str(e)}", exc_info=True)
            errors.append(str(e))

        elapsed_ms = (time.time() - start_time) * 1000

        return self._build_result(candidates, 1, elapsed_ms, agents_executed, errors)

    def _build_result(
        self,
        candidates: List[Dict[str, Any]],
        num_docs: int,
        elapsed_ms: float,
        agents_executed: List[str],
        errors: List[str],
    ) -> Dict[str, Any]:
        """Build standardized result dictionary"""
        return {
            "candidates": [
                c.model_dump() if hasattr(c, "model_dump") else c
                for c in candidates
            ],
            "total_documents": num_docs,
            "total_candidates": len(candidates),
            "processing_time_ms": round(elapsed_ms, 2),
            "agents_executed": agents_executed,
            "errors": errors,
            "success": len(errors) == 0,
        }

    async def validation_skill(
        self, input_data: Dict[str, Any], output: Dict[str, Any]
    ) -> tuple:
        """
        Validate orchestrator output

        Checks:
        - Contains list of ExclusionCandidate objects
        - Each candidate has required fields
        - Confidence scores are valid
        """
        candidates = output.get("candidates", [])

        if not isinstance(candidates, list):
            return (False, "Output candidates must be a list")

        for i, candidate in enumerate(candidates):
            if not candidate.get("id"):
                return (False, f"Candidate {i} missing id")
            if not candidate.get("company_name"):
                return (False, f"Candidate {i} missing company_name")
            if not candidate.get("status"):
                return (False, f"Candidate {i} missing status")

            conf = candidate.get("confidence_score", {})
            if not conf.get("overall_confidence"):
                return (False, f"Candidate {i} missing confidence score")

        return (True, f"Validated {len(candidates)} candidates")

    async def explanation_skill(
        self, input_data: Dict[str, Any], output: Dict[str, Any]
    ) -> str:
        """Generate explanation of orchestration result"""
        num_candidates = len(output.get("candidates", []))
        agents = output.get("agents_executed", [])
        errors = output.get("errors", [])
        time_ms = output.get("processing_time_ms", 0)

        explanation = (
            f"Pipeline processed document in {time_ms:.0f}ms. "
            f"Created {num_candidates} candidates using agents: {', '.join(agents)}. "
        )

        if errors:
            explanation += f"Errors: {'; '.join(errors)}"
        else:
            explanation += "No errors encountered."

        return explanation
