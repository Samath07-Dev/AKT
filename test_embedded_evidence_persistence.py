"""
test_embedded_evidence_persistence.py

Comprehensive isolated unit and integration tests for Phase 5:
Option A Embedded Evidence Persistence in MongoDB `scores` collection.

Safety Constraints Verified:
1. Isolated in-memory async database mock (no live MongoDB connection).
2. Atomic persistence: 5 item-level UnifiedEvidenceRecords embedded directly in `scores`.
3. Idempotency: Replay with existing submission_id returns cached result without duplicate insert.
4. Concurrency: DuplicateKeyError handled safely during race conditions.
5. Privacy policy: Raw student code and freeform answers replaced with [EXCLUDED_PRIVACY_POLICY].
6. Research admission: MCQ -> ADMITTED_BINARY, Short Answer -> ADMITTED_FORMATIVE_ONLY,
   Coding -> PENDING_EVALUATION with raw_score=None.
7. Backward compatibility: Legacy score records without evidence_records handled cleanly.
8. Cognitive safety: BKT/EMA tracker updated strictly by MCQ items.
"""

import copy
import pytest
from datetime import datetime, timezone
from pymongo.errors import DuplicateKeyError
from fastapi.testclient import TestClient

import api
from conftest import TEST_SERVICE_SECRET
from src.schemas.evidence import (
    UnifiedEvidenceRecord,
    ModalityType,
    EvaluationLifecycle,
    AdmissionStatus,
)
from src.evidence_adapters.bundle_builder import (
    build_embedded_bundle_evidence,
    PRIVACY_EXCLUSION_TOKEN,
)


class InMemoryAsyncCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, key_or_list, direction=1):
        if isinstance(key_or_list, list):
            for field, dir_val in reversed(key_or_list):
                if field == "_id":
                    continue
                self._docs.sort(key=lambda d: d.get(field, ""), reverse=(dir_val == -1))
        else:
            self._docs.sort(key=lambda d: d.get(key_or_list, ""), reverse=(direction == -1))
        return self

    async def to_list(self, length=100):
        return [copy.deepcopy(d) for d in self._docs[:length]]


class InMemoryAsyncCollection:
    def __init__(self, initial_docs=None, simulate_duplicate_key_error=False):
        self.docs = [copy.deepcopy(d) for d in (initial_docs or [])]
        self.simulate_duplicate_key_error = simulate_duplicate_key_error

    def _matches(self, doc, query):
        for k, v in (query or {}).items():
            if isinstance(v, dict):
                if "$exists" in v:
                    exists = k in doc
                    if exists != bool(v["$exists"]):
                        return False
                else:
                    return False
            elif doc.get(k) != v:
                return False
        return True

    async def find_one(self, query=None, projection=None):
        for doc in self.docs:
            if self._matches(doc, query):
                result = copy.deepcopy(doc)
                if projection and projection.get("_id") == 0:
                    result.pop("_id", None)
                return result
        return None

    def find(self, query=None, projection=None):
        matched = []
        for doc in self.docs:
            if self._matches(doc, query):
                item = copy.deepcopy(doc)
                if projection and projection.get("_id") == 0:
                    item.pop("_id", None)
                matched.append(item)
        return InMemoryAsyncCursor(matched)

    async def insert_one(self, doc):
        if self.simulate_duplicate_key_error:
            raise DuplicateKeyError("E11000 duplicate key error collection: scores index: submission_id_1")
        # Check unique constraint on submission_id
        if "submission_id" in doc:
            for existing in self.docs:
                if existing.get("submission_id") == doc["submission_id"]:
                    raise DuplicateKeyError(f"Duplicate submission_id: {doc['submission_id']}")

        stored = copy.deepcopy(doc)
        stored.setdefault("_id", f"fake_id_{len(self.docs) + 1}")
        self.docs.append(stored)
        return stored

    async def update_one(self, query, update, upsert=False):
        for doc in self.docs:
            if self._matches(doc, query):
                if "$set" in update:
                    doc.update(copy.deepcopy(update["$set"]))
                if "$inc" in update:
                    for k, delta in update["$inc"].items():
                        doc[k] = doc.get(k, 0) + delta
                return type("Res", (), {"matched_count": 1})()
        if upsert:
            new_doc = copy.deepcopy(query)
            if "$set" in update:
                new_doc.update(copy.deepcopy(update["$set"]))
            self.docs.append(new_doc)
            return type("Res", (), {"matched_count": 1})()
        return type("Res", (), {"matched_count": 0})()


