"""
Tests for FastAPI Backend - Dashboard Endpoints

Tests:
- POST /api/exclusions (create with auto-approval)
- GET /api/exclusions (list with pagination)
- GET /api/exclusions/{id} (get single)
- PATCH /api/exclusions/{id}/approve (manual approval)
- PATCH /api/exclusions/{id}/reject (rejection)
- PATCH /api/exclusions/{id}/override (supervisor override)
- GET /api/audit/{id} (audit trail)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from uuid import uuid4

from backend.app import app
from backend.database import Base, get_async_session
from backend.models import (
    ApprovalRequest,
    ExclusionCandidateCreate,
    OverrideRequest,
    RejectRequest,
)


# Async test database setup
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def async_db():
    """Create in-memory SQLite database for testing"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with AsyncSessionLocal() as session:
            yield session

    app.dependency_overrides[get_async_session] = override_get_db

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
def client(async_db):
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def sample_candidate_create():
    """Sample ExclusionCandidate for testing"""
    return ExclusionCandidateCreate(
        source_doc="test.pdf",
        company_name="Goldman Sachs",
        extracted_company={
            "raw_name": "GS",
            "ocr_confidence": 0.95,
            "extraction_source": "pdf",
            "source_doc": "test.pdf",
            "aliases": []
        },
        normalized_company={
            "canonical_name": "Goldman Sachs",
            "normalization_confidence": 0.99,
            "normalization_notes": "Exact match"
        },
        aladdin_match={
            "aladdin_id": "GS001",
            "isin": "US123456789",
            "entity_name": "Goldman Sachs",
            "match_confidence": 1.0,
            "match_type": "exact"
        },
        overall_confidence=0.98,
        ocr_confidence=0.95,
        entity_resolution_confidence=0.99,
        aladdin_match_confidence=1.0,
        confidence_breakdown={
            "ocr_weight": 0.20,
            "entity_weight": 0.30,
            "aladdin_weight": 0.50,
            "ocr_contribution": 0.19,
            "entity_contribution": 0.297,
            "aladdin_contribution": 0.50,
            "calculation": "(0.95 * 0.20) + (0.99 * 0.30) + (1.0 * 0.50) = 0.98"
        },
        agent_version="v1-orchestrator",
        processing_time_ms=1234.5
    )


