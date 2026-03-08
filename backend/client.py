"""
Streamlit Backend Client - Handles communication with FastAPI backend

Provides fallback to mock data if backend is unavailable.
"""

import requests
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class BackendConfig:
    """Backend configuration"""
    base_url: str = "http://localhost:8001"
    timeout: float = 5.0
    fallback_mode: bool = False  # When True, uses mock data


class BackendClient:
    """Client for communicating with FastAPI backend"""

    def __init__(self, config: BackendConfig = None):
        self.config = config or BackendConfig()
        self.session = requests.Session()
        self._test_connection()

    def _test_connection(self) -> bool:
        """Test if backend is available"""
        try:
            response = self.session.get(
                f"{self.config.base_url}/health",
                timeout=self.config.timeout
            )
            is_available = response.status_code == 200
            if not is_available:
                logger.warning(f"Backend health check failed: {response.status_code}")
                self.config.fallback_mode = True
            return is_available
        except requests.RequestException as e:
            logger.warning(f"Backend unavailable: {e}. Using fallback mode.")
            self.config.fallback_mode = True
            return False

    def list_exclusions(
        self,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        List exclusions from backend
        Falls back to mock data if backend unavailable
        """
        if self.config.fallback_mode:
            return self._get_mock_list(status, skip, limit)

        try:
            params = {"skip": skip, "limit": limit}
            if status:
                params["status"] = status

            response = self.session.get(
                f"{self.config.base_url}/api/exclusions",
                params=params,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to list exclusions: {e}")
            self.config.fallback_mode = True
            return self._get_mock_list(status, skip, limit)

    def get_exclusion(self, exclusion_id: str) -> Optional[Dict[str, Any]]:
        """Get single exclusion"""
        if self.config.fallback_mode:
            return self._get_mock_single(exclusion_id)

        try:
            response = self.session.get(
                f"{self.config.base_url}/api/exclusions/{exclusion_id}",
                timeout=self.config.timeout
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get exclusion: {e}")
            self.config.fallback_mode = True
            return self._get_mock_single(exclusion_id)

    def create_exclusion(self, candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create exclusion (for demo, returns mock data)"""
        if self.config.fallback_mode:
            return self._create_mock_exclusion(candidate)

        try:
            response = self.session.post(
                f"{self.config.base_url}/api/exclusions",
                json=candidate,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to create exclusion: {e}")
            self.config.fallback_mode = True
            return self._create_mock_exclusion(candidate)

    def approve_exclusion(
        self,
        exclusion_id: str,
        user_id: str,
        reason: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Approve exclusion"""
        if self.config.fallback_mode:
            logger.info(f"[MOCK] Approved {exclusion_id} by {user_id}")
            return {"status": "approved", "reviewed_by": user_id}

        try:
            response = self.session.patch(
                f"{self.config.base_url}/api/exclusions/{exclusion_id}/approve",
                json={"user_id": user_id, "reason": reason},
                timeout=self.config.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to approve exclusion: {e}")
            return self._create_mock_exclusion({})

    def reject_exclusion(
        self,
        exclusion_id: str,
        user_id: str,
        reason: str
    ) -> Optional[Dict[str, Any]]:
        """Reject exclusion"""
        if self.config.fallback_mode:
            logger.info(f"[MOCK] Rejected {exclusion_id} by {user_id}: {reason}")
            return {"status": "rejected", "reviewed_by": user_id}

        try:
            response = self.session.patch(
                f"{self.config.base_url}/api/exclusions/{exclusion_id}/reject",
                json={"user_id": user_id, "reason": reason},
                timeout=self.config.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to reject exclusion: {e}")
            return {"status": "rejected", "reviewed_by": user_id}

    def get_audit_trail(self, exclusion_id: str) -> List[Dict[str, Any]]:
        """Get audit trail for exclusion"""
        if self.config.fallback_mode:
            return self._get_mock_audit_trail(exclusion_id)

        try:
            response = self.session.get(
                f"{self.config.base_url}/api/audit/{exclusion_id}",
                timeout=self.config.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get audit trail: {e}")
            return self._get_mock_audit_trail(exclusion_id)

    # ==================== FALLBACK MOCK DATA ====================

    @staticmethod
    def _get_mock_list(status: Optional[str] = None, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """Return mock list data"""
        mock_items = [
            {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "source_doc": "client_email_001.eml",
                "company_name": "Goldman Sachs",
                "extracted_company": {"raw_name": "GS", "ocr_confidence": 0.95},
                "normalized_company": {"canonical_name": "Goldman Sachs", "normalization_confidence": 0.99},
                "aladdin_match": {"aladdin_id": "GS001", "isin": "US0123456789", "match_confidence": 1.0},
                "overall_confidence": 0.98,
                "ocr_confidence": 0.95,
                "entity_resolution_confidence": 0.99,
                "aladdin_match_confidence": 1.0,
                "confidence_breakdown": {"ocr_weight": 0.20, "entity_weight": 0.30, "aladdin_weight": 0.50},
                "status": "auto_approved",
                "agent_version": "v1-orchestrator",
                "reviewed_by": "AUTO",
                "reviewed_at": "2026-03-08T12:00:00Z",
                "created_at": "2026-03-08T12:00:00Z",
                "updated_at": "2026-03-08T12:00:00Z"
            },
            {
                "id": "550e8400-e29b-41d4-a716-446655440002",
                "source_doc": "client_email_001.eml",
                "company_name": "Morgan Stanley",
                "extracted_company": {"raw_name": "Morgan Stanley", "ocr_confidence": 0.90},
                "normalized_company": {"canonical_name": "Morgan Stanley", "normalization_confidence": 0.95},
                "aladdin_match": {"aladdin_id": "MS001", "isin": "US0234567890", "match_confidence": 0.95},
                "overall_confidence": 0.93,
                "ocr_confidence": 0.90,
                "entity_resolution_confidence": 0.95,
                "aladdin_match_confidence": 0.95,
                "confidence_breakdown": {"ocr_weight": 0.20, "entity_weight": 0.30, "aladdin_weight": 0.50},
                "status": "auto_approved",
                "agent_version": "v1-orchestrator",
                "reviewed_by": "AUTO",
                "reviewed_at": "2026-03-08T12:00:00Z",
                "created_at": "2026-03-08T12:00:00Z",
                "updated_at": "2026-03-08T12:00:00Z"
            },
            {
                "id": "550e8400-e29b-41d4-a716-446655440003",
                "source_doc": "client_email_002.eml",
                "company_name": "Unknown Vendor XYZ",
                "extracted_company": {"raw_name": "Unknown Vendor XYZ", "ocr_confidence": 0.40},
                "normalized_company": {"canonical_name": "Unknown Vendor XYZ", "normalization_confidence": 0.50},
                "aladdin_match": {"aladdin_id": "", "isin": "", "match_confidence": 0.0},
                "overall_confidence": 0.40,
                "ocr_confidence": 0.40,
                "entity_resolution_confidence": 0.50,
                "aladdin_match_confidence": 0.0,
                "confidence_breakdown": {"ocr_weight": 0.20, "entity_weight": 0.30, "aladdin_weight": 0.50},
                "status": "pending",
                "agent_version": "v1-orchestrator",
                "reviewed_by": None,
                "reviewed_at": None,
                "created_at": "2026-03-08T12:00:00Z",
                "updated_at": "2026-03-08T12:00:00Z"
            }
        ]

        if status:
            mock_items = [item for item in mock_items if item["status"] == status]

        return {
            "items": mock_items[skip:skip + limit],
            "total": len(mock_items),
            "skip": skip,
            "limit": limit
        }

    @staticmethod
    def _get_mock_single(exclusion_id: str) -> Optional[Dict[str, Any]]:
        """Return mock single item"""
        items = BackendClient._get_mock_list(None, 0, 1000)["items"]
        for item in items:
            if item["id"] == exclusion_id:
                return item
        return None

    @staticmethod
    def _create_mock_exclusion(candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Create mock exclusion"""
        import uuid
        from datetime import datetime
        now = datetime.utcnow().isoformat() + "Z"
        return {
            "id": str(uuid.uuid4()),
            "source_doc": candidate.get("source_doc", "unknown.pdf"),
            "company_name": candidate.get("company_name", "Unknown"),
            "extracted_company": candidate.get("extracted_company", {}),
            "normalized_company": candidate.get("normalized_company", {}),
            "aladdin_match": candidate.get("aladdin_match", {}),
            "overall_confidence": candidate.get("overall_confidence", 0.5),
            "ocr_confidence": candidate.get("ocr_confidence", 0.5),
            "entity_resolution_confidence": candidate.get("entity_resolution_confidence", 0.5),
            "aladdin_match_confidence": candidate.get("aladdin_match_confidence", 0.5),
            "confidence_breakdown": candidate.get("confidence_breakdown", {}),
            "status": "auto_approved" if candidate.get("overall_confidence", 0) >= 0.90 else "pending",
            "agent_version": "v1-orchestrator",
            "reviewed_by": "AUTO" if candidate.get("overall_confidence", 0) >= 0.90 else None,
            "reviewed_at": now if candidate.get("overall_confidence", 0) >= 0.90 else None,
            "created_at": now,
            "updated_at": now
        }

    @staticmethod
    def _get_mock_audit_trail(exclusion_id: str) -> List[Dict[str, Any]]:
        """Return mock audit trail"""
        now = datetime.utcnow().isoformat() + "Z"
        return [
            {
                "id": "audit-001",
                "exclusion_id": exclusion_id,
                "action": "extract",
                "agent_name": "ExtractionAgent",
                "input_data": {},
                "output_data": {},
                "confidence_score": 0.95,
                "audit_explanation": "Company extracted from document via OCR",
                "timestamp": now
            },
            {
                "id": "audit-002",
                "exclusion_id": exclusion_id,
                "action": "resolve",
                "agent_name": "EntityResolverAgent",
                "input_data": {},
                "output_data": {},
                "confidence_score": 0.99,
                "audit_explanation": "Company name normalized to canonical form",
                "timestamp": now
            },
            {
                "id": "audit-003",
                "exclusion_id": exclusion_id,
                "action": "match",
                "agent_name": "AladdinClientAgent",
                "input_data": {},
                "output_data": {},
                "confidence_score": 1.0,
                "audit_explanation": "Matched to Aladdin via exact match",
                "timestamp": now
            },
            {
                "id": "audit-004",
                "exclusion_id": exclusion_id,
                "action": "aggregate",
                "agent_name": "ConfidenceAggregatorAgent",
                "input_data": {},
                "output_data": {},
                "confidence_score": 0.98,
                "audit_explanation": "Confidence aggregated from multiple sources",
                "timestamp": now
            },
            {
                "id": "audit-005",
                "exclusion_id": exclusion_id,
                "action": "auto_approve",
                "agent_name": "ConfidenceAggregatorAgent",
                "input_data": {},
                "output_data": {},
                "confidence_score": 0.98,
                "audit_explanation": "Auto-approved due to high confidence: 0.98 >= 0.90",
                "timestamp": now
            }
        ]

    @property
    def backend_status(self) -> str:
        """Get backend connection status"""
        return "🔴 Fallback Mode (Mock Data)" if self.config.fallback_mode else "🟢 Connected to Backend"

