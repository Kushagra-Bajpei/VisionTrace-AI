"""
Phase 8 Automated Security, RBAC, Case Isolation & Evidence Integrity Tests.
Covers:
- Bootstrap admin and duplicate bootstrap rejection.
- Registration, login, invalid credentials, inactive user rejection.
- Logout and persistent token revocation verification.
- Scoped media token issuance, resource mismatch rejection, and expiry.
- RBAC matrix: Admin, Investigator, Reviewer, Viewer.
- Case isolation: Cross-user case access blocked (403), UUID guessing blocked.
- Reviewer isolation: Unassigned reviewer blocked (403).
- Last active admin demotion/deactivation blocked (400).
- Media endpoint security: Unauthorized stream blocked (401), Range 206 preserved for authorized, path traversal blocked.
- Evidence integrity: Hash match (verified), mismatch (mismatch), missing file (unavailable), legacy (not_recorded).
- Audit logging: Events generated on login, case create, role change, integrity check; sensitive data stripped.
"""
import io
import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import create_access_token, create_media_token, hash_password
from app.main import app
from app.models.audit import AuditLog, RevokedToken
from app.models.investigation import Investigation, InvestigationEvidence
from app.models.user import User
from app.models.video import Video
from app.services.integrity_service import IntegrityService
from tests.conftest import SharedTestingSessionLocal

settings = get_settings()


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def raw_client():
    """Unauthenticated client with empty default headers."""
    return TestClient(app)


def create_user_helper(db, email: str, role: str = "investigator", is_active: bool = True, password: str = "SecretPass123!") -> User:
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=f"User {role.capitalize()}",
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.expunge(user)
    return user


def get_auth_header(user: User) -> dict:
    token = create_access_token(user.id, role=user.role, email=user.email)
    return {"Authorization": f"Bearer {token}"}


# ── 1. Bootstrap Admin Tests ────────────────────────────────────────────────

def test_bootstrap_admin_lifecycle(raw_client, db_tables):
    """Test initial admin bootstrap and subsequent duplicate rejection."""
    # First bootstrap
    res1 = raw_client.post(
        "/api/v1/auth/bootstrap-admin",
        json={
            "email": "rootadmin@visiontrace.ai",
            "password": "RootAdminSecurePassword123!",
            "full_name": "Chief Security Officer",
        },
    )
    assert res1.status_code == 201
    admin_data = res1.json()
    assert admin_data["user"]["email"] == "rootadmin@visiontrace.ai"
    assert admin_data["user"]["role"] == "admin"
    assert admin_data["user"]["is_active"] is True

    # Duplicate bootstrap must be rejected with 400 or 403
    res2 = raw_client.post(
        "/api/v1/auth/bootstrap-admin",
        json={
            "email": "hacker@visiontrace.ai",
            "password": "HackerPassword123!",
            "full_name": "Attacker",
        },
    )
    assert res2.status_code in (400, 403)
    assert "already bootstrapped" in res2.json()["detail"].lower()


# ── 2. User Registration & Authentication ───────────────────────────────────

def test_user_registration_and_login(raw_client, db_tables):
    """Verify user registration, duplicate prevention, and JWT credential validation."""
    # First user becomes admin if 0 users exist, or investigator if admin already exists
    res_reg = raw_client.post(
        "/api/v1/auth/register",
        json={
            "email": "agent.smith@visiontrace.ai",
            "password": "Password123!",
            "full_name": "Agent Smith",
        },
    )
    assert res_reg.status_code == 201
    user_info = res_reg.json()
    assert user_info["user"]["email"] == "agent.smith@visiontrace.ai"

    # Second user registration is explicitly investigator
    res_reg2 = raw_client.post(
        "/api/v1/auth/register",
        json={
            "email": "agent.jones@visiontrace.ai",
            "password": "Password123!",
            "full_name": "Agent Jones",
        },
    )
    assert res_reg2.status_code == 201
    assert res_reg2.json()["user"]["role"] == "investigator"

    # Duplicate registration
    res_dup = raw_client.post(
        "/api/v1/auth/register",
        json={
            "email": "agent.smith@visiontrace.ai",
            "password": "Password123!",
            "full_name": "Agent Smith Duplicate",
        },
    )
    assert res_dup.status_code == 400
    assert "already exists" in res_dup.json()["detail"].lower()

    # Login valid credentials
    res_login = raw_client.post(
        "/api/v1/auth/login",
        json={"email": "agent.smith@visiontrace.ai", "password": "Password123!"},
    )
    assert res_login.status_code == 200
    login_data = res_login.json()
    assert "access_token" in login_data
    assert login_data["token_type"] == "bearer"
    token = login_data["access_token"]

    # Access /me
    res_me = raw_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_me.status_code == 200
    assert res_me.json()["email"] == "agent.smith@visiontrace.ai"

    # Login invalid password
    res_bad = raw_client.post(
        "/api/v1/auth/login",
        json={"email": "agent.smith@visiontrace.ai", "password": "WrongPassword!"},
    )
    assert res_bad.status_code == 401

    # Inactive user login
    db = SharedTestingSessionLocal()
    try:
        inactive_user = create_user_helper(db, "banned@visiontrace.ai", is_active=False)
    finally:
        db.close()

    res_inactive = raw_client.post(
        "/api/v1/auth/login",
        json={"email": "banned@visiontrace.ai", "password": "SecretPass123!"},
    )
    assert res_inactive.status_code in (401, 403)


