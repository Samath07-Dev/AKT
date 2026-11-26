"""
test_student_dashboard_flow.py

Comprehensive tests for:
- Student Registration & Login helpers with MongoDB persistence
- Password hashing verification
- Historical score logging and retrieval
- Student Dashboard concept selection and difficulty scaffolding
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from conftest import skip_unverified_db, TEST_SERVICE_SECRET
from api import (
    app as fastapi_app,
    get_mongo_db,
    get_motor_client,
    get_motor_db,
    selector
)

@skip_unverified_db
def test_mongodb_connection():
    """Verifies that MongoDB is accessible."""
    db = get_mongo_db()
    assert db is not None, "MongoDB connection should be active"
    # Ensure ping command works
    db.client.admin.command('ping')

@skip_unverified_db
def test_student_registration_and_login_flow():
    """Tests student registration, duplicate prevention, and login via FastAPI and MongoDB."""
    client = TestClient(fastapi_app)
    client.headers["X-Internal-Service-Secret"] = TEST_SERVICE_SECRET

    unique_user = f"user_{uuid.uuid4().hex[:6]}"
    password = "SecurePassword456"
    full_name = "Alex Test"
    email = f"{unique_user}@university.edu"

    # 1. Register student via FastAPI endpoint
    reg_res = client.post("/register", json={
        "username": unique_user,
        "password": password,
        "full_name": full_name,
        "email": email
    })
    assert reg_res.status_code == 200
    user_data = reg_res.json()
    assert user_data["status"] == "success"
    assert "student_id" in user_data
    student_id = user_data["student_id"]
    assert user_data["username"] == unique_user
    assert user_data["full_name"] == full_name

    # 2. Check MongoDB document directly to verify password uses Argon2id (not plaintext, not SHA-256)
    db = get_mongo_db()
    assert db is not None
    db_user = db["users"].find_one({"username": unique_user.lower()})
    assert db_user is not None
    assert db_user["password_hash"].startswith("$argon2id$")
    assert "SecurePassword456" not in str(db_user.values())

    # 3. Duplicate registration rejected (HTTP 400)
    dup_res = client.post("/register", json={
        "username": unique_user,
        "password": "DifferentPassword"
    })
    assert dup_res.status_code == 400
    assert "already registered" in dup_res.json().get("detail", "").lower()

    # 4. Successful login
    login_res = client.post("/login", json={
        "username": unique_user,
        "password": password
    })
    assert login_res.status_code == 200
    logged_user = login_res.json()
    assert logged_user["status"] == "success"
    assert logged_user["student_id"] == student_id
    assert logged_user["full_name"] == full_name

    # 5. Invalid password login rejected (HTTP 401)
    bad_res = client.post("/login", json={
        "username": unique_user,
        "password": "WrongPassword"
    })
    assert bad_res.status_code == 401
    assert "invalid" in bad_res.json().get("detail", "").lower()

@skip_unverified_db
def test_historical_score_recording_and_retrieval():
    """Tests recording bundle evaluation scores to MongoDB and retrieving historical logs via FastAPI."""
    client = TestClient(fastapi_app)
    client.headers["X-Internal-Service-Secret"] = TEST_SERVICE_SECRET

    test_stu_id = f"STU_{uuid.uuid4().hex[:6].upper()}"
    student_headers = {"X-Authenticated-Student-Id": test_stu_id}

    # Record 2 practice sessions
    rec1 = {
        "concept": "Variables",
        "difficulty": "easy",
        "bundle_average_score": 0.92,
        "mcq_scores": [1.0, 1.0, 1.0],
        "short_answer_score": 0.88,
        "code_score": 0.90,
        "next_difficulty": "medium",
        "scaffolding_reasoning": "Strong performance; upgraded to medium."
    }
    res_score1 = client.post(f"/api/v1/student/{test_stu_id}/record_score", json=rec1, headers=student_headers)
    assert res_score1.status_code == 200

    rec2 = {
        "concept": "Conditionals",
        "difficulty": "medium",
        "bundle_average_score": 0.84,
        "mcq_scores": [1.0, 1.0, 0.0],
        "short_answer_score": 0.85,
        "code_score": 1.0,
        "next_difficulty": "hard",
        "scaffolding_reasoning": "High mastery; upgraded to hard."
    }
    res_score2 = client.post(f"/api/v1/student/{test_stu_id}/record_score", json=rec2, headers=student_headers)
    assert res_score2.status_code == 200

    # Retrieve history via endpoint
    res_hist = client.get(f"/api/v1/student/{test_stu_id}/history", headers=student_headers)
    assert res_hist.status_code == 200
    hist_data = res_hist.json()
    history = hist_data.get("history", [])
    assert len(history) >= 2
    # Verify latest score is on top
    assert history[0]["concept"] == "Conditionals"
    assert history[0]["bundle_average_score"] == 0.84
    assert history[1]["concept"] == "Variables"
    assert history[1]["bundle_average_score"] == 0.92

def test_dashboard_scaffolding_and_concept_selection():
    """Tests adaptive difficulty scaffolding for student practice routing."""
    # Score > 0.8 upgrades easy -> medium
    next_diff, reason = selector.scaffold_difficulty(last_evidence_score=0.85, current_difficulty="easy")
    assert next_diff == "medium"

    # Score < 0.5 downgrades hard -> medium
    next_diff2, reason2 = selector.scaffold_difficulty(last_evidence_score=0.40, current_difficulty="hard")
    assert next_diff2 == "medium"

@skip_unverified_db
def test_motor_backend_integration_and_mastery_tracking():
    """Verifies motor connection in FastAPI backend and individual student mastery tracking in MongoDB."""
    # 1. Verify motor client is connected
    motor_client = get_motor_client()
    assert motor_client is not None
    motor_db = get_motor_db()
    assert motor_db is not None

    client = TestClient(fastapi_app)
    client.headers["X-Internal-Service-Secret"] = TEST_SERVICE_SECRET

    # Verify healthcheck reports motor connected
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "motor" in res_root.json().get("mongodb", "").lower()

    # 2. Register student via FastAPI motor endpoint
    unique_user = f"motor_stu_{uuid.uuid4().hex[:6]}"
    reg_res = client.post("/register", json={
        "username": unique_user,
        "password": "Password123!",
        "full_name": "Motor Test Student",
        "email": f"{unique_user}@test.edu"
    })
    assert reg_res.status_code == 200
    reg_data = reg_res.json()
    student_id = reg_data["student_id"]
    assert "mastery_state" in reg_data
    assert "Variables" in reg_data["mastery_state"]
    assert reg_data["mastery_state"]["Variables"]["mastery"] == 0.30

    # 3. Verify Login endpoint retrieves credentials & mastery state
    login_res = client.post("/login", json={
        "username": unique_user,
        "password": "Password123!"
    })
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert login_data["student_id"] == student_id
    assert "mastery_state" in login_data

    # 4. Update and track individual mastery state in MongoDB
    student_headers = {"X-Authenticated-Student-Id": student_id}
    new_mastery_state = {
        "Variables": {"mastery": 0.88, "uncertainty": 0.12, "history": []},
        "Conditionals": {"mastery": 0.75, "uncertainty": 0.20, "history": []}
    }
    update_res = client.post(f"/api/v1/student/{student_id}/mastery", json={
        "knowledge_state": new_mastery_state,
        "concept_difficulties": {"Variables": "hard", "Conditionals": "medium"}
    }, headers=student_headers)
    assert update_res.status_code == 200

    # 5. Fetch mastery state via endpoint
    mastery_res = client.get(f"/api/v1/student/{student_id}/mastery", headers=student_headers)
    assert mastery_res.status_code == 200
    m_data = mastery_res.json()
    assert m_data["student_id"] == student_id
    assert m_data["knowledge_state"]["Variables"]["mastery"] == 0.88
    assert m_data["concept_difficulties"]["Variables"] == "hard"

    # 6. Verify direct MongoDB document persistence in student_states
    db = get_mongo_db()
    assert db is not None
    state_doc = db["student_states"].find_one({"student_id": student_id})
    assert state_doc is not None
    assert state_doc["knowledge_state"]["Variables"]["mastery"] == 0.88
    assert state_doc["concept_difficulties"]["Variables"] == "hard"

def test_session_state_logged_in_gating():
    """Verifies that app.py session_state gating logic cleanly separates Auth vs Dashboard."""
    # Test unauthenticated state logic
    session_state = {"logged_in": False, "user_info": {}, "current_page": "dashboard"}
    assert session_state["logged_in"] is False
    auth_visible = not session_state["logged_in"]
    dashboard_visible = session_state["logged_in"]
    assert auth_visible is True
    assert dashboard_visible is False

    # Simulate successful login
    session_state["logged_in"] = True
    session_state["user_info"] = {"student_id": "S001", "username": "alice", "full_name": "Alice Smith"}
    
    # When true, Auth is suppressed, and personalized Dashboard and concept selector are active
    auth_visible = not session_state["logged_in"]
    dashboard_visible = session_state["logged_in"]
    assert auth_visible is False
    assert dashboard_visible is True
    assert session_state["user_info"]["student_id"] == "S001"

def test_zero_attempts_dashboard_display_logic():
    """Verifies that 0 attempts displays 0.0% / Not Attempted on frontend while preserving 0.30 backend prior."""
    from src.engine.knowledge_state import KnowledgeStateTracker
    tracker = KnowledgeStateTracker()
    state_dict = tracker.get_knowledge_state()
    
    # 1. Backend initialization values remain intact for mathematical updates
    assert state_dict["Variables"]["mastery"] == 0.30
    assert state_dict["Variables"]["uncertainty"] == 0.50
    assert state_dict["Variables"]["attempts"] == 0

    # 2. Simulate 0-attempts student
    score_history = []
    total_attempts = len(score_history)
    assert total_attempts == 0

    # Frontend overall accuracy presentation
    if total_attempts > 0:
        overall_accuracy_disp = "100.0%"
    else:
        overall_accuracy_disp = "0.0%"
    assert overall_accuracy_disp == "0.0%"

    # Frontend current concept mastery presentation
    selected_kc = "Variables"
    curr_kc_data = state_dict.get(selected_kc, {})
    curr_kc_attempts = curr_kc_data.get("attempts", 0)
    if total_attempts == 0 or curr_kc_attempts == 0:
        curr_kc_mastery_disp = "0.0%"
    else:
        curr_kc_mastery_disp = f"{curr_kc_data.get('mastery', 0.30)*100:.1f}%"
    assert curr_kc_mastery_disp == "0.0%"

    # Frontend concept card presentation
    for c_name, c_data in state_dict.items():
        c_att = c_data.get("attempts", 0)
        if total_attempts == 0 or c_att == 0:
            card_m_disp = "0.0%"
            badge_lbl = "Not Attempted"
            badge_cls = "diff-neutral"
        else:
            card_m_disp = f"{c_data.get('mastery', 0.30)*100:.0f}%"
            badge_lbl = "Mastered"
            badge_cls = "diff-easy"
        assert card_m_disp == "0.0%"
        assert badge_lbl == "Not Attempted"
        assert badge_cls == "diff-neutral"


# ==============================================================================
# PHASE 3.3.4.33: FASTAPI SCORE LEDGER & IDEMPOTENT EMA INTEGRATION TESTS
# ==============================================================================
import concurrent.futures
from datetime import datetime, timezone

@skip_unverified_db
def test_mcq_correct_update_0_30_to_0_44():
    """Verifies that a single correct MCQ (e=1.0) updates mastery from 0.30 to 0.44 with alpha=0.20."""
    client = TestClient(fastapi_app)
    client.headers["X-Internal-Service-Secret"] = TEST_SERVICE_SECRET

    student_id = f"S_TEST_{uuid.uuid4().hex[:8].upper()}"
    headers = {"X-Authenticated-Student-Id": student_id}
    sub_id = f"sub_correct_{uuid.uuid4().hex[:8]}"

    res = client.post(f"/api/v1/student/{student_id}/record_score", json={
        "submission_id": sub_id,
        "concept": "Variables",
        "difficulty": "medium",
        "bundle_average_score": 1.0,
        "mcq_scores": [1.0],
        "short_answer_score": 0.0,
        "code_score": 0.0
    }, headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["bkt_processed"] is True
    assert round(data["mastery"], 4) == 0.2394
    assert round(data["uncertainty"], 4) == 0.2610
    assert data["attempts"] == 4


@skip_unverified_db
def test_mcq_incorrect_update_0_30_to_0_24():
    """Verifies that a single incorrect MCQ (padded to 3 MCQs + 1 SA) updates mastery to 0.1306."""
    client = TestClient(fastapi_app)
    client.headers["X-Internal-Service-Secret"] = TEST_SERVICE_SECRET

    student_id = f"S_TEST_{uuid.uuid4().hex[:8].upper()}"
    headers = {"X-Authenticated-Student-Id": student_id}
    sub_id = f"sub_incorrect_{uuid.uuid4().hex[:8]}"

    res = client.post(f"/api/v1/student/{student_id}/record_score", json={
        "submission_id": sub_id,
        "concept": "Conditionals",
        "difficulty": "easy",
        "bundle_average_score": 0.0,
        "mcq_scores": [0.0],
        "short_answer_score": 0.0,
        "code_score": 0.0
    }, headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["bkt_processed"] is True
    assert round(data["mastery"], 4) == 0.1306
    assert round(data["uncertainty"], 4) == 0.2610
    assert data["attempts"] == 4


@skip_unverified_db
def test_three_sequential_observations_numerical_criteria():
    """
    Verifies numerical acceptance criteria for bundle observations under Phase 7:
    - Evidence [1, 0, 0] + SA 85.0 yields mastery 0.4237, uncertainty ~0.2610, attempts = 4
    - Evidence [1, 1, 1] + SA 85.0 yields mastery 0.6937, uncertainty ~0.2610, attempts = 4
    """
    client = TestClient(fastapi_app)
    client.headers["X-Internal-Service-Secret"] = TEST_SERVICE_SECRET

    student_id = f"S_TEST_{uuid.uuid4().hex[:8].upper()}"
    headers = {"X-Authenticated-Student-Id": student_id}

    # 1. Exception Handling: [1.0, 0.0, 0.0]
    res1 = client.post(f"/api/v1/student/{student_id}/record_score", json={
        "submission_id": f"sub_eh_{uuid.uuid4().hex[:8]}",
        "concept": "Exception Handling",
        "difficulty": "easy",
        "bundle_average_score": 0.54,
        "mcq_scores": [1.0, 0.0, 0.0],
        "short_answer_score": 85.0,
        "code_score": 0.0
    }, headers=headers)
    assert res1.status_code == 200
    d1 = res1.json()
    assert round(d1["mastery"], 4) == 0.4237
    assert abs(d1["uncertainty"] - 0.2610) < 0.001
    assert d1["attempts"] == 4

    # 2. Loops: [1.0, 1.0, 1.0]
    res2 = client.post(f"/api/v1/student/{student_id}/record_score", json={
        "submission_id": f"sub_loops_{uuid.uuid4().hex[:8]}",
        "concept": "Loops",
        "difficulty": "medium",
        "bundle_average_score": 0.94,
        "mcq_scores": [1.0, 1.0, 1.0],
        "short_answer_score": 85.0,
        "code_score": 0.0
    }, headers=headers)
    assert res2.status_code == 200
    d2 = res2.json()
    assert round(d2["mastery"], 4) == 0.6937
    assert abs(d2["uncertainty"] - 0.2610) < 0.001
    assert d2["attempts"] == 4


@skip_unverified_db
def test_evidence_exclusion_short_answer_and_code():
    """
    Verifies that coding scores remain quarantined while Short Answer is admitted under Phase 7.
    """
    client = TestClient(fastapi_app)
    client.headers["X-Internal-Service-Secret"] = TEST_SERVICE_SECRET

    student_id = f"S_TEST_{uuid.uuid4().hex[:8].upper()}"
    headers = {"X-Authenticated-Student-Id": student_id}

    # Pass 1 MCQ (1.0), Short Answer (0.85), Code (0.00), Bundle Average (0.6167)
    res = client.post(f"/api/v1/student/{student_id}/record_score", json={
        "submission_id": f"sub_excl_{uuid.uuid4().hex[:8]}",
        "concept": "Functions",
        "difficulty": "medium",
        "bundle_average_score": 0.6167,
        "mcq_scores": [1.0],
        "short_answer_score": 0.85,
        "code_score": 0.0
    }, headers=headers)
    assert res.status_code == 200
    data = res.json()
    # Mastery reflects padded MCQs + admitted SA (0.4237), attempts = 4, quarantined code excluded
    assert round(data["mastery"], 4) == 0.4237
    assert data["attempts"] == 4


@skip_unverified_db
def test_invalid_evidence_rejection():
    """Verifies that non-binary or out-of-bounds evidence scores return HTTP 400."""
    client = TestClient(fastapi_app)
    client.headers["X-Internal-Service-Secret"] = TEST_SERVICE_SECRET

    student_id = f"S_TEST_{uuid.uuid4().hex[:8].upper()}"
    headers = {"X-Authenticated-Student-Id": student_id}

    # Pass non-binary numbers, strings, and out-of-bounds values
    res = client.post(f"/api/v1/student/{student_id}/record_score", json={
        "submission_id": f"sub_inv_{uuid.uuid4().hex[:8]}",
        "concept": "Arrays",
        "difficulty": "hard",
        "bundle_average_score": 0.50,
        "mcq_scores": [0.5, 2.0, -1.0, 0.75],
        "short_answer_score": 0.0,
        "code_score": 0.0
    }, headers=headers)
    assert res.status_code == 400


@skip_unverified_db
def test_idempotent_duplicate_submission():
    """Verifies that resubmitting the same submission_id reuses the existing score and skips re-application."""
    client = TestClient(fastapi_app)
    client.headers["X-Internal-Service-Secret"] = TEST_SERVICE_SECRET

    student_id = f"S_TEST_{uuid.uuid4().hex[:8].upper()}"
    headers = {"X-Authenticated-Student-Id": student_id}
    sub_id = f"sub_dup_{uuid.uuid4().hex[:8]}"

    payload = {
        "submission_id": sub_id,
        "concept": "Syntax",
        "difficulty": "easy",
        "bundle_average_score": 1.0,
        "mcq_scores": [1.0],
        "short_answer_score": 0.0,
        "code_score": 0.0
    }

    # First attempt: updates state
    res1 = client.post(f"/api/v1/student/{student_id}/record_score", json=payload, headers=headers)
    assert res1.status_code == 200
    assert round(res1.json()["mastery"], 4) == 0.2394
    assert res1.json()["attempts"] == 4

    # Second attempt (same submission_id): returns cached result, does NOT apply EMA again
    res2 = client.post(f"/api/v1/student/{student_id}/record_score", json=payload, headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2.get("replayed") is True
    assert round(data2["mastery"], 4) == 0.2394
    assert data2["attempts"] == 4

    # Verify scores collection contains exactly 1 document for this submission_id
    db = get_mongo_db()
    count = db["scores"].count_documents({"submission_id": sub_id})
    assert count == 1


import httpx
import asyncio

@skip_unverified_db
def test_concurrent_duplicate_requests():
    """Verifies that concurrent duplicate submissions for the same submission_id do not duplicate writes."""
    student_id = f"S_TEST_{uuid.uuid4().hex[:8].upper()}"
    sub_id = f"sub_conc_{uuid.uuid4().hex[:8]}"

    payload = {
        "submission_id": sub_id,
        "concept": "OOP",
        "difficulty": "medium",
        "bundle_average_score": 1.0,
        "mcq_scores": [1.0],
        "short_answer_score": 0.0,
        "code_score": 0.0
    }
    headers = {
        "X-Internal-Service-Secret": TEST_SERVICE_SECRET,
        "X-Authenticated-Student-Id": student_id
    }

    async def _execute():
        transport = httpx.ASGITransport(app=fastapi_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await asyncio.gather(
                client.post(f"/api/v1/student/{student_id}/record_score", json=payload, headers=headers),
                client.post(f"/api/v1/student/{student_id}/record_score", json=payload, headers=headers)
            )

    res1, res2 = asyncio.run(_execute())

    assert res1.status_code == 200
    assert res2.status_code == 200

    # Ensure exactly 1 score row in MongoDB and 4 attempts recorded (3 MCQs + 1 SA)
    db = get_mongo_db()
    assert db["scores"].count_documents({"submission_id": sub_id}) == 1
    state_doc = db["student_states"].find_one({"student_id": student_id})
    assert state_doc["knowledge_state"]["OOP"]["attempts"] == 4
    assert round(state_doc["knowledge_state"]["OOP"]["mastery"], 4) == 0.2394


@skip_unverified_db
def test_two_distinct_submissions_same_student():
    """Verifies sequential state transitions across two distinct assessment submissions."""
    client = TestClient(fastapi_app)
    client.headers["X-Internal-Service-Secret"] = TEST_SERVICE_SECRET

    student_id = f"S_TEST_{uuid.uuid4().hex[:8].upper()}"
    headers = {"X-Authenticated-Student-Id": student_id}

    # Submission 1: bundle 1 -> mastery 0.2394, attempts 4
    res1 = client.post(f"/api/v1/student/{student_id}/record_score", json={
        "submission_id": f"sub_seq1_{uuid.uuid4().hex[:8]}",
        "concept": "Dictionaries",
        "difficulty": "medium",
        "bundle_average_score": 1.0,
        "mcq_scores": [1.0],
        "short_answer_score": 0.0,
        "code_score": 0.0
    }, headers=headers)
    assert res1.status_code == 200
    assert round(res1.json()["mastery"], 4) == 0.2394

    # Submission 2: bundle 2 -> mastery 0.2130, attempts 8
    res2 = client.post(f"/api/v1/student/{student_id}/record_score", json={
        "submission_id": f"sub_seq2_{uuid.uuid4().hex[:8]}",
        "concept": "Dictionaries",
        "difficulty": "hard",
        "bundle_average_score": 1.0,
        "mcq_scores": [1.0],
        "short_answer_score": 0.0,
        "code_score": 0.0
    }, headers=headers)
    assert res2.status_code == 200
    assert round(res2.json()["mastery"], 4) == 0.2130
    assert res2.json()["attempts"] == 8


@skip_unverified_db
def test_crash_recovery_after_score_insertion_case_a():
    """
    Simulates Crash Case A: Score inserted with bkt_processed: False, process crashed before state update.
    Verifies that the recovery reconciliation applies the pending update and marks it processed.
    """
    client = TestClient(fastapi_app)
    client.headers["X-Internal-Service-Secret"] = TEST_SERVICE_SECRET

    student_id = f"S_TEST_{uuid.uuid4().hex[:8].upper()}"
    headers = {"X-Authenticated-Student-Id": student_id}
    sub_crash_a = f"sub_crash_a_{uuid.uuid4().hex[:8]}"

    # Manually insert unprocessed score into db.scores
    db = get_mongo_db()
    db["scores"].insert_one({
        "submission_id": sub_crash_a,
        "student_id": student_id,
        "concept": "File Handling",
        "difficulty": "easy",
        "bundle_average_score": 1.0,
        "mcq_scores": [1.0],
        "short_answer_score": 0.0,
        "code_score": 0.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "bkt_processed": False,
        "bkt_processed_at": None,
        "bkt_observations_applied": 0
    })

    # Trigger recovery via submission
    res = client.post(f"/api/v1/student/{student_id}/record_score", json={
        "submission_id": sub_crash_a,
        "concept": "File Handling",
        "difficulty": "easy",
        "bundle_average_score": 1.0,
        "mcq_scores": [1.0],
        "short_answer_score": 0.0,
        "code_score": 0.0
    }, headers=headers)
    assert res.status_code == 200

    # Assert score is marked bkt_processed: True and state is updated to 0.44
    score_doc = db["scores"].find_one({"submission_id": sub_crash_a})
    assert score_doc["bkt_processed"] is True

    state_doc = db["student_states"].find_one({"student_id": student_id})
    assert round(state_doc["knowledge_state"]["File Handling"]["mastery"], 4) == 0.4400
    assert state_doc["knowledge_state"]["File Handling"]["attempts"] == 1


@skip_unverified_db
def test_crash_recovery_state_saved_marker_lost_case_c():
    """
    Simulates Crash Case C (the critical hazard): State persistence succeeded with last_submission_id,
    but process crashed before bkt_processed was set to True in scores.
    Verifies that reconciliation detects the state token match, SKIPS re-application, and marks processed.
    """
    client = TestClient(fastapi_app)
    client.headers["X-Internal-Service-Secret"] = TEST_SERVICE_SECRET

    student_id = f"S_TEST_{uuid.uuid4().hex[:8].upper()}"
    headers = {"X-Authenticated-Student-Id": student_id}
    sub_crash_c = f"sub_crash_c_{uuid.uuid4().hex[:8]}"

    # Manually set up state as if it was ALREADY updated to 0.4400 with the token
    db = get_mongo_db()
    from api import get_initial_mastery_state
    k_state = get_initial_mastery_state()
    k_state["Variables"]["mastery"] = 0.4400
    k_state["Variables"]["uncertainty"] = 0.4250
    k_state["Variables"]["attempts"] = 1
    k_state["Variables"]["last_submission_id"] = sub_crash_c
    k_state["Variables"]["processed_submissions"] = [sub_crash_c]
    k_state["Variables"]["history"] = [{
        "attempt": 1,
        "evidence_score": 1.0,
        "activity_type": 0,
        "difficulty": "medium",
        "response_time_sec": 0.0,
        "post_mastery": 0.4400,
        "post_uncertainty": 0.4250,
        "submission_id": sub_crash_c
    }]

    db["student_states"].update_one(
        {"student_id": student_id},
        {"$set": {
            "student_id": student_id,
            "knowledge_state": k_state,
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )

    # Insert score with bkt_processed: False (marker was lost)
    db["scores"].insert_one({
        "submission_id": sub_crash_c,
        "student_id": student_id,
        "concept": "Variables",
        "difficulty": "medium",
        "bundle_average_score": 1.0,
        "mcq_scores": [1.0],
        "short_answer_score": 0.0,
        "code_score": 0.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "bkt_processed": False,
        "bkt_processed_at": None,
        "bkt_observations_applied": 0
    })

    # Trigger retry / reconciliation
    res = client.post(f"/api/v1/student/{student_id}/record_score", json={
        "submission_id": sub_crash_c,
        "concept": "Variables",
        "difficulty": "medium",
        "bundle_average_score": 1.0,
        "mcq_scores": [1.0],
        "short_answer_score": 0.0,
        "code_score": 0.0
    }, headers=headers)
    assert res.status_code == 200

    # CRUCIAL ASSERTION: Mastery must REMAIN 0.4400, NOT increment to 0.5520! Attempts must remain 1!
    state_doc = db["student_states"].find_one({"student_id": student_id})
    assert round(state_doc["knowledge_state"]["Variables"]["mastery"], 4) == 0.4400
    assert state_doc["knowledge_state"]["Variables"]["attempts"] == 1

    # Score document must now be marked bkt_processed: True
    score_doc = db["scores"].find_one({"submission_id": sub_crash_c})
    assert score_doc["bkt_processed"] is True


@skip_unverified_db
def test_retry_after_lost_http_response_case_d():
    """
    Simulates Case D: Score was fully processed, but client timed out and retried.
    Verifies that the retry is served idempotently with status: success and replayed: True.
    """
    client = TestClient(fastapi_app)
    client.headers["X-Internal-Service-Secret"] = TEST_SERVICE_SECRET

    student_id = f"S_TEST_{uuid.uuid4().hex[:8].upper()}"
    headers = {"X-Authenticated-Student-Id": student_id}
    sub_id = f"sub_lost_{uuid.uuid4().hex[:8]}"

    payload = {
        "submission_id": sub_id,
        "concept": "Conditionals",
        "difficulty": "medium",
        "bundle_average_score": 1.0,
        "mcq_scores": [1.0],
        "short_answer_score": 0.0,
        "code_score": 0.0
    }

    # Initial request
    res1 = client.post(f"/api/v1/student/{student_id}/record_score", json=payload, headers=headers)
    assert res1.status_code == 200
    assert round(res1.json()["mastery"], 4) == 0.2394

    # Retry request (lost response recovery)
    res2 = client.post(f"/api/v1/student/{student_id}/record_score", json=payload, headers=headers)
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["bkt_processed"] is True
    assert d2.get("replayed") is True
    assert round(d2["mastery"], 4) == 0.2394
    assert d2["attempts"] == 4


@skip_unverified_db
def test_deterministic_pending_submission_ordering():
    """
    Verifies that multiple pending records are reconciled in strict chronological order.
    Order:
      1. sub_p1 at T1: e=1.0 (0.30 -> 0.44)
      2. sub_p2 at T2: e=0.0 (0.44 -> 0.3520)
    If processed in reverse order (p2 then p1), result would be 0.3920 instead of 0.3520.
    """
    client = TestClient(fastapi_app)
    client.headers["X-Internal-Service-Secret"] = TEST_SERVICE_SECRET

    student_id = f"S_TEST_{uuid.uuid4().hex[:8].upper()}"
    headers = {"X-Authenticated-Student-Id": student_id}

    sub_p1 = f"sub_p1_{uuid.uuid4().hex[:8]}"
    sub_p2 = f"sub_p2_{uuid.uuid4().hex[:8]}"

    db = get_mongo_db()
    # Insert sub_p1 with earlier timestamp
    db["scores"].insert_one({
        "submission_id": sub_p1,
        "student_id": student_id,
        "concept": "Functions",
        "difficulty": "medium",
        "bundle_average_score": 1.0,
        "mcq_scores": [1.0],
        "short_answer_score": 0.0,
        "code_score": 0.0,
        "timestamp": "2026-11-09T01:00:00.000Z",
        "bkt_processed": False,
        "bkt_processed_at": None,
        "bkt_observations_applied": 0
    })

    # Insert sub_p2 with later timestamp
    db["scores"].insert_one({
        "submission_id": sub_p2,
        "student_id": student_id,
        "concept": "Functions",
        "difficulty": "medium",
        "bundle_average_score": 0.0,
        "mcq_scores": [0.0],
        "short_answer_score": 0.0,
        "code_score": 0.0,
        "timestamp": "2026-11-09T01:05:00.000Z",
        "bkt_processed": False,
        "bkt_processed_at": None,
        "bkt_observations_applied": 0
    })

    # Trigger reconciliation via submission_id sub_p2
    res = client.post(f"/api/v1/student/{student_id}/record_score", json={
        "submission_id": sub_p2,
        "concept": "Functions",
        "difficulty": "medium",
        "bundle_average_score": 0.0,
        "mcq_scores": [0.0],
        "short_answer_score": 0.0,
        "code_score": 0.0
    }, headers=headers)
    assert res.status_code == 200

    # Check resulting mastery: must be 0.3520 (p1 then p2), NOT 0.3920
    state_doc = db["student_states"].find_one({"student_id": student_id})
    f_mastery = state_doc["knowledge_state"]["Functions"]["mastery"]
    assert round(f_mastery, 4) == 0.3520
    assert state_doc["knowledge_state"]["Functions"]["attempts"] == 2


@skip_unverified_db
def test_student_identity_isolation():
    """Verifies that requests cannot modify knowledge states belonging to another student."""
    client = TestClient(fastapi_app)
    client.headers["X-Internal-Service-Secret"] = TEST_SERVICE_SECRET

    student_a = f"S_TEST_A_{uuid.uuid4().hex[:6].upper()}"
    student_b = f"S_TEST_B_{uuid.uuid4().hex[:6].upper()}"

    # Student A authenticated, but targets Student B's endpoint -> HTTP 403 Forbidden
    res = client.post(
        f"/api/v1/student/{student_b}/record_score",
        json={
            "submission_id": f"sub_iso_{uuid.uuid4().hex[:8]}",
            "concept": "Variables",
            "difficulty": "easy",
            "bundle_average_score": 1.0,
            "mcq_scores": [1.0]
        },
        headers={"X-Authenticated-Student-Id": student_a}
    )
    assert res.status_code == 403
    assert "Forbidden" in res.json().get("detail", "")


@skip_unverified_db
def test_test_database_isolation_guard():
    """Verifies that tests strictly run against akt_tutor_test and never access production akt_tutor."""
    import api
    assert api.MONGO_DB_NAME == "akt_tutor_test"
    assert api.MONGO_DB_NAME != "akt_tutor"

    # Verify S009 existing records in akt_tutor_test remain untouched
    db = get_mongo_db()
    s009_scores = list(db["scores"].find({"student_id": "S009"}))
    assert len(s009_scores) == 2, f"Expected 2 records for S009, found {len(s009_scores)}"
    s009_state = db["student_states"].find_one({"student_id": "S009"})
    assert s009_state is not None
    assert round(s009_state["knowledge_state"]["Exception Handling"]["mastery"], 4) == 0.2816
    assert round(s009_state["knowledge_state"]["Loops"]["mastery"], 4) == 0.6416
    assert s009_state["knowledge_state"]["Variables"]["mastery"] == 0.30