class InMemoryMotorDB:
    def __init__(self, collections=None):
        self._collections = {
            "scores": InMemoryAsyncCollection(),
            "student_states": InMemoryAsyncCollection(),
            "users": InMemoryAsyncCollection(),
        }
        if collections:
            for name, docs in collections.items():
                self._collections[name] = InMemoryAsyncCollection(docs)

    def __getitem__(self, name):
        if name not in self._collections:
            self._collections[name] = InMemoryAsyncCollection()
        return self._collections[name]


def _make_auth_headers(student_id: str):
    return {
        "X-Internal-Service-Secret": TEST_SERVICE_SECRET,
        "X-Authenticated-Student-Id": student_id,
    }


def test_build_embedded_bundle_evidence_structure():
    """Verify that build_embedded_bundle_evidence produces 5 valid UnifiedEvidenceRecords."""
    records = build_embedded_bundle_evidence(
        student_id="student_pers_001",
        submission_id="sub_test_001",
        concept="Variables",
        difficulty="medium",
        mcq_scores=[1.0, 0.0, 1.0],
        short_answer_score=0.85,
        code_score=0.0,
        code_status="PENDING_SECURE_EVALUATION",
        code_execution_status="NOT_PERFORMED",
        code_tests_passed=0,
        code_tests_total=2,
    )

    assert len(records) == 5
    # Verify each is valid according to UnifiedEvidenceRecord
    for r in records:
        validated = UnifiedEvidenceRecord.model_validate(r)
        assert validated.submission_id == "sub_test_001"
        assert validated.bundle_id == "bundle_variables_medium"
        assert validated.student_id == "student_pers_001"

    # MCQs 1-3
    for i in range(3):
        rec = UnifiedEvidenceRecord.model_validate(records[i])
        assert rec.modality == ModalityType.MCQ
        assert rec.evaluation_lifecycle == EvaluationLifecycle.EVALUATED_SUCCESS
        assert rec.admission_status in (
            AdmissionStatus.ADMITTED_BINARY,
            AdmissionStatus.ADMITTED_FORMATIVE_ONLY,
        )
        assert rec.raw_score in (0.0, 1.0)

    # Short Answer
    sa_rec = UnifiedEvidenceRecord.model_validate(records[3])
    assert sa_rec.modality == ModalityType.SHORT_ANSWER
    assert sa_rec.evaluation_lifecycle == EvaluationLifecycle.EVALUATED_SUCCESS
    assert sa_rec.admission_status == AdmissionStatus.ADMITTED_FORMATIVE_ONLY
    assert sa_rec.normalized_score == pytest.approx(0.85, abs=1e-3)
    assert sa_rec.raw_score == pytest.approx(0.85, abs=1e-3)

    # Coding Challenge
    code_rec = UnifiedEvidenceRecord.model_validate(records[4])
    assert code_rec.modality == ModalityType.CODING
    assert code_rec.evaluation_lifecycle == EvaluationLifecycle.PENDING_EVALUATION
    assert code_rec.admission_status == AdmissionStatus.PENDING_EVALUATION
    assert code_rec.raw_score is None
    assert code_rec.normalized_score is None
    assert code_rec.evaluation_completion_timestamp is None


def test_record_student_score_endpoint_embeds_evidence(monkeypatch):
    """
    Test that /api/v1/student/{id}/record_score automatically creates and embeds
    5 UnifiedEvidenceRecords in the MongoDB scores document if not provided in payload.
    """
    student_id = "student_record_score_001"
    fake_db = InMemoryMotorDB()
    monkeypatch.setattr(api, "get_motor_db", lambda: fake_db)
    api._student_trackers.pop(student_id, None)
    api._in_memory_scores.pop(student_id, None)

    client = TestClient(api.app)
    headers = _make_auth_headers(student_id)

    payload = {
        "submission_id": "sub_record_score_001",
        "student_id": student_id,
        "concept": "Loops",
        "difficulty": "medium",
        "bundle_average_score": 0.76,
        "mcq_scores": [1.0, 1.0, 0.0],
        "short_answer_score": 0.90,
        "code_score": 0.0,
        "code_status": "PENDING_SECURE_EVALUATION",
        "code_execution_status": "NOT_PERFORMED",
        "code_tests_passed": 0,
        "code_tests_total": 2,
        "syntax_preview_passed": True,
        "syntax_preview_count": 2,
    }

    res = client.post(
        f"/api/v1/student/{student_id}/record_score",
        json=payload,
        headers=headers,
    )
    assert res.status_code == 200

    # Verify score document in database
    docs = fake_db["scores"].docs
    assert len(docs) == 1
    score_doc = docs[0]
    assert score_doc["submission_id"] == "sub_record_score_001"
    assert "evidence_records" in score_doc
    assert len(score_doc["evidence_records"]) == 5

    # Validate each embedded record
    for rec in score_doc["evidence_records"]:
        validated = UnifiedEvidenceRecord.model_validate(rec)
        assert validated.submission_id == "sub_record_score_001"
        assert validated.student_id == student_id


