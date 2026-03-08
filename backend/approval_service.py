"""
Approval Service - Implements Exclusion Approval Workflow and State Machine

State Transitions:
- PENDING → AUTO_APPROVED (if confidence >= 0.90)
- PENDING → APPROVED (human review)
- PENDING → REJECTED (human review)
- APPROVED/AUTO_APPROVED → SYNCED (post to Aladdin)

Each transition creates immutable audit_log entry.
"""

import logging
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import ApprovalOverrideDB, AuditLogDB, ExclusionDB
from config.constants import ConfidenceThresholds, ExclusionStatus

logger = logging.getLogger(__name__)


class ApprovalService:
    """
    Manage exclusion approval workflow with state machine and audit logging
    """

    @staticmethod
    async def auto_approve_if_qualified(
        session: AsyncSession,
        exclusion: ExclusionDB,
    ) -> bool:
        """
        Auto-approve exclusion if confidence >= AUTO_APPROVAL_THRESHOLD

        Args:
            session: Database session
            exclusion: Exclusion to potentially auto-approve

        Returns:
            True if auto-approved, False otherwise
        """
        if exclusion.overall_confidence >= ConfidenceThresholds.AUTO_APPROVAL_THRESHOLD:
            logger.info(
                f"Auto-approving exclusion {exclusion.id} "
                f"(confidence: {exclusion.overall_confidence:.2f})"
            )

            # Update exclusion status
            exclusion.status = ExclusionStatus.AUTO_APPROVED.value
            exclusion.reviewed_at = datetime.utcnow()
            exclusion.reviewed_by = "AUTO"

            # Create audit log entry
            audit_entry = AuditLogDB(
                id=uuid4(),
                exclusion_id=exclusion.id,
                action="auto_approve",
                agent_name="ConfidenceAggregatorAgent",
                confidence_score=exclusion.overall_confidence,
                input_data={
                    "overall_confidence": exclusion.overall_confidence,
                    "threshold": ConfidenceThresholds.AUTO_APPROVAL_THRESHOLD,
                },
                output_data={"status": ExclusionStatus.AUTO_APPROVED.value},
                audit_explanation=(
                    f"Auto-approved due to high confidence: "
                    f"{exclusion.overall_confidence:.2f} >= "
                    f"{ConfidenceThresholds.AUTO_APPROVAL_THRESHOLD}"
                ),
            )

            session.add(audit_entry)
            session.add(exclusion)
            await session.flush()

            logger.info(f"Created audit entry {audit_entry.id} for auto-approval")
            return True

        return False

    @staticmethod
    async def approve_candidate(
        session: AsyncSession,
        exclusion_id: UUID,
        user_id: str,
        reason: str = None,
    ) -> ExclusionDB:
        """
        Approve an exclusion (human decision)

        Args:
            session: Database session
            exclusion_id: Exclusion ID to approve
            user_id: User approving
            reason: Optional reason for approval

        Returns:
            Updated exclusion

        Raises:
            ValueError: If exclusion not found or invalid state
        """
        # Fetch exclusion
        result = await session.execute(
            select(ExclusionDB).where(ExclusionDB.id == exclusion_id)
        )
        exclusion = result.scalar_one_or_none()

        if not exclusion:
            raise ValueError(f"Exclusion {exclusion_id} not found")

        if exclusion.status not in [
            ExclusionStatus.PENDING.value,
            ExclusionStatus.AUTO_APPROVED.value,
        ]:
            raise ValueError(
                f"Cannot approve exclusion in status: {exclusion.status}"
            )

        logger.info(f"Approving exclusion {exclusion_id} by {user_id}")

        # Update status
        old_status = exclusion.status
        exclusion.status = ExclusionStatus.APPROVED.value
        exclusion.reviewed_by = user_id
        exclusion.reviewed_at = datetime.utcnow()

        # Create audit log
        audit_entry = AuditLogDB(
            id=uuid4(),
            exclusion_id=exclusion_id,
            action="approve",
            user_id=user_id,
            input_data={"old_status": old_status, "reason": reason or ""},
            output_data={"new_status": ExclusionStatus.APPROVED.value},
            audit_explanation=f"Human approval by {user_id}. Reason: {reason or 'N/A'}",
        )

        session.add(audit_entry)
        session.add(exclusion)
        await session.flush()

        logger.info(f"Exclusion {exclusion_id} approved, audit entry {audit_entry.id}")
        return exclusion

    @staticmethod
    async def reject_candidate(
        session: AsyncSession,
        exclusion_id: UUID,
        user_id: str,
        reason: str,
    ) -> ExclusionDB:
        """
        Reject an exclusion (human decision)

        Args:
            session: Database session
            exclusion_id: Exclusion ID to reject
            user_id: User rejecting
            reason: Reason for rejection

        Returns:
            Updated exclusion

        Raises:
            ValueError: If exclusion not found or invalid state
        """
        # Fetch exclusion
        result = await session.execute(
            select(ExclusionDB).where(ExclusionDB.id == exclusion_id)
        )
        exclusion = result.scalar_one_or_none()

        if not exclusion:
            raise ValueError(f"Exclusion {exclusion_id} not found")

        if exclusion.status != ExclusionStatus.PENDING.value:
            raise ValueError(
                f"Cannot reject exclusion in status: {exclusion.status}"
            )

        logger.info(f"Rejecting exclusion {exclusion_id} by {user_id}: {reason}")

        # Update status
        exclusion.status = ExclusionStatus.REJECTED.value
        exclusion.reviewed_by = user_id
        exclusion.reviewed_at = datetime.utcnow()

        # Create audit log
        audit_entry = AuditLogDB(
            id=uuid4(),
            exclusion_id=exclusion_id,
            action="reject",
            user_id=user_id,
            input_data={"reason": reason},
            output_data={"new_status": ExclusionStatus.REJECTED.value},
            audit_explanation=f"Human rejection by {user_id}. Reason: {reason}",
        )

        session.add(audit_entry)
        session.add(exclusion)
        await session.flush()

        logger.info(f"Exclusion {exclusion_id} rejected, audit entry {audit_entry.id}")
        return exclusion

    @staticmethod
    async def override_candidate(
        session: AsyncSession,
        exclusion_id: UUID,
        user_id: str,
        new_status: str,
        override_reason: str,
        training_feedback: str = None,
    ) -> ExclusionDB:
        """
        Override previous decision with human judgment and capture training data

        Args:
            session: Database session
            exclusion_id: Exclusion ID to override
            user_id: User overriding (supervisor)
            new_status: New status (approved|rejected)
            override_reason: Reason for override
            training_feedback: Feedback for model improvement

        Returns:
            Updated exclusion

        Raises:
            ValueError: If exclusion not found or invalid state
        """
        # Fetch exclusion
        result = await session.execute(
            select(ExclusionDB).where(ExclusionDB.id == exclusion_id)
        )
        exclusion = result.scalar_one_or_none()

        if not exclusion:
            raise ValueError(f"Exclusion {exclusion_id} not found")

        if new_status not in [ExclusionStatus.APPROVED.value, ExclusionStatus.REJECTED.value]:
            raise ValueError(f"Invalid new_status: {new_status}")

        logger.info(
            f"Override exclusion {exclusion_id} by {user_id}: "
            f"{exclusion.status} → {new_status}"
        )

        # Record override in approval_overrides table
        old_status = exclusion.status
        override_record = ApprovalOverrideDB(
            id=uuid4(),
            exclusion_id=exclusion_id,
            original_status=old_status,
            new_status=new_status,
            approved_by=user_id,
            override_reason=override_reason,
            training_feedback=training_feedback or "",
        )

        # Update exclusion status
        exclusion.status = new_status
        exclusion.reviewed_by = user_id
        exclusion.reviewed_at = datetime.utcnow()

        # Create audit log entry
        audit_entry = AuditLogDB(
            id=uuid4(),
            exclusion_id=exclusion_id,
            action="override",
            user_id=user_id,
            input_data={"old_status": old_status, "override_reason": override_reason},
            output_data={"new_status": new_status},
            audit_explanation=(
                f"Override by {user_id}: {old_status} → {new_status}. "
                f"Reason: {override_reason}. "
                f"Training feedback: {training_feedback or 'N/A'}"
            ),
        )

        session.add(override_record)
        session.add(audit_entry)
        session.add(exclusion)
        await session.flush()

        logger.info(
            f"Override recorded {override_record.id}, audit entry {audit_entry.id}"
        )
        return exclusion

    @staticmethod
    async def mark_synced(
        session: AsyncSession,
        exclusion_id: UUID,
        sync_status: str = "synced",
    ) -> ExclusionDB:
        """
        Mark exclusion as synced to Aladdin API

        Args:
            session: Database session
            exclusion_id: Exclusion ID to mark synced
            sync_status: Status value (usually 'synced')

        Returns:
            Updated exclusion

        Raises:
            ValueError: If exclusion not found or not approved
        """
        # Fetch exclusion
        result = await session.execute(
            select(ExclusionDB).where(ExclusionDB.id == exclusion_id)
        )
        exclusion = result.scalar_one_or_none()

        if not exclusion:
            raise ValueError(f"Exclusion {exclusion_id} not found")

        if exclusion.status not in [
            ExclusionStatus.APPROVED.value,
            ExclusionStatus.AUTO_APPROVED.value,
        ]:
            raise ValueError(
                f"Cannot sync exclusion in status: {exclusion.status}. "
                f"Must be approved or auto_approved."
            )

        logger.info(f"Marking exclusion {exclusion_id} as {sync_status}")

        # Update status
        old_status = exclusion.status
        exclusion.status = sync_status
        exclusion.updated_at = datetime.utcnow()

        # Create audit log
        audit_entry = AuditLogDB(
            id=uuid4(),
            exclusion_id=exclusion_id,
            action="sync",
            input_data={"aladdin_id": exclusion.aladdin_match.get("aladdin_id") if isinstance(exclusion.aladdin_match, dict) else ""},
            output_data={"new_status": sync_status},
            audit_explanation=f"Synced to Aladdin API from status: {old_status}",
        )

        session.add(audit_entry)
        session.add(exclusion)
        await session.flush()

        logger.info(f"Exclusion {exclusion_id} marked as {sync_status}")
        return exclusion

    @staticmethod
    async def get_audit_trail(
        session: AsyncSession,
        exclusion_id: UUID,
    ) -> list:
        """
        Get complete immutable audit trail for an exclusion

        Args:
            session: Database session
            exclusion_id: Exclusion ID

        Returns:
            List of AuditLogDB entries in chronological order
        """
        result = await session.execute(
            select(AuditLogDB)
            .where(AuditLogDB.exclusion_id == exclusion_id)
            .order_by(AuditLogDB.timestamp)
        )
        return result.scalars().all()
