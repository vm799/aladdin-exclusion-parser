"""
Dashboard API - REST Endpoints for Exclusion Management

Implements:
- POST /exclusions - Create from orchestrator
- GET /exclusions - List with pagination & filters
- GET /exclusions/{id} - Get single
- PATCH /exclusions/{id}/approve - Human approval
- PATCH /exclusions/{id}/reject - Human rejection
- PATCH /exclusions/{id}/override - Human override with training data
- GET /audit/{id} - Get audit trail
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.approval_service import ApprovalService
from backend.database import AuditLogDB, ExclusionDB, get_async_session
from backend.models import (
    ApprovalRequest,
    AuditLogResponse,
    ExclusionCandidateCreate,
    ExclusionCandidateResponse,
    OverrideRequest,
    PaginatedResponse,
    RejectRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/exclusions", response_model=ExclusionCandidateResponse, status_code=201)
async def create_exclusion(
    candidate: ExclusionCandidateCreate,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Create new exclusion from orchestrator output

    Process:
    1. Validate input (Pydantic)
    2. Store in database
    3. Create audit log entries (extract, resolve, match, aggregate)
    4. Auto-approve if confidence >= 0.90
    5. Return created exclusion

    Args:
        candidate: ExclusionCandidate from orchestrator
        session: Database session

    Returns:
        Created exclusion with full metadata
    """
    try:
        # Create exclusion record
        exclusion = ExclusionDB(
            source_doc=candidate.source_doc,
            company_name=candidate.company_name,
            extracted_company=candidate.extracted_company,
            normalized_company=candidate.normalized_company,
            aladdin_match=candidate.aladdin_match,
            overall_confidence=candidate.overall_confidence,
            ocr_confidence=candidate.ocr_confidence,
            entity_resolution_confidence=candidate.entity_resolution_confidence,
            aladdin_match_confidence=candidate.aladdin_match_confidence,
            confidence_breakdown=candidate.confidence_breakdown,
            agent_version=candidate.agent_version,
            processing_time_ms=candidate.processing_time_ms,
            status="pending",  # Will be updated by auto_approve_if_qualified
        )

        session.add(exclusion)
        await session.flush()  # Get ID before creating audit logs

        # Create audit log entries for each agent
        audit_entries = [
            AuditLogDB(
                exclusion_id=exclusion.id,
                action="extract",
                agent_name="ExtractionAgent",
                input_data={"source_doc": candidate.source_doc},
                output_data={
                    "extracted_company": candidate.extracted_company,
                    "ocr_confidence": candidate.ocr_confidence,
                },
                confidence_score=candidate.ocr_confidence,
                audit_explanation="Company extracted from document via OCR/parsing",
            ),
            AuditLogDB(
                exclusion_id=exclusion.id,
                action="resolve",
                agent_name="EntityResolverAgent",
                input_data={"raw_name": candidate.extracted_company.get("raw_name", "")},
                output_data={
                    "canonical_name": candidate.normalized_company.get("canonical_name", ""),
                    "normalization_confidence": candidate.entity_resolution_confidence,
                },
                confidence_score=candidate.entity_resolution_confidence,
                audit_explanation="Company name normalized to canonical form",
            ),
            AuditLogDB(
                exclusion_id=exclusion.id,
                action="match",
                agent_name="AladdinClientAgent",
                input_data={
                    "canonical_name": candidate.normalized_company.get("canonical_name", "")
                },
                output_data={
                    "aladdin_id": candidate.aladdin_match.get("aladdin_id"),
                    "match_confidence": candidate.aladdin_match_confidence,
                },
                confidence_score=candidate.aladdin_match_confidence,
                audit_explanation=(
                    f"Matched to Aladdin via {candidate.aladdin_match.get('match_type', 'unknown')} match"
                ),
            ),
            AuditLogDB(
                exclusion_id=exclusion.id,
                action="aggregate",
                agent_name="ConfidenceAggregatorAgent",
                input_data={
                    "ocr_confidence": candidate.ocr_confidence,
                    "entity_confidence": candidate.entity_resolution_confidence,
                    "aladdin_confidence": candidate.aladdin_match_confidence,
                },
                output_data={
                    "overall_confidence": candidate.overall_confidence,
                    "confidence_breakdown": candidate.confidence_breakdown,
                },
                confidence_score=candidate.overall_confidence,
                audit_explanation=(
                    f"Confidence aggregated: "
                    f"({candidate.ocr_confidence:.2f} * 0.20) + "
                    f"({candidate.entity_resolution_confidence:.2f} * 0.30) + "
                    f"({candidate.aladdin_match_confidence:.2f} * 0.50) = "
                    f"{candidate.overall_confidence:.2f}"
                ),
            ),
        ]

        session.add_all(audit_entries)
        await session.flush()

        logger.info(
            f"Created exclusion {exclusion.id} for {candidate.company_name} "
            f"with confidence {candidate.overall_confidence:.2f}"
        )

        # Check for auto-approval
        await ApprovalService.auto_approve_if_qualified(session, exclusion)

        # Commit transaction
        await session.commit()

        # Refresh to get updated status
        await session.refresh(exclusion)

        logger.info(f"Exclusion {exclusion.id} created with status: {exclusion.status}")
        return ExclusionCandidateResponse.from_orm(exclusion)

    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to create exclusion: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to create exclusion: {str(e)}")