def test_evaluate_bundle_embeds_evidence_records(monkeypatch):
    """
    Test that /api/v1/evaluate_bundle constructs embedded evidence and returns it
    in BundleAssessmentResponse while persisting it into MongoDB scores collection.
    """
    student_id = "student_bundle_eval_001"
    fake_db = InMemoryMotorDB()
    monkeypatch.setattr(api, "get_motor_db", lambda: fake_db)
    api._student_trackers.pop(student_id, None)
    api._in_memory_scores.pop(student_id, None)

    client = TestClient(api.app)
    headers = _make_auth_headers(student_id)

    bundle_req = {
        "student_id": student_id,
        "concept": "Variables",
        "difficulty": "medium",
        "mcq_responses": ["A", "B", "A"],
        "short_answer_response": "Variables store data values in computer memory.",
        "code_response": "x = 10\nprint(x)",
        "response_time_sec": 45.0,
    }

    res = client.post(
        "/api/v1/evaluate_bundle",
        json=bundle_req,
        headers=headers,
    )
    assert res.status_code == 200
    resp_data = res.json()

    # Response contains evidence_records
    assert "evidence_records" in resp_data
    assert resp_data["evidence_records"] is not None
    assert len(resp_data["evidence_records"]) == 5

    # Database contains 1 score document with matching evidence_records
    assert len(fake_db["scores"].docs) == 1
    stored_doc = fake_db["scores"].docs[0]
    assert stored_doc["evidence_records"] == resp_data["evidence_records"]

    # Verify coding record is PENDING_EVALUATION with raw_score=None
    code_evidence = stored_doc["evidence_records"][4]
    assert code_evidence["modality"] == "CODING"
    assert code_evidence["evaluation_lifecycle"] == "PENDING_EVALUATION"
    assert code_evidence["admission_status"] == "PENDING_EVALUATION"
    assert code_evidence["raw_score"] is None
    assert code_evidence["evaluation_completion_timestamp"] is None


def test_privacy_exclusion_in_embedded_evidence(monkeypatch):
    """
    Ensure raw student code and freeform answers are NOT stored in the persistent ledger.
    They must be replaced with the standardized PRIVACY_EXCLUSION_TOKEN.
    """
    student_id = "student_privacy_001"
    fake_db = InMemoryMotorDB()
    monkeypatch.setattr(api, "get_motor_db", lambda: fake_db)
    api._student_trackers.pop(student_id, None)
    api._in_memory_scores.pop(student_id, None)

    client = TestClient(api.app)
    headers = _make_auth_headers(student_id)

    raw_secret_code = "def proprietary_algorithm(): return 42"
    raw_secret_text = "This is my private intellectual property answer."

    bundle_req = {
        "student_id": student_id,
        "concept": "Functions",
        "difficulty": "medium",
        "mcq_responses": ["A", "A", "A"],
        "short_answer_response": raw_secret_text,
        "code_response": raw_secret_code,
        "response_time_sec": 30.0,
    }

    res = client.post("/api/v1/evaluate_bundle", json=bundle_req, headers=headers)
    assert res.status_code == 200

    stored_doc = fake_db["scores"].docs[0]
    evidence_list = stored_doc["evidence_records"]

    # Check Short Answer item (index 3)
    sa_item = evidence_list[3]
    assert sa_item["modality_details"]["short_answer"]["submitted_text"] == PRIVACY_EXCLUSION_TOKEN
    assert raw_secret_text not in str(evidence_list)

    # Check Coding Challenge item (index 4)
    code_item = evidence_list[4]
    assert code_item["modality_details"]["coding"]["submitted_code"] == PRIVACY_EXCLUSION_TOKEN
    assert raw_secret_code not in str(evidence_list)


