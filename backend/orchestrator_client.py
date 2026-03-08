"""
Orchestrator Client - Sends ExclusionCandidates from Orchestrator to FastAPI Backend

Enables orchestrator.py to POST completed ExclusionCandidate objects to the backend
for storage, approval workflow, and dashboard display.
"""

import asyncio
import logging
from typing import List, Optional
from uuid import UUID

import httpx
from agents.models import ExclusionCandidate

logger = logging.getLogger(__name__)


class OrchestratorClient:
    """Client for sending exclusion candidates to FastAPI backend"""

    def __init__(self, backend_url: str = "http://localhost:8000", timeout: int = 30):
        """
        Initialize orchestrator client

        Args:
            backend_url: FastAPI backend URL
            timeout: Request timeout in seconds
        """
        self.backend_url = backend_url
        self.timeout = timeout

    async def save_candidate(
        self,
        candidate: ExclusionCandidate,
    ) -> Optional[str]:
        """
        Send single ExclusionCandidate to backend

        Args:
            candidate: Exclusion candidate from orchestrator

        Returns:
            Candidate ID if successful, None if failed
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.backend_url}/api/exclusions",
                    json=candidate.model_dump(),
                )

                if response.status_code in [200, 201]:
                    data = response.json()
                    logger.info(
                        f"✅ Saved candidate {candidate.company_name} to backend "
                        f"(status={data.get('status')})"
                    )
                    return data.get("id")
                else:
                    logger.error(
                        f"❌ Failed to save candidate {candidate.company_name}: "
                        f"{response.status_code} {response.text}"
                    )
                    return None

        except httpx.ConnectError:
            logger.error(
                f"❌ Backend connection failed ({self.backend_url}). "
                f"Ensure FastAPI is running: uvicorn backend.app:app --port 8000"
            )
            return None
        except Exception as e:
            logger.error(f"❌ Error saving candidate: {str(e)}", exc_info=True)
            return None

    async def save_candidates_batch(
        self,
        candidates: List[ExclusionCandidate],
    ) -> int:
        """
        Send multiple ExclusionCandidates to backend (parallel)

        Args:
            candidates: List of exclusion candidates

        Returns:
            Number of successfully saved candidates
        """
        if not candidates:
            return 0

        logger.info(f"Sending {len(candidates)} candidates to backend...")

        # Send all in parallel
        tasks = [self.save_candidate(c) for c in candidates]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successes
        successful = sum(1 for r in results if r is not None and not isinstance(r, Exception))
        logger.info(f"✅ Successfully saved {successful}/{len(candidates)} candidates")

        return successful

    async def get_candidates(
        self,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[dict]:
        """
        Fetch candidates from backend (for dashboard)

        Args:
            status: Filter by status (optional)
            limit: Maximum candidates to return

        Returns:
            List of exclusion candidate dicts
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                params = {"limit": limit}
                if status:
                    params["status"] = status

                response = await client.get(
                    f"{self.backend_url}/api/exclusions",
                    params=params,
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✅ Retrieved {len(data.get('items', []))} candidates")
                    return data.get("items", [])
                else:
                    logger.error(f"Failed to fetch candidates: {response.status_code}")
                    return []

        except Exception as e:
            logger.error(f"Error fetching candidates: {str(e)}")
            return []

    async def approve_candidate(
        self,
        candidate_id: UUID,
        user_id: str,
        reason: str = None,
    ) -> bool:
        """
        Approve a candidate via backend

        Args:
            candidate_id: Candidate UUID
            user_id: User approving
            reason: Optional approval reason

        Returns:
            True if successful, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.patch(
                    f"{self.backend_url}/api/exclusions/{candidate_id}/approve",
                    json={"user_id": user_id, "reason": reason or ""},
                )

                if response.status_code == 200:
                    logger.info(f"✅ Approved candidate {candidate_id}")
                    return True
                else:
                    logger.error(f"Failed to approve: {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"Error approving candidate: {str(e)}")
            return False

    async def reject_candidate(
        self,
        candidate_id: UUID,
        user_id: str,
        reason: str,
    ) -> bool:
        """
        Reject a candidate via backend

        Args:
            candidate_id: Candidate UUID
            user_id: User rejecting
            reason: Rejection reason

        Returns:
            True if successful, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.patch(
                    f"{self.backend_url}/api/exclusions/{candidate_id}/reject",
                    json={"user_id": user_id, "reason": reason},
                )

                if response.status_code == 200:
                    logger.info(f"✅ Rejected candidate {candidate_id}")
                    return True
                else:
                    logger.error(f"Failed to reject: {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"Error rejecting candidate: {str(e)}")
            return False

    async def get_audit_trail(self, candidate_id: UUID) -> List[dict]:
        """
        Get immutable audit trail for a candidate

        Args:
            candidate_id: Candidate UUID

        Returns:
            List of audit log entries
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.backend_url}/api/audit/{candidate_id}",
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Failed to get audit trail: {response.status_code}")
                    return []

        except Exception as e:
            logger.error(f"Error getting audit trail: {str(e)}")
            return []