@router.get("/exclusions", response_model=PaginatedResponse)
async def list_exclusions(
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_async_session),
):
    """
    List exclusions with pagination and filtering

    Args:
        status: Filter by status (optional)
        skip: Number of records to skip (pagination)
        limit: Maximum records to return
        session: Database session

    Returns:
        Paginated list of exclusions
    """
    try:
        # Build query
        query = select(ExclusionDB)
        if status:
            query = query.where(ExclusionDB.status == status)

        # Get total count
        count_result = await session.execute(
            select(func.count(ExclusionDB.id)).where(
                ExclusionDB.status == status if status else True
            )
        )
        total = count_result.scalar()

        # Get paginated results
        query = query.order_by(ExclusionDB.created_at.desc()).offset(skip).limit(limit)
        result = await session.execute(query)
        exclusions = result.scalars().all()

        logger.info(
            f"Listed {len(exclusions)} exclusions (skip={skip}, limit={limit}, "
            f"status={status or 'all'}, total={total})"
        )

        return PaginatedResponse(
            items=[ExclusionCandidateResponse.from_orm(e) for e in exclusions],
            total=total,
            skip=skip,
            limit=limit,
        )

    except Exception as e:
        logger.error(f"Failed to list exclusions: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list exclusions")


@router.get("/exclusions/{exclusion_id}", response_model=ExclusionCandidateResponse)
async def get_exclusion(
    exclusion_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get single exclusion by ID

    Args:
        exclusion_id: Exclusion UUID
        session: Database session

    Returns:
        Exclusion with full metadata
    """
    try:
        result = await session.execute(
            select(ExclusionDB).where(ExclusionDB.id == exclusion_id)
        )
        exclusion = result.scalar_one_or_none()

        if not exclusion:
            raise HTTPException(status_code=404, detail=f"Exclusion {exclusion_id} not found")

        return ExclusionCandidateResponse.from_orm(exclusion)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get exclusion {exclusion_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get exclusion")


@router.patch("/exclusions/{exclusion_id}/approve", response_model=ExclusionCandidateResponse)
async def approve_exclusion(
    exclusion_id: UUID,
    request: ApprovalRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Approve an exclusion (human decision)

    Args:
        exclusion_id: Exclusion UUID
        request: Approval request with user_id and reason
        session: Database session

    Returns:
        Updated exclusion with status=approved
    """
    try:
        result = await session.execute(
            select(ExclusionDB).where(ExclusionDB.id == exclusion_id)
        )
        exclusion = result.scalar_one_or_none()

        if not exclusion:
            raise HTTPException(status_code=404, detail=f"Exclusion {exclusion_id} not found")

        # Approve via service
        exclusion = await ApprovalService.approve_candidate(
            session=session,
            exclusion_id=exclusion_id,
            user_id=request.user_id,
            reason=request.reason,
        )

        await session.commit()
        await session.refresh(exclusion)

        logger.info(f"Exclusion {exclusion_id} approved by {request.user_id}")
        return ExclusionCandidateResponse.from_orm(exclusion)

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error approving {exclusion_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to approve exclusion {exclusion_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to approve exclusion")


@router.patch("/exclusions/{exclusion_id}/reject", response_model=ExclusionCandidateResponse)
async def reject_exclusion(
    exclusion_id: UUID,
    request: RejectRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Reject an exclusion (human decision)

    Args:
        exclusion_id: Exclusion UUID
        request: Rejection request with user_id and reason
        session: Database session

    Returns:
        Updated exclusion with status=rejected
    """
    try:
        result = await session.execute(
            select(ExclusionDB).where(ExclusionDB.id == exclusion_id)
        )
        exclusion = result.scalar_one_or_none()

        if not exclusion:
            raise HTTPException(status_code=404, detail=f"Exclusion {exclusion_id} not found")

        # Reject via service
        exclusion = await ApprovalService.reject_candidate(
            session=session,
            exclusion_id=exclusion_id,
            user_id=request.user_id,
            reason=request.reason,
        )

        await session.commit()
        await session.refresh(exclusion)

        logger.info(f"Exclusion {exclusion_id} rejected by {request.user_id}")
        return ExclusionCandidateResponse.from_orm(exclusion)

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error rejecting {exclusion_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to reject exclusion {exclusion_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to reject exclusion")


@router.patch("/exclusions/{exclusion_id}/override", response_model=ExclusionCandidateResponse)
async def override_exclusion(
    exclusion_id: UUID,
    request: OverrideRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Override previous decision with human judgment and training data

    Args:
        exclusion_id: Exclusion UUID
        request: Override request with user_id, new_status, reason, and training_feedback
        session: Database session

    Returns:
        Updated exclusion with new status
    """
    try:
        result = await session.execute(
            select(ExclusionDB).where(ExclusionDB.id == exclusion_id)
        )
        exclusion = result.scalar_one_or_none()

        if not exclusion:
            raise HTTPException(status_code=404, detail=f"Exclusion {exclusion_id} not found")

        # Override via service
        exclusion = await ApprovalService.override_candidate(
            session=session,
            exclusion_id=exclusion_id,
            user_id=request.user_id,
            new_status=request.new_status,
            override_reason=request.override_reason,
            training_feedback=request.training_feedback,
        )

        await session.commit()
        await session.refresh(exclusion)

        logger.info(
            f"Exclusion {exclusion_id} overridden by {request.user_id} "
            f"to status: {request.new_status}"
        )
        return ExclusionCandidateResponse.from_orm(exclusion)

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error overriding {exclusion_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to override exclusion {exclusion_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to override exclusion")


@router.get("/audit/{exclusion_id}", response_model=List[AuditLogResponse])
async def get_audit_trail(
    exclusion_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get complete immutable audit trail for an exclusion

    Args:
        exclusion_id: Exclusion UUID
        session: Database session

    Returns:
        List of audit log entries in chronological order
    """
    try:
        # Verify exclusion exists
        result = await session.execute(
            select(ExclusionDB).where(ExclusionDB.id == exclusion_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Exclusion {exclusion_id} not found")

        # Get audit trail
        audit_entries = await ApprovalService.get_audit_trail(session, exclusion_id)

        logger.info(f"Retrieved {len(audit_entries)} audit entries for {exclusion_id}")
        return [AuditLogResponse.from_orm(entry) for entry in audit_entries]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get audit trail for {exclusion_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get audit trail")