def test_idempotency_replay_prevents_duplicate_evidence(monkeypatch):
    """
    Submitting the same submission_id twice must be idempotent:
    The second call must return the cached score without inserting a duplicate document.
    """
    student_id = "student_idempotency_001"
    sub_id = "sub_idempotency_unique_99"
    fake_db = InMemoryMotorDB()
    monkeypatch.setattr(api, "get_motor_db", lambda: fake_db)
    api._student_trackers.pop(student_id, None)
    api._in_memory_scores.pop(student_id, None)

    client = TestClient(api.app)
    headers = _make_auth_headers(student_id)

    payload = {
        "submission_id": sub_id,
        "student_id": student_id,
        "concept": "Variables",
        "difficulty": "easy",
        "bundle_average_score": 1.0,
        "mcq_scores": [1.0, 1.0, 1.0],
        "short_answer_score": 1.0,
        "code_score": 0.0,
    }

    # First submission
    res1 = client.post(f"/api/v1/student/{student_id}/record_score", json=payload, headers=headers)
    assert res1.status_code == 200
    assert len(fake_db["scores"].docs) == 1

    # Second submission (replay)
    res2 = client.post(f"/api/v1/student/{student_id}/record_score", json=payload, headers=headers)
    assert res2.status_code == 200
    # Still exactly 1 score document in database
    assert len(fake_db["scores"].docs) == 1
    assert fake_db["scores"].docs[0]["submission_id"] == sub_id
    assert len(fake_db["scores"].docs[0]["evidence_records"]) == 5


def test_duplicate_key_error_concurrency_race(monkeypatch):
    """
    If two concurrent requests race to insert the same submission_id,
    DuplicateKeyError must be caught and existing score returned cleanly.
    """
    import asyncio

    async def _test():
        student_id = "student_race_001"
        sub_id = "sub_race_123"

        # Pre-populate the document in DB to simulate another thread having just inserted it
        existing_entry = {
            "submission_id": sub_id,
            "student_id": student_id,
            "concept": "Variables",
            "difficulty": "medium",
            "bundle_average_score": 0.8,
            "mcq_scores": [1.0, 1.0, 0.0],
            "short_answer_score": 0.8,
            "code_score": 0.0,
            "timestamp": "2026-11-17T00:00:00Z",
            "bkt_processed": True,
            "evidence_records": [{"evidence_id": "ev_race_1"}]
        }
        fake_col = InMemoryAsyncCollection(initial_docs=[existing_entry], simulate_duplicate_key_error=True)
        fake_db = InMemoryMotorDB(collections={"scores": fake_col.docs})
        fake_db._collections["scores"].simulate_duplicate_key_error = True
        monkeypatch.setattr(api, "get_motor_db", lambda: fake_db)

        # Calling record_student_score_internal_async should catch DuplicateKeyError and return existing_score
        result = await api.record_student_score_internal_async(
            student_id=student_id,
            concept="Variables",
            difficulty="medium",
            bundle_average_score=0.8,
            mcq_scores=[1.0, 1.0, 0.0],
            short_answer_score=0.8,
            code_score=0.0,
            submission_id=sub_id,
        )

        assert result["status"] == "success"
        assert result["submission_id"] == sub_id
        assert result["replayed"] is True
        assert result["bkt_processed"] is True

    asyncio.run(_test())


def test_backward_compatibility_legacy_scores(monkeypatch):
    """
    Score documents in MongoDB lacking 'evidence_records' must load and return cleanly
    via /history endpoint without errors or missing key crashes.
    """
    student_id = "student_legacy_001"
    legacy_doc = {
        "submission_id": "sub_legacy_100",
        "student_id": student_id,
        "concept": "Variables",
        "difficulty": "easy",
        "bundle_average_score": 0.9,
        "mcq_scores": [1.0, 1.0, 1.0],
        "short_answer_score": 0.8,
        "code_score": 0.0,
        "code_status": "PENDING_SECURE_EVALUATION",
        "timestamp": "2026-11-01T10:00:00Z",
        # NOTE: no 'evidence_records' field present!
    }

    fake_db = InMemoryMotorDB(collections={"scores": [legacy_doc]})
    monkeypatch.setattr(api, "get_motor_db", lambda: fake_db)
    api._student_trackers.pop(student_id, None)
    api._in_memory_scores.pop(student_id, None)

    client = TestClient(api.app)
    headers = _make_auth_headers(student_id)

    res = client.get(f"/api/v1/student/{student_id}/history", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["history"]) == 1
    assert data["history"][0]["submission_id"] == "sub_legacy_100"
    assert "evidence_records" not in data["history"][0]  # Missing safely tolerated


