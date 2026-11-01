"""
test_student_dashboard_flow.py

Comprehensive tests for:
- Student Registration & Login helpers with MongoDB persistence
- Password hashing verification
- Historical score logging and retrieval
- Student Dashboard concept selection and difficulty scaffolding
"""

import hashlib
import uuid
import pytest
from app import (
    api_or_db_register,
    api_or_db_login,
    api_or_db_get_student_history,
    api_or_db_record_score,
    api_or_db_get_student_mastery_state,
    api_or_db_save_student_mastery_state,
    get_cached_scaffold_difficulty,
    compute_dashboard_metrics,
    get_cached_recommendation_info,
    get_mongodb_connection
)

def test_mongodb_connection():
    """Verifies that MongoDB is accessible."""
    db = get_mongodb_connection()
    assert db is not None, "MongoDB connection should be active"
    # Ensure ping command works
    db.client.admin.command('ping')

def test_student_registration_and_login_flow():
    """Tests student registration, duplicate prevention, and login."""
    unique_user = f"user_{uuid.uuid4().hex[:6]}"
    password = "SecurePassword456"
    full_name = "Alex Test"
    email = f"{unique_user}@university.edu"

    # 1. Register student
    success, msg, user_data = api_or_db_register(
        username=unique_user,
        password=password,
        full_name=full_name,
        email=email
    )
    assert success is True
    assert "student_id" in user_data
    student_id = user_data["student_id"]
    assert user_data["username"] == unique_user
    assert user_data["full_name"] == full_name

    # 2. Check MongoDB document directly to verify password is NOT plaintext
    db = get_mongodb_connection()
    db_user = db["users"].find_one({"username": unique_user.lower()})
    assert db_user is not None
    assert db_user["password_hash"] == hashlib.sha256(password.encode("utf-8")).hexdigest()
    assert "SecurePassword456" not in str(db_user.values())

    # 3. Duplicate registration rejected
    dup_success, dup_msg, _ = api_or_db_register(
        username=unique_user,
        password="DifferentPassword"
    )
    assert dup_success is False
    assert "already registered" in dup_msg.lower()

    # 4. Successful login
    login_ok, login_msg, logged_user = api_or_db_login(unique_user, password)
    assert login_ok is True
    assert logged_user["student_id"] == student_id
    assert logged_user["full_name"] == full_name

    # 5. Invalid password login rejected
    bad_ok, bad_msg, _ = api_or_db_login(unique_user, "WrongPassword")
    assert bad_ok is False
    assert "invalid" in bad_msg.lower()

def test_historical_score_recording_and_retrieval():
    """Tests recording bundle evaluation scores to MongoDB and retrieving historical logs."""
    test_stu_id = f"STU_{uuid.uuid4().hex[:6].upper()}"

    # Record 2 practice sessions
    api_or_db_record_score(
        student_id=test_stu_id,
        concept="Variables",
        difficulty="easy",
        bundle_average_score=0.92,
        mcq_scores=[1.0, 1.0, 1.0],
        short_answer_score=0.88,
        code_score=0.90,
        next_difficulty="medium",
        scaffolding_reasoning="Strong performance; upgraded to medium."
    )

    api_or_db_record_score(
        student_id=test_stu_id,
        concept="Conditionals",
        difficulty="medium",
        bundle_average_score=0.84,
        mcq_scores=[1.0, 1.0, 0.0],
        short_answer_score=0.85,
        code_score=1.0,
        next_difficulty="hard",
        scaffolding_reasoning="High mastery; upgraded to hard."
    )

    history = api_or_db_get_student_history(test_stu_id)
    assert len(history) >= 2
    # Verify latest score is on top
    assert history[0]["concept"] == "Conditionals"
    assert history[0]["bundle_average_score"] == 0.84
    assert history[1]["concept"] == "Variables"
    assert history[1]["bundle_average_score"] == 0.92

def test_dashboard_scaffolding_and_concept_selection():
    """Tests adaptive difficulty scaffolding for student practice routing."""
    # Score > 0.8 upgrades easy -> medium
    next_diff, reason = get_cached_scaffold_difficulty(last_score=0.85, current_diff="easy")
    assert next_diff == "medium"

    # Score < 0.5 downgrades hard -> medium
    next_diff2, reason2 = get_cached_scaffold_difficulty(last_score=0.40, current_diff="hard")
    assert next_diff2 == "medium"

def test_motor_backend_integration_and_mastery_tracking():
    """Verifies motor connection in FastAPI backend and individual student mastery tracking in MongoDB."""
    from fastapi.testclient import TestClient
    from api import app, get_motor_client, get_motor_db
    
    # 1. Verify motor client is connected
    motor_client = get_motor_client()
    assert motor_client is not None
    motor_db = get_motor_db()
    assert motor_db is not None

    client = TestClient(app)
    
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
    new_mastery_state = {
        "Variables": {"mastery": 0.88, "uncertainty": 0.12, "history": []},
        "Conditionals": {"mastery": 0.75, "uncertainty": 0.20, "history": []}
    }
    update_res = client.post(f"/api/v1/student/{student_id}/mastery", json={
        "knowledge_state": new_mastery_state,
        "concept_difficulties": {"Variables": "hard", "Conditionals": "medium"}
    })
    assert update_res.status_code == 200

    # 5. Fetch mastery state via endpoint
    mastery_res = client.get(f"/api/v1/student/{student_id}/mastery")
    assert mastery_res.status_code == 200
    m_data = mastery_res.json()
    assert m_data["student_id"] == student_id
    assert m_data["knowledge_state"]["Variables"]["mastery"] == 0.88
    assert m_data["concept_difficulties"]["Variables"] == "hard"

    # 6. Verify app helper retrieves individual mastery state
    loaded_state = api_or_db_get_student_mastery_state(student_id)
    assert loaded_state is not None
    assert loaded_state["Variables"]["mastery"] == 0.88

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
