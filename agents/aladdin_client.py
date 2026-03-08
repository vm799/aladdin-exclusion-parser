"""
Aladdin Client Agent - PAUL Skill-Based Agent for Counterparty ID Matching

Responsibilities:
- Query Aladdin API via aladdinsdk for counterparty/ISIN lookups
- Fall back to CSV-based lookup if SDK unavailable
- Return AladdinMatch results with confidence scores
- Handle API errors gracefully with fallback strategy
"""

import asyncio
import csv
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from agents.base_agent import SkillAgent
from agents.models import AladdinMatch, NormalizedCompany
from config.constants import ConfidenceThresholds, MatchType

logger = logging.getLogger(__name__)


class AladdinClientAgent(SkillAgent):
    """
    PAUL Skill-based agent for matching companies to Aladdin IDs/ISINs

    Two-mode operation:
    1. SDK Mode: Use official aladdinsdk for real Aladdin API calls
       - Queries live Aladdin counterparty database
       - Returns ISIN and entity IDs
    2. CSV Fallback: Use CSV lookup file for local development/testing
       - Provides identical interface when SDK unavailable
       - Useful for proof-of-concept and testing

    Implements:
    - Core Skill: Query Aladdin API or CSV, return AladdinMatch
    - Validation Skill: Check match format, confidence score validity
    - Explanation Skill: Document API response time, match method
    - Fallback Skill: Return manual_required on API error
    """

    # Cached set of valid match types for validation (avoid recreating on each call)
    VALID_MATCH_TYPES = {t.value for t in MatchType}

    def __init__(
        self,
        llm_config: "LLMConfig",
        name: str = "AladdinClientAgent",
        csv_fallback_path: Optional[str] = None,
    ):
        """
        Initialize Aladdin client agent

        Args:
            llm_config: OpenAI LLM configuration
            name: Agent name
            csv_fallback_path: Path to CSV fallback (aladdin_id, isin columns)
        """
        super().__init__(llm_config, name)
        self.csv_fallback_path = csv_fallback_path or "aladdin_lookup_sample.csv"
        self.sdk_available = False
        self.aladdin_api = None
        self.csv_db: Dict[str, Dict[str, str]] = {}  # canonical_name → {aladdin_id, isin, ...}

        self._init_sdk()
        self._load_csv_fallback()

    def _init_sdk(self):
        """Initialize Aladdin SDK if available"""
        try:
            from aladdinsdk.api.client import AladdinAPI

            self.aladdin_api = AladdinAPI("CounterpartyAPI")
            self.sdk_available = True
            self.logger.info("AladdinSDK initialized successfully")
        except ImportError:
            self.logger.warning("aladdinsdk not installed - using CSV fallback")
            self.sdk_available = False
        except Exception as e:
            self.logger.warning(f"Failed to initialize AladdinSDK: {str(e)} - using CSV fallback")
            self.sdk_available = False

    def _load_csv_fallback(self):
        """Load CSV fallback database"""
        try:
            with open(self.csv_fallback_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    company_name = row.get("company_name", "").strip()
                    if company_name:
                        self.csv_db[company_name.lower()] = {
                            "company_name": company_name,
                            "aladdin_id": row.get("aladdin_id", ""),
                            "isin": row.get("isin", ""),
                            "asset_class": row.get("asset_class", ""),
                            "region": row.get("region", ""),
                        }

            self.logger.info(f"Loaded {len(self.csv_db)} companies from CSV fallback")
        except FileNotFoundError:
            self.logger.warning(f"CSV fallback not found: {self.csv_fallback_path}")
        except Exception as e:
            self.logger.error(f"Failed to load CSV fallback: {str(e)}")

    async def core_skill(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Match normalized company to Aladdin ID/ISIN

        Input:
            {
                "company": NormalizedCompany,
                "prefer_sdk": bool (optional, default True)
            }

        Output:
            {
                "aladdin_id": str or None,
                "isin": str or None,
                "entity_name": str,
                "match_confidence": 0.0-1.0,
                "match_type": "exact|fuzzy|partial|manual_required",
                "api_response_time_ms": float,
                "source": "sdk|csv"
            }
        """
        company = input_data.get("company")
        prefer_sdk = input_data.get("prefer_sdk", True)

        if not isinstance(company, (dict, NormalizedCompany)):
            raise ValueError(f"Expected dict or NormalizedCompany, got {type(company)}")

        canonical_name = company.get("canonical_name", "")

        # Attempt SDK first if available and preferred
        if self.sdk_available and prefer_sdk:
            result = await self._query_aladdin_sdk(canonical_name)
            if result:
                return result

        # Fall back to CSV
        result = self._query_csv(canonical_name)
        return result

    async def _query_aladdin_sdk(self, canonical_name: str) -> Optional[Dict[str, Any]]:
        """
        Query Aladdin API via SDK

        Calls: POST /counterparties:search with company name
        """
        if not self.aladdin_api:
            return None

        try:
            import asyncio

            start = time.time()

            # Call Aladdin API counterparty search endpoint
            # Wrap blocking sync call in executor to avoid blocking event loop
            req_body = {"query": {"company_name": canonical_name}}
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.aladdin_api.post("/counterparties:search", req_body)
            )

            elapsed_ms = (time.time() - start) * 1000

            # Parse response - assuming format: {"results": [{"id": "...", "isin": "..."}]}
            if not response or not isinstance(response, dict):
                self.logger.warning(f"Unexpected Aladdin API response format")
                return None

            results = response.get("results", [])
            if not results:
                self.logger.info(f"No Aladdin matches for: {canonical_name}")
                return None

            # Use best match (first result)
            best_match = results[0]

            return {
                "aladdin_id": best_match.get("id"),
                "isin": best_match.get("isin"),
                "entity_name": best_match.get("entity_name", canonical_name),
                "match_confidence": ConfidenceThresholds.ALADDIN_FUZZY,
                "match_type": MatchType.FUZZY.value,
                "api_response_time_ms": elapsed_ms,
                "source": "sdk",
            }

        except Exception as e:
            self.logger.error(f"Aladdin SDK query failed: {str(e)}")
            return None

    def _query_csv(self, canonical_name: str) -> Dict[str, Any]:
        """
        Query CSV fallback database

        Performs exact and fuzzy matching on canonical_name
        """
        start = time.time()
        canonical_lower = canonical_name.lower().strip()

        # Exact match
        if canonical_lower in self.csv_db:
            entry = self.csv_db[canonical_lower]
            elapsed_ms = (time.time() - start) * 1000

            return {
                "aladdin_id": entry.get("aladdin_id"),
                "isin": entry.get("isin"),
                "entity_name": entry.get("company_name", canonical_name),
                "match_confidence": ConfidenceThresholds.ALADDIN_EXACT,
                "match_type": MatchType.EXACT.value,
                "api_response_time_ms": elapsed_ms,
                "source": "csv",
            }

        # Fuzzy match: use similarity scoring to avoid false positives
        best_match = None
        best_similarity = 0.75  # Threshold for fuzzy match

        for db_name, entry in self.csv_db.items():
            similarity = self._string_similarity(canonical_lower, db_name)
            if similarity > best_similarity and similarity > best_match[1] if best_match else similarity > best_similarity:
                best_match = (entry, similarity)

        if best_match:
            entry, similarity = best_match
            elapsed_ms = (time.time() - start) * 1000

            return {
                "aladdin_id": entry.get("aladdin_id"),
                "isin": entry.get("isin"),
                "entity_name": entry.get("company_name", canonical_name),
                "match_confidence": ConfidenceThresholds.ALADDIN_FUZZY,
                "match_type": MatchType.FUZZY.value,
                "api_response_time_ms": elapsed_ms,
                "source": "csv",
            }

        # No match found
        elapsed_ms = (time.time() - start) * 1000

        return {
            "aladdin_id": None,
            "isin": None,
            "entity_name": None,
            "match_confidence": 0.0,
            "match_type": MatchType.MANUAL_REQUIRED.value,
            "api_response_time_ms": elapsed_ms,
            "source": "csv",
        }

    @staticmethod
    def _string_similarity(s1: str, s2: str) -> float:
        """Calculate string similarity using Jaccard similarity on tokens"""
        s1 = s1.lower().strip()
        s2 = s2.lower().strip()

        if s1 == s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        # Split into tokens (words)
        set1 = set(s1.split())
        set2 = set(s2.split())
        if not set1 or not set2:
            return 0.0

        # Jaccard similarity: intersection / union
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    async def validation_skill(
        self, input_data: Dict[str, Any], output: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Validate Aladdin match output

        Checks:
        - Confidence score 0.0-1.0
        - Match type is valid
        - If aladdin_id present, should have high confidence
        - If manual_required, confidence should be 0.0
        """
        confidence = output.get("match_confidence", 0)
        match_type = output.get("match_type", "")
        aladdin_id = output.get("aladdin_id")

        if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 1):
            return (False, f"Invalid confidence score: {confidence}")

        if match_type not in self.VALID_MATCH_TYPES:
            return (False, f"Invalid match_type: {match_type}")

        if match_type == MatchType.MANUAL_REQUIRED.value:
            if confidence != 0.0:
                return (False, "manual_required matches should have confidence 0.0")
        else:
            if not aladdin_id:
                return (False, f"Non-manual matches must have aladdin_id")

        return (True, f"Valid Aladdin match: {match_type} with confidence {confidence}")

    async def explanation_skill(
        self, input_data: Dict[str, Any], output: Dict[str, Any]
    ) -> str:
        """Generate explanation of Aladdin matching decision"""
        company_name = input_data.get("company", {}).get("canonical_name", "unknown")
        match_type = output.get("match_type", "unknown")
        source = output.get("source", "unknown")
        api_time = output.get("api_response_time_ms", 0)

        if output.get("aladdin_id"):
            explanation = (
                f"Matched '{company_name}' to Aladdin ID {output['aladdin_id']} "
                f"via {match_type} match ({source} source, {api_time:.0f}ms)"
            )
        else:
            explanation = (
                f"No Aladdin match found for '{company_name}' - "
                f"requires manual lookup ({source} source, {api_time:.0f}ms)"
            )

        return explanation