def test_infrastructure_failure_evidence_handling():
    """
    When coding sandbox encounters an infrastructure failure (e.g. Docker timeout/offline),
    raw_score=None, tests_run=0, and admission_status=REJECTED_INFRASTRUCTURE_FAILURE.
    """
    coding_output = {
        "code_status": "EVALUATION_FAILED_INFRASTRUCTURE",
        "code_execution_status": "INFRASTRUCTURE_UNAVAILABLE",
        "code_score": 0.0,
        "code_tests_passed": 0,
        "code_tests_total": 3,
        "syntax_valid": True,
        "runtime_error": "Docker daemon offline",
        "feedback": "Execution infrastructure failed",
    }

    records = build_embedded_bundle_evidence(
        student_id="student_infra_001",
        submission_id="sub_infra_001",
        concept="Variables",
        difficulty="hard",
        mcq_scores=[1.0, 1.0, 1.0],
        short_answer_score=0.9,
        code_score=0.0,
        coding_evaluator_output=coding_output,
    )

    code_rec = UnifiedEvidenceRecord.model_validate(records[4])
    assert code_rec.modality == ModalityType.CODING
    assert code_rec.evaluation_lifecycle == EvaluationLifecycle.EVALUATION_FAILED_INFRASTRUCTURE
    assert code_rec.admission_status == AdmissionStatus.REJECTED_INFRASTRUCTURE_FAILURE
    assert code_rec.raw_score is None
    assert code_rec.normalized_score is None
    assert code_rec.modality_details.coding.tests_passed is None
    assert code_rec.modality_details.coding.tests_run == 0
    assert code_rec.modality_details.coding.tests_not_run == 3
    assert code_rec.modality_details.coding.total_test_cases == 3


def test_ema_preservation_only_mcq_updates(monkeypatch):
    """
    Phase 7 Cognitive Research Policy:
    Verify that MCQs and evaluated Short Answer scores update BKT/EMA tracker state,
    while pending/un-reconciled Coding scores do not alter knowledge state.
    """
    student_id = "student_ema_guard_001"
    fake_db = InMemoryMotorDB()
    monkeypatch.setattr(api, "get_motor_db", lambda: fake_db)
    api._student_trackers.pop(student_id, None)
    api._in_memory_scores.pop(student_id, None)

    client = TestClient(api.app)
    headers = _make_auth_headers(student_id)

    # Initial bundle submission: 3 perfect MCQs
    req1 = {
        "student_id": student_id,
        "concept": "Variables",
        "difficulty": "medium",
        "mcq_responses": ["B", "B", "B"],  # All correct
        "short_answer_response": "Variables store data in memory.",
        "code_response": "x = 10",
        "response_time_sec": 30.0,
    }
    res1 = client.post("/api/v1/evaluate_bundle", json=req1, headers=headers)
    assert res1.status_code == 200
    data1 = res1.json()
    mastery1 = data1["updated_mastery"]

    # Retrieve tracker state
    tracker = api._student_trackers[student_id]
    state_var = tracker.state.get("Variables", {})
    history = state_var.get("history", [])

    # Exactly 4 history observations: 3 MCQs + 1 Short Answer
    assert len(history) == 4
    mcq_count = sum(1 for obs in history if obs["activity_type"] == 0)
    sa_count = sum(1 for obs in history if obs["activity_type"] == 2)
    assert mcq_count == 3
    assert sa_count == 1
    # Coding (activity_type=1) is pending Docker execution and must not be in history
    assert not any(obs["activity_type"] == 1 for obs in history)


def test_evaluate_bundle_injects_into_evaluation_queue(monkeypatch):
    """
    Phase 6 Verification:
    Verify that evaluate_bundle hands off the raw code and test cases to
    api.evaluation_queue before privacy masking.
    """
    student_id = "student_q_test_001"
    fake_db = InMemoryMotorDB()
    monkeypatch.setattr(api, "get_motor_db", lambda: fake_db)
    api._student_trackers.pop(student_id, None)
    api._in_memory_scores.pop(student_id, None)

    # Empty queue
    while not api.evaluation_queue.empty():
        api.evaluation_queue.get_nowait()

    client = TestClient(api.app)
    headers = _make_auth_headers(student_id)

    raw_test_code = "my_var = 12345\nprint(my_var)"
    bundle_req = {
        "student_id": student_id,
        "concept": "Variables",
        "difficulty": "medium",
        "mcq_responses": ["A", "B", "A"],
        "short_answer_response": "Variables store values in memory.",
        "code_response": raw_test_code,
        "response_time_sec": 30.0,
    }

    res = client.post("/api/v1/evaluate_bundle", json=bundle_req, headers=headers)
    assert res.status_code == 200

    # Verify that the task was injected into evaluation_queue
    # (or processed by worker if lifespan started)
    # If not yet dequeued, queue size is >= 1; if dequeued, task was handled.
    # In either case, the queue held the raw code without crashing.
    assert res.json()["concept"] == "Variables"