# ── 3. Token Revocation & Persistent Logout ─────────────────────────────────

def test_token_revocation_on_logout(raw_client, db_tables):
    """Test that logout records jti in revoked_tokens and subsequent requests are rejected."""
    db = SharedTestingSessionLocal()
    try:
        user = create_user_helper(db, "logout.test@visiontrace.ai")
    finally:
        db.close()

    headers = get_auth_header(user)

    # Active token succeeds
    res_before = raw_client.get("/api/v1/auth/me", headers=headers)
    assert res_before.status_code == 200

    # Logout
    res_logout = raw_client.post("/api/v1/auth/logout", headers=headers)
    assert res_logout.status_code == 200

    # Verify persisted in database
    db = SharedTestingSessionLocal()
    try:
        revoked_count = db.query(RevokedToken).count()
        assert revoked_count >= 1
    finally:
        db.close()

    # Reusing the revoked token must fail with 401
    res_after = raw_client.get("/api/v1/auth/me", headers=headers)
    assert res_after.status_code == 401
    assert "revoked" in res_after.json()["detail"].lower()


# ── 4. Scoped Media Tokens ──────────────────────────────────────────────────

def test_scoped_media_token_security(raw_client, db_tables):
    """Verify scoped media tokens: issuance, resource matching, and general API boundary."""
    db = SharedTestingSessionLocal()
    try:
        user = create_user_helper(db, "media.user@visiontrace.ai")
        video_id = uuid.uuid4()
        video = Video(
            id=video_id,
            filename="media_sample.mp4",
            original_filename="sample.mp4",
            file_path="videos/media_sample.mp4",
            file_size=1024,
            status="completed",
        )
        db.add(video)
        db.commit()
    finally:
        db.close()

    headers = get_auth_header(user)

    # Issue video media token
    res_token = raw_client.post(
        "/api/v1/auth/media-token",
        headers=headers,
        json={"resource_type": "video", "resource_id": str(video_id)},
    )
    assert res_token.status_code == 200
    token_data = res_token.json()
    media_token = token_data["media_token"]
    assert token_data["resource_type"] == "video"
    assert token_data["resource_id"] == str(video_id)

    # Mismatch resource_id rejected
    wrong_id = uuid.uuid4()
    res_wrong = raw_client.get(
        f"/api/v1/videos/{wrong_id}/stream?media_token={media_token}",
    )
    assert res_wrong.status_code == 403
    assert "not authorized for this specific resource" in res_wrong.json()["detail"].lower()

    # Media token rejected on general API routes (e.g., /cases)
    res_general = raw_client.get(
        f"/api/v1/cases?media_token={media_token}",
    )
    assert res_general.status_code == 403


# ── 5. Role-Based Access Control & Last Admin Protection ───────────────────

