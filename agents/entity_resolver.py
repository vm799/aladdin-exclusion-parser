"""
Entity Resolution Agent - PAUL Skill-Based Agent for Company Name Normalization

Responsibilities:
- Load alias database from CSV
- Match extracted company names to canonical forms via alias lookup
- Use OpenAI GPT-4 for semantic disambiguation of ambiguous names
- Return normalized companies with confidence scores
"""

import asyncio
import csv
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from agents.base_agent import SkillAgent
from agents.models import ExtractedCompany, NormalizedCompany
from config.constants import ConfidenceThresholds

logger = logging.getLogger(__name__)


class EntityResolverAgent(SkillAgent):
    """
    PAUL Skill-based agent for normalizing and resolving company names

    Two-stage resolution:
    1. Alias Database Lookup (fast, no API cost)
       - Load CSV with company → aliases mappings
       - "GS" → alias match → "Goldman Sachs"
    2. GPT-4 Semantic Disambiguation (for unresolved/ambiguous names)
       - "Citi Bank" → GPT-4 determines "Citigroup" vs "Citibank"

    Implements:
    - Core Skill: Load DB, resolve names, handle ambiguity
    - Validation Skill: Check all names resolved, confidence > 0
    - Explanation Skill: Document resolution method (alias vs GPT-4)
    - Fallback Skill: Return unresolved with confidence 0, flag manual_required
    """

    def __init__(
        self,
        llm_config: "LLMConfig",
        name: str = "EntityResolverAgent",
        alias_db_path: Optional[str] = None,
    ):
        """
        Initialize entity resolver agent

        Args:
            llm_config: OpenAI LLM configuration
            name: Agent name
            alias_db_path: Path to alias CSV file (company_name, aliases columns)
        """
        super().__init__(llm_config, name)
        self.alias_db_path = alias_db_path or "aladdin_lookup_sample.csv"
        self.alias_map: Dict[str, str] = {}  # alias → canonical name
        self.canonical_aliases: Dict[str, List[str]] = {}  # canonical → list of aliases
        self._load_alias_database()

    def _load_alias_database(self):
        """Load alias database from CSV"""
        try:
            with open(self.alias_db_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    canonical = row.get("company_name", "").strip()
                    aliases_str = row.get("aliases", "")

                    if canonical:
                        # Store canonical name mapping
                        self.alias_map[canonical.lower()] = canonical

                        # Parse comma-separated aliases
                        if aliases_str:
                            aliases = [a.strip() for a in aliases_str.split(",")]
                            self.canonical_aliases[canonical] = aliases

                            # Map each alias to canonical
                            for alias in aliases:
                                self.alias_map[alias.lower()] = canonical

            self.logger.info(
                f"Loaded {len(self.canonical_aliases)} companies with "
                f"{len(self.alias_map)} total alias mappings from {self.alias_db_path}"
            )
        except FileNotFoundError:
            self.logger.warning(f"Alias database not found: {self.alias_db_path}")
        except Exception as e:
            self.logger.error(f"Failed to load alias database: {str(e)}")

    async def core_skill(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve and normalize company names

        Input:
            {
                "companies": [ExtractedCompany...],
                "use_gpt4": bool (optional, default True)
            }

        Output:
            {
                "normalized": [NormalizedCompany...],
                "unresolved": [ExtractedCompany...],
                "resolution_method": "alias_only" | "alias_and_gpt4",
                "ambiguities_found": [...]
            }
        """
        companies = input_data.get("companies", [])
        use_gpt4 = input_data.get("use_gpt4", True)

        normalized = []
        unresolved = []
        ambiguities = []

        # Stage 1: Alias lookup
        for company in companies:
            resolved = await self._resolve_via_alias(company)
            if resolved:
                normalized.append(resolved)
            else:
                unresolved.append(company)

        # Stage 2: GPT-4 disambiguation for unresolved
        if use_gpt4 and unresolved:
            self.logger.info(f"Using GPT-4 for {len(unresolved)} unresolved companies")
            gpt4_results = await self._resolve_via_gpt4(unresolved)
            normalized.extend(gpt4_results["normalized"])
            unresolved = gpt4_results["unresolved"]
            ambiguities = gpt4_results["ambiguities"]

        return {
            "normalized": [c.model_dump() for c in normalized],
            "unresolved": [c.model_dump() for c in unresolved],
            "resolution_method": "alias_and_gpt4" if use_gpt4 else "alias_only",
            "ambiguities_found": ambiguities,
            "total_resolved": len(normalized),
        }

    async def _resolve_via_alias(self, company: ExtractedCompany) -> Optional[NormalizedCompany]:
        """
        Resolve company name via alias database lookup

        Returns NormalizedCompany if found, None otherwise
        """
        raw_name = company.raw_name.lower().strip()

        # Exact match
        if raw_name in self.alias_map:
            canonical = self.alias_map[raw_name]
            return NormalizedCompany(
                canonical_name=canonical,
                extracted_from=company,
                normalization_confidence=ConfidenceThresholds.ENTITY_EXACT_MATCH,
                normalization_notes=f"Exact alias match for '{company.raw_name}'",
            )

        # Substring match (for partial names like "Morgan Stanley Inc" vs "Morgan Stanley")
        for alias_key, canonical in self.alias_map.items():
            if raw_name.startswith(alias_key) or alias_key.startswith(raw_name):
                # Only match if similarity is high (avoid false positives)
                if self._string_similarity(raw_name, alias_key) > 0.8:
                    return NormalizedCompany(
                        canonical_name=canonical,
                        extracted_from=company,
                        normalization_confidence=ConfidenceThresholds.ENTITY_FUZZY_HIGH,
                        normalization_notes=f"Fuzzy alias match for '{company.raw_name}' → {canonical}",
                    )

        return None

    async def _resolve_via_gpt4(self, companies: List[ExtractedCompany]) -> Dict[str, Any]:
        """
        Use OpenAI GPT-4 to semantically resolve ambiguous company names

        Handles cases like:
        - "Citi Bank" → determine Citigroup vs Citibank
        - "Morgan Stanley" → resolve exact canonical form
        - Abbreviations → expand to full names
        """
        normalized = []
        unresolved = []
        ambiguities = []

        if not companies:
            return {
                "normalized": normalized,
                "unresolved": unresolved,
                "ambiguities": ambiguities,
            }

        # Prepare batch prompt for efficiency
        company_names = [c.raw_name for c in companies]
        canonical_names = list(set(self.canonical_aliases.keys()))

        prompt = f"""
You are a financial data specialist. Resolve these company names to their canonical forms.

Known canonical companies (with aliases):
{json.dumps(self.canonical_aliases, indent=2)}

Companies to resolve:
{json.dumps(company_names)}

For each company, determine:
1. The canonical name (from known list, or best guess if unknown)
2. Confidence (0.0-1.0): 1.0 if exact match, 0.7-0.9 if strong inference, 0.0 if cannot determine
3. Ambiguity: List any alternative interpretations

Return JSON:
{{
  "resolutions": [
    {{"raw_name": "...", "canonical": "...", "confidence": 0.95, "method": "exact_match|fuzzy|inference|unknown"}}
  ]
}}
"""

        try:
            response = await self.llm.create_completion_async(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2048,
            )

            text = response.choices[0].message.content

            # Extract JSON more robustly - handle multiple {} blocks
            json_match = re.search(r'\{[^{}]*"resolutions"[^{}]*\}', text, re.DOTALL)
            if not json_match:
                # Fallback: try to find any valid JSON object
                json_match = re.search(r'\{.*\}', text, re.DOTALL)

            if not json_match:
                raise ValueError("No valid JSON found in GPT-4 response")

            json_str = json_match.group()
            result = json.loads(json_str)

            for resolution in result.get("resolutions", []):
                raw_name = resolution["raw_name"]
                canonical = resolution["canonical"]
                confidence = resolution["confidence"]
                method = resolution["method"]

                # Find original ExtractedCompany
                original = next((c for c in companies if c.raw_name == raw_name), None)
                if not original:
                    continue

                if confidence > 0:
                    notes = f"Resolved via GPT-4 {method}: '{raw_name}' → {canonical}"
                    normalized.append(
                        NormalizedCompany(
                            canonical_name=canonical,
                            extracted_from=original,
                            normalization_confidence=confidence,
                            normalization_notes=notes,
                        )
                    )
                else:
                    unresolved.append(original)
                    ambiguities.append({"raw_name": raw_name, "reason": "GPT-4 uncertain"})

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            self.logger.error(f"GPT-4 response parsing failed: {str(e)}")
            self.logger.debug(f"Response was: {text}")
            # Fall back: mark all as unresolved
            unresolved = companies
            ambiguities = [{"raw_name": c.raw_name, "reason": "GPT-4 response parse error"} for c in companies]
        except Exception as e:
            self.logger.error(f"Unexpected error in GPT-4 resolution: {str(e)}", exc_info=True)
            # Fall back: mark all as unresolved
            unresolved = companies
            ambiguities = [{"raw_name": c.raw_name, "reason": f"Unexpected error: {type(e).__name__}"} for c in companies]

        return {
            "normalized": normalized,
            "unresolved": unresolved,
            "ambiguities": ambiguities,
        }

    @staticmethod
    def _string_similarity(s1: str, s2: str) -> float:
        """Calculate string similarity (Jaccard similarity on trigrams)"""
        s1 = s1.lower().strip()
        s2 = s2.lower().strip()

        if s1 == s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        # Simple overlap check
        set1 = set(s1.split())
        set2 = set(s2.split())
        if not set1 or not set2:
            return 0.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union

    async def validation_skill(
        self, input_data: Dict[str, Any], output: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Validate entity resolution output

        Checks:
        - All normalized companies have canonical_name
        - Confidence scores are 0.0-1.0
        - Total resolved + unresolved == input count
        """
        normalized = output.get("normalized", [])
        unresolved = output.get("unresolved", [])
        input_count = len(input_data.get("companies", []))
        total = len(normalized) + len(unresolved)

        if total != input_count:
            return (
                False,
                f"Company count mismatch: {input_count} input, {total} output",
            )

        for company in normalized:
            if not company.get("canonical_name"):
                return (False, "Found normalized company without canonical_name")

            conf = company.get("normalization_confidence", 0)
            if not isinstance(conf, (int, float)) or not (0 <= conf <= 1):
                return (False, f"Invalid confidence: {conf}")

        return (
            True,
            f"Validated: {len(normalized)} resolved, {len(unresolved)} unresolved",
        )

    async def explanation_skill(
        self, input_data: Dict[str, Any], output: Dict[str, Any]
    ) -> str:
        """Generate explanation of resolution decisions"""
        method = output.get("resolution_method", "unknown")
        resolved = len(output.get("normalized", []))
        unresolved = len(output.get("unresolved", []))

        explanation = (
            f"Entity resolution using {method}: "
            f"{resolved} companies resolved to canonical names, "
            f"{unresolved} require manual review. "
            f"Unresolved companies flagged for GPT-4 or human disambiguation."
        )

        return explanation