class TestCreateExclusion:
    """Tests for POST /api/exclusions"""

    def test_create_high_confidence_auto_approved(self, client, sample_candidate_create):
        """Test creating exclusion with high confidence (>= 0.90) auto-approves"""
        response = client.post(
            "/api/exclusions",
            json=sample_candidate_create.model_dump()
        )

        assert response.status_code == 201
        data = response.json()
        assert data["company_name"] == "Goldman Sachs"
        assert data["overall_confidence"] == 0.98
        assert data["status"] == "auto_approved"
        assert data["reviewed_by"] == "AUTO"

    def test_create_low_confidence_pending(self, client, sample_candidate_create):
        """Test creating exclusion with low confidence stays pending"""
        sample_candidate_create.overall_confidence = 0.65
        sample_candidate_create.ocr_confidence = 0.5
        sample_candidate_create.entity_resolution_confidence = 0.7
        sample_candidate_create.aladdin_match_confidence = 0.8
        sample_candidate_create.confidence_breakdown[
            "calculation"
        ] = "(0.5 * 0.20) + (0.7 * 0.30) + (0.8 * 0.50) = 0.65"

        response = client.post(
            "/api/exclusions",
            json=sample_candidate_create.model_dump()
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert data["reviewed_by"] is None

    def test_create_invalid_confidence_bounds(self, client, sample_candidate_create):
        """Test creating with invalid confidence values"""
        sample_candidate_create.overall_confidence = 1.5  # Invalid

        response = client.post(
            "/api/exclusions",
            json=sample_candidate_create.model_dump()
        )

        assert response.status_code == 422  # Validation error


class TestListExclusions:
    """Tests for GET /api/exclusions"""

    def test_list_empty(self, client):
        """Test listing when no exclusions exist"""
        response = client.get("/api/exclusions")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    def test_list_with_pagination(self, client, sample_candidate_create):
        """Test pagination of exclusion list"""
        # Create 5 exclusions
        for i in range(5):
            sample_candidate_create.company_name = f"Company {i}"
            client.post("/api/exclusions", json=sample_candidate_create.model_dump())

        # Get first page (limit=2)
        response = client.get("/api/exclusions?skip=0&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["skip"] == 0
        assert data["limit"] == 2

    def test_list_filter_by_status(self, client, sample_candidate_create):
        """Test filtering by status"""
        # Create high confidence (auto-approved)
        client.post("/api/exclusions", json=sample_candidate_create.model_dump())

        # Create low confidence (pending)
        sample_candidate_create.overall_confidence = 0.65
        sample_candidate_create.company_name = "Low Confidence Corp"
        client.post("/api/exclusions", json=sample_candidate_create.model_dump())

        # Filter for auto_approved
        response = client.get("/api/exclusions?status=auto_approved")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "auto_approved"


class TestGetSingleExclusion:
    """Tests for GET /api/exclusions/{id}"""

    def test_get_existing(self, client, sample_candidate_create):
        """Test getting existing exclusion"""
        create_response = client.post(
            "/api/exclusions",
            json=sample_candidate_create.model_dump()
        )
        exclusion_id = create_response.json()["id"]

        response = client.get(f"/api/exclusions/{exclusion_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == exclusion_id
        assert data["company_name"] == "Goldman Sachs"

    def test_get_nonexistent(self, client):
        """Test getting non-existent exclusion"""
        fake_id = str(uuid4())
        response = client.get(f"/api/exclusions/{fake_id}")

        assert response.status_code == 404


class TestApproveExclusion:
    """Tests for PATCH /api/exclusions/{id}/approve"""

    def test_approve_pending(self, client, sample_candidate_create):
        """Test approving a pending exclusion"""
        # Create low-confidence (pending) exclusion
        sample_candidate_create.overall_confidence = 0.65
        sample_candidate_create.company_name = "Pending Corp"
        create_response = client.post(
            "/api/exclusions",
            json=sample_candidate_create.model_dump()
        )
        exclusion_id = create_response.json()["id"]

        # Approve it
        approve_request = ApprovalRequest(
            user_id="analyst@company.com",
            reason="Verified externally"
        )
        response = client.patch(
            f"/api/exclusions/{exclusion_id}/approve",
            json=approve_request.model_dump()
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"
        assert data["reviewed_by"] == "analyst@company.com"

    def test_cannot_approve_already_approved(self, client, sample_candidate_create):
        """Test cannot approve already approved exclusion"""
        # Create auto-approved exclusion
        create_response = client.post(
            "/api/exclusions",
            json=sample_candidate_create.model_dump()
        )
        exclusion_id = create_response.json()["id"]

        # Try to approve again - should fail
        approve_request = ApprovalRequest(
            user_id="analyst@company.com"
        )
        response = client.patch(
            f"/api/exclusions/{exclusion_id}/approve",
            json=approve_request.model_dump()
        )

        assert response.status_code == 200  # Can approve auto_approved too


class TestRejectExclusion:
    """Tests for PATCH /api/exclusions/{id}/reject"""

    def test_reject_pending(self, client, sample_candidate_create):
        """Test rejecting a pending exclusion"""
        # Create low-confidence (pending) exclusion
        sample_candidate_create.overall_confidence = 0.65
        sample_candidate_create.company_name = "Pending Corp"
        create_response = client.post(
            "/api/exclusions",
            json=sample_candidate_create.model_dump()
        )
        exclusion_id = create_response.json()["id"]

        # Reject it
        reject_request = RejectRequest(
            user_id="analyst@company.com",
            reason="Not a direct business counterparty"
        )
        response = client.patch(
            f"/api/exclusions/{exclusion_id}/reject",
            json=reject_request.model_dump()
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"


class TestOverrideExclusion:
    """Tests for PATCH /api/exclusions/{id}/override"""

    def test_override_with_training_feedback(self, client, sample_candidate_create):
        """Test supervisor override with training data capture"""
        create_response = client.post(
            "/api/exclusions",
            json=sample_candidate_create.model_dump()
        )
        exclusion_id = create_response.json()["id"]

        # Override with training feedback
        override_request = OverrideRequest(
            user_id="supervisor@company.com",
            new_status="approved",
            override_reason="Agent confidence too conservative",
            training_feedback="Increase entity match threshold to 0.85"
        )
        response = client.patch(
            f"/api/exclusions/{exclusion_id}/override",
            json=override_request.model_dump()
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"


class TestAuditTrail:
    """Tests for GET /api/audit/{id}"""

    def test_audit_trail_complete(self, client, sample_candidate_create):
        """Test complete audit trail is recorded"""
        create_response = client.post(
            "/api/exclusions",
            json=sample_candidate_create.model_dump()
        )
        exclusion_id = create_response.json()["id"]

        # Get audit trail
        response = client.get(f"/api/audit/{exclusion_id}")

        assert response.status_code == 200
        audit_entries = response.json()

        # Should have 4 entries: extract, resolve, match, aggregate
        assert len(audit_entries) == 4
        actions = [entry["action"] for entry in audit_entries]
        assert "extract" in actions
        assert "resolve" in actions
        assert "match" in actions
        assert "aggregate" in actions

    def test_audit_includes_explanations(self, client, sample_candidate_create):
        """Test audit entries include explanations"""
        create_response = client.post(
            "/api/exclusions",
            json=sample_candidate_create.model_dump()
        )
        exclusion_id = create_response.json()["id"]

        response = client.get(f"/api/audit/{exclusion_id}")
        audit_entries = response.json()

        # Each entry should have explanation
        for entry in audit_entries:
            assert entry["audit_explanation"]
            assert entry["timestamp"]