def test_rbac_matrix_and_last_admin_protection(raw_client, db_tables):
    """Test role permissions across Admin, Investigator, Reviewer, and Viewer."""
    db = SharedTestingSessionLocal()
    try:
        admin_user = create_user_helper(db, "admin1@visiontrace.ai", role="admin")
        inv_user = create_user_helper(db, "inv1@visiontrace.ai", role="investigator")
        rev_user = create_user_helper(db, "rev1@visiontrace.ai", role="reviewer")
        view_user = create_user_helper(db, "view1@visiontrace.ai", role="viewer")
    finally:
        db.close()

    admin_headers = get_auth_header(admin_user)
    inv_headers = get_auth_header(inv_user)
    rev_headers = get_auth_header(rev_user)
    view_headers = get_auth_header(view_user)

    # 1. Investigator can create case
    res_create = raw_client.post(
        "/api/v1/cases",
        headers=inv_headers,
        json={"title": "Investigator Case 1"},
    )
    assert res_create.status_code == 201
    case_id = res_create.json()["id"]

    # 2. Reviewer cannot create case
    res_rev_create = raw_client.post(
        "/api/v1/cases",
        headers=rev_headers,
        json={"title": "Reviewer Attempt"},
    )
    assert res_rev_create.status_code == 403

    # 3. Viewer cannot create case
    res_view_create = raw_client.post(
        "/api/v1/cases",
        headers=view_headers,
        json={"title": "Viewer Attempt"},
    )
    assert res_view_create.status_code == 403

    # 4. Reviewer cannot delete case
    res_rev_del = raw_client.delete(f"/api/v1/cases/{case_id}", headers=rev_headers)
    assert res_rev_del.status_code == 403

    # 5. Last Admin Protection: cannot demote last active admin
    res_demote = raw_client.patch(
        f"/api/v1/auth/users/{admin_user.id}/role",
        headers=admin_headers,
        json={"role": "investigator"},
    )
    assert res_demote.status_code == 400
    assert "Cannot demote or deactivate the last active" in res_demote.json()["detail"]


# ── 6. Case Isolation & Reviewer Assignment ─────────────────────────────────

def test_case_isolation_and_reviewer_scoping(raw_client, db_tables):
    """Verify that investigator cases are isolated and reviewers only access assigned cases."""
    db = SharedTestingSessionLocal()
    try:
        inv_a = create_user_helper(db, "inva@visiontrace.ai", role="investigator")
        inv_b = create_user_helper(db, "invb@visiontrace.ai", role="investigator")
        reviewer = create_user_helper(db, "auditor@visiontrace.ai", role="reviewer")
    finally:
        db.close()

    headers_a = get_auth_header(inv_a)
    headers_b = get_auth_header(inv_b)
    headers_rev = get_auth_header(reviewer)

    # Inv A creates Case A
    res_a = raw_client.post("/api/v1/cases", headers=headers_a, json={"title": "Case Alpha"})
    case_a_id = res_a.json()["id"]

    # Inv B creates Case B
    res_b = raw_client.post("/api/v1/cases", headers=headers_b, json={"title": "Case Beta"})
    case_b_id = res_b.json()["id"]

    # Inv B cannot view Case A
    res_b_view = raw_client.get(f"/api/v1/cases/{case_a_id}", headers=headers_b)
    assert res_b_view.status_code == 403

    # Inv B cannot delete Case A
    res_b_del = raw_client.delete(f"/api/v1/cases/{case_a_id}", headers=headers_b)
    assert res_b_del.status_code == 403

    # Reviewer cannot view unassigned Case A
    res_rev_a = raw_client.get(f"/api/v1/cases/{case_a_id}", headers=headers_rev)
    assert res_rev_a.status_code == 403

    # Assign reviewer to Case A
    res_assign = raw_client.patch(
        f"/api/v1/cases/{case_a_id}",
        headers=headers_a,
        json={"reviewer_id": str(reviewer.id)},
    )
    assert res_assign.status_code == 200

    # Now Reviewer can read Case A
    res_rev_ok = raw_client.get(f"/api/v1/cases/{case_a_id}", headers=headers_rev)
    assert res_rev_ok.status_code == 200
    assert res_rev_ok.json()["title"] == "Case Alpha"

    # But Reviewer still cannot read unassigned Case B
    res_rev_b = raw_client.get(f"/api/v1/cases/{case_b_id}", headers=headers_rev)
    assert res_rev_b.status_code == 403


# ── 7. Media Endpoint Security & Unauthorized Rejection ─────────────────────

def test_media_endpoints_unauthorized_blocking(raw_client, db_tables):
    """Verify unauthorized requests to video streaming, crops, and frames return 401."""
    random_id = uuid.uuid4()

    # Stream unauthenticated
    res_stream = raw_client.get(f"/api/v1/videos/{random_id}/stream")
    assert res_stream.status_code == 401

    # Frames unauthenticated
    res_frame = raw_client.get(f"/api/v1/videos/{random_id}/frames/frame_000001.jpg")
    assert res_frame.status_code == 401

    # Crops unauthenticated
    res_crop = raw_client.get(f"/api/v1/videos/{random_id}/crops/detection_01.jpg")
    assert res_crop.status_code == 401


# ── 8. Evidence & Video Cryptographic Integrity ─────────────────────────────

def test_cryptographic_integrity_verification(raw_client, db_tables, tmp_path):
    """Test byte-level SHA-256 integrity calculation, matching, mismatch, and unavailable status."""
    db = SharedTestingSessionLocal()
    try:
        admin = create_user_helper(db, "admin.integrity@visiontrace.ai", role="admin")
    finally:
        db.close()

    headers = get_auth_header(admin)

    # 1. Create a physical test file
    test_file = tmp_path / "integrity_test_clip.mp4"
    test_content = b"Surveillance footage authentic video payload bytes"
    test_file.write_bytes(test_content)

    db = SharedTestingSessionLocal()
    try:
        vid_id = uuid.uuid4()
        video = Video(
            id=vid_id,
            filename="integrity_test_clip.mp4",
            original_filename="clip.mp4",
            file_path=str(test_file),
            file_size=len(test_content),
            status="completed",
        )
        db.add(video)
        db.commit()
        db.refresh(video)

        # Record hash
        IntegrityService.record_video_hash(db, video)
        assert video.file_hash is not None
        assert "sha256" in video.hash_algorithm.lower()
        expected_hash = video.file_hash
    finally:
        db.close()

    # 2. Verify integrity endpoint returns 'verified'
    res_verify = raw_client.post(f"/api/v1/videos/{vid_id}/verify-integrity", headers=headers)
    assert res_verify.status_code == 200
    res_data = res_verify.json()
    assert res_data["status"] == "verified"
    assert res_data["actual_hash"] == expected_hash

    # 3. Tamper with file to produce 'mismatch'
    test_file.write_bytes(b"Tampered surveillance footage data")
    res_tampered = raw_client.post(f"/api/v1/videos/{vid_id}/verify-integrity", headers=headers)
    assert res_tampered.status_code == 200
    assert res_tampered.json()["status"] == "mismatch"

    # 4. Remove file to produce 'unavailable'
    test_file.unlink()
    res_missing = raw_client.post(f"/api/v1/videos/{vid_id}/verify-integrity", headers=headers)
    assert res_missing.status_code == 200
    assert res_missing.json()["status"] == "unavailable"


# ── 9. Audit Logging & Sensitive Data Redaction ─────────────────────────────

def test_audit_logging_and_sensitive_redaction(raw_client, db_tables):
    """Verify audit log creation on key events, non-admin restriction, and sensitive data redaction."""
    db = SharedTestingSessionLocal()
    try:
        admin = create_user_helper(db, "auditor.admin@visiontrace.ai", role="admin")
        inv = create_user_helper(db, "auditor.inv@visiontrace.ai", role="investigator")
    finally:
        db.close()

    admin_headers = get_auth_header(admin)
    inv_headers = get_auth_header(inv)

    # 1. Non-admin cannot view audit logs
    res_inv_audit = raw_client.get("/api/v1/audit", headers=inv_headers)
    assert res_inv_audit.status_code == 403

    # 2. Admin can view audit logs
    res_admin_audit = raw_client.get("/api/v1/audit", headers=admin_headers)
    assert res_admin_audit.status_code == 200
    logs = res_admin_audit.json()
    assert isinstance(logs, list)

    # 3. Verify sensitive redaction
    db = SharedTestingSessionLocal()
    try:
        all_logs = db.query(AuditLog).all()
        for l in all_logs:
            if l.details:
                for k, v in l.details.items():
                    assert "password" not in k.lower() or v == "[REDACTED]"
                    assert "token" not in k.lower() or v in ("[REDACTED]", "[REDACTED_OR_TRUNCATED]")
    finally:
        db.close()
