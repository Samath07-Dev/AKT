"""
test_bkt_version_locking.py

Isolated regression tests for BKT/EMA optimistic locking (`student_states.version`),
new student registration, legacy/null version recovery, idempotency, and retry safety.

Uses an in-memory async MongoDB double so no real database (`akt_tutor` or
`akt_tutor_test`) is ever modified during test execution.
"""

import asyncio
import copy
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

import api
from conftest import TEST_SERVICE_SECRET
from src.engine.knowledge_state import KnowledgeStateTracker


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
    def __init__(self, initial_docs=None, unique_fields=()):
        self.docs = []
        self.unique_fields = tuple(unique_fields)
        for idx, d in enumerate(initial_docs or []):
            stored = copy.deepcopy(d)
            stored.setdefault("_id", f"seed_id_{idx + 1}")
            self.docs.append(stored)
        self.on_before_update = None
        self.on_before_insert = None

    def _matches(self, doc, query):
        for k, v in (query or {}).items():
            if k == "$or":
                if not any(self._matches(doc, branch) for branch in v):
                    return False
            elif isinstance(v, dict):
                if "$exists" in v:
                    exists = k in doc
                    if exists != bool(v["$exists"]):
                        return False
                else:
                    return False
            elif v is None:
                # MongoDB equality `{"field": None}` matches missing or explicit None
                if doc.get(k) is not None:
                    return False
            elif doc.get(k) != v:
                return False
        return True

    async def count_documents(self, query=None):
        return sum(1 for d in self.docs if self._matches(d, query))

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
        if self.on_before_insert is not None:
            self.on_before_insert(self, doc)
        for uf in self.unique_fields:
            val = doc.get(uf)
            if val is not None and any(d.get(uf) == val for d in self.docs):
                raise DuplicateKeyError(f"E11000 duplicate key error on {uf}={val}")
        stored = copy.deepcopy(doc)
        stored.setdefault("_id", f"fake_id_{len(self.docs) + 1}")
        self.docs.append(stored)
        return stored

    async def update_one(self, query, update, upsert=False):
        if self.on_before_update is not None:
            self.on_before_update(self, query, update)
        for doc in self.docs:
            if self._matches(doc, query):
                if "$set" in update:
                    doc.update(copy.deepcopy(update["$set"]))
                if "$inc" in update:
                    for k, delta in update["$inc"].items():
                        doc[k] = doc.get(k, 0) + delta
                return type("Res", (), {"matched_count": 1})()
        if upsert:
            new_doc = {}
            for k, v in (query or {}).items():
                if not k.startswith("$") and not isinstance(v, dict):
                    new_doc[k] = copy.deepcopy(v)
            if "$set" in update:
                new_doc.update(copy.deepcopy(update["$set"]))
            if "$setOnInsert" in update:
                new_doc.update(copy.deepcopy(update["$setOnInsert"]))
            if "$inc" in update:
                for k, delta in update["$inc"].items():
                    new_doc[k] = new_doc.get(k, 0) + delta
            new_doc.setdefault("_id", f"fake_id_{len(self.docs) + 1}")
            self.docs.append(new_doc)
            return type("Res", (), {"matched_count": 1})()
        return type("Res", (), {"matched_count": 0})()


class InMemoryMotorDB:
    def __init__(self, collections=None):
        self._collections = {
            "scores": InMemoryAsyncCollection(unique_fields=("submission_id",)),
            "student_states": InMemoryAsyncCollection(unique_fields=("student_id",)),
            "users": InMemoryAsyncCollection(),
        }
        if collections:
            for name, docs in collections.items():
                unique_fields = (
                    ("student_id",) if name == "student_states"
                    else ("submission_id",) if name == "scores"
                    else ()
                )
                self._collections[name] = InMemoryAsyncCollection(docs, unique_fields=unique_fields)

    def __getitem__(self, name):
        if name not in self._collections:
            self._collections[name] = InMemoryAsyncCollection()
        return self._collections[name]


def _setup_isolated_env(monkeypatch, collections=None):
    fake_db = InMemoryMotorDB(collections)
    monkeypatch.setattr(api, "get_motor_db", lambda: fake_db)
    api._in_memory_users.clear()
    api._in_memory_scores.clear()
    api._in_memory_student_states.clear()
    api._student_trackers.clear()
    return fake_db


def _auth_headers(student_id: str):
    return {
        "X-Internal-Service-Secret": TEST_SERVICE_SECRET,
        "X-Authenticated-Student-Id": student_id,
    }


def test_1_and_2_registration_sets_version_1_and_first_assessment_increments(monkeypatch):
    """
    1. New registration creates student_states.version = 1.
    2. First assessment updates mastery successfully and increments version to 2.
    """
    fake_db = _setup_isolated_env(monkeypatch)
    client = TestClient(api.app)
    client.headers["X-Internal-Service-Secret"] = TEST_SERVICE_SECRET

    reg_res = client.post(
        "/api/v1/register",
        json={"username": "new_student_v1", "password": "Password123!", "full_name": "New Student"},
    )
    assert reg_res.status_code == 200
    student_id = reg_res.json()["student_id"]

    state_doc = next(d for d in fake_db["student_states"].docs if d["student_id"] == student_id)
    assert state_doc["version"] == 1

    rec_res = client.post(
        f"/api/v1/student/{student_id}/record_score",
        json={
            "submission_id": f"sub_{student_id}_first",
            "concept": "Variables",
            "difficulty": "medium",
            "bundle_average_score": 60.0,
            "mcq_scores": [1.0, 0.0, 0.0],
            "short_answer_score": 0.0,
            "code_score": 0.0,
        },
        headers={"X-Authenticated-Student-Id": student_id},
    )
    assert rec_res.status_code == 200
    data = rec_res.json()
    assert data["bkt_processed"] is True
    assert data["attempts"] == 4
    # 3 MCQs: 0.30 -> 0.44 -> 0.352 -> 0.2816; Short Answer 0.0: -> 0.2394
    assert round(data["mastery"], 4) == 0.2394

    updated_state = next(d for d in fake_db["student_states"].docs if d["student_id"] == student_id)
    assert updated_state["version"] == 2

    score_doc = fake_db["scores"].docs[0]
    assert score_doc["bkt_processed"] is True
    assert score_doc["bkt_observations_applied"] == 4


def test_3_existing_document_without_version_updates_safely(monkeypatch):
    """3. Existing student_states document without a version field can be updated safely."""
    student_id = "S_LEGACY_NO_VER"
    fake_db = _setup_isolated_env(
        monkeypatch,
        collections={
            "student_states": [
                {
                    "student_id": student_id,
                    "knowledge_state": api.get_initial_mastery_state(),
                    "concept_difficulties": api.get_initial_concept_difficulties(),
                    "updated_at": "2026-11-08T15:39:39.751366+00:00",
                }
            ]
        },
    )
    client = TestClient(api.app)
    res = client.post(
        f"/api/v1/student/{student_id}/record_score",
        json={
            "submission_id": "sub_legacy_no_ver_1",
            "concept": "Variables",
            "difficulty": "medium",
            "bundle_average_score": 100.0,
            "mcq_scores": [1.0],
            "short_answer_score": 100.0,
            "code_score": 0.0,
        },
        headers=_auth_headers(student_id),
    )
    assert res.status_code == 200
    assert res.json()["bkt_processed"] is True
    # 3 MCQs [1.0, 0.0, 0.0] -> 0.2816; Short Answer 1.0 -> 0.4612
    assert round(res.json()["mastery"], 4) == 0.4612

    state_doc = fake_db["student_states"].docs[0]
    assert state_doc["version"] == 1
    assert fake_db["scores"].docs[0]["bkt_processed"] is True


def test_4_existing_document_with_null_version_updates_safely(monkeypatch):
    """4. Existing student_states document with version: None can be updated safely."""
    student_id = "S_LEGACY_NULL_VER"
    fake_db = _setup_isolated_env(
        monkeypatch,
        collections={
            "student_states": [
                {
                    "student_id": student_id,
                    "knowledge_state": api.get_initial_mastery_state(),
                    "concept_difficulties": api.get_initial_concept_difficulties(),
                    "version": None,
                    "updated_at": "2026-11-08T15:39:39.751366+00:00",
                }
            ]
        },
    )
    client = TestClient(api.app)
    res = client.post(
        f"/api/v1/student/{student_id}/record_score",
        json={
            "submission_id": "sub_legacy_null_ver_1",
            "concept": "Loops",
            "difficulty": "easy",
            "bundle_average_score": 0.0,
            "mcq_scores": [0.0],
            "short_answer_score": 0.0,
            "code_score": 0.0,
        },
        headers=_auth_headers(student_id),
    )
    assert res.status_code == 200
    assert res.json()["bkt_processed"] is True
    # 3 MCQs [0.0, 0.0, 0.0] -> 0.1536; Short Answer 0.0 -> 0.1306
    assert round(res.json()["mastery"], 4) == 0.1306

    state_doc = fake_db["student_states"].docs[0]
    assert state_doc["version"] == 1
    assert fake_db["scores"].docs[0]["bkt_processed"] is True


def test_5_real_optimistic_lock_conflict_returns_409(monkeypatch):
    """5. True optimistic-lock conflicts (versioned and concurrent unversioned) return HTTP 409."""
    student_id = "S_CONFLICT_VER"
    fake_db = _setup_isolated_env(
        monkeypatch,
        collections={
            "student_states": [
                {
                    "student_id": student_id,
                    "knowledge_state": api.get_initial_mastery_state(),
                    "version": 2,
                }
            ]
        },
    )
    tracker = KnowledgeStateTracker()

    # Stale expected_version=1 against DB version=2 -> HTTP 409
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            api.persist_student_mastery_state(
                student_id=student_id,
                tracker_instance=tracker,
                expected_version=1,
            )
        )
    assert exc_info.value.status_code == 409

    # Simulate concurrent writer racing between find_one and update_one on an unversioned doc
    student_unver = "S_CONFLICT_UNVER"
    fake_db["student_states"].docs.append(
        {
            "student_id": student_unver,
            "knowledge_state": api.get_initial_mastery_state(),
        }
    )

    def simulate_concurrent_writer(coll, query, update):
        if query.get("student_id") == student_unver:
            for d in coll.docs:
                if d["student_id"] == student_unver:
                    d["version"] = 1
            coll.on_before_update = None

    fake_db["student_states"].on_before_update = simulate_concurrent_writer

    with pytest.raises(HTTPException) as exc_unver:
        asyncio.run(
            api.persist_student_mastery_state(
                student_id=student_unver,
                tracker_instance=tracker,
                expected_version=0,
            )
        )
    assert exc_unver.value.status_code == 409


def test_6_replaying_same_submission_id_does_not_duplicate_scores(monkeypatch):
    """6. Replaying the same submission_id returns idempotent replay without duplicate scores."""
    student_id = "S_REPLAY_1"
    fake_db = _setup_isolated_env(
        monkeypatch,
        collections={
            "student_states": [
                {
                    "student_id": student_id,
                    "knowledge_state": api.get_initial_mastery_state(),
                    "version": 1,
                }
            ]
        },
    )
    client = TestClient(api.app)
    payload = {
        "submission_id": "sub_replay_unique",
        "concept": "Syntax",
        "difficulty": "medium",
        "bundle_average_score": 100.0,
        "mcq_scores": [1.0],
        "short_answer_score": 100.0,
        "code_score": 0.0,
    }
    res1 = client.post(
        f"/api/v1/student/{student_id}/record_score",
        json=payload,
        headers=_auth_headers(student_id),
    )
    assert res1.status_code == 200
    assert round(res1.json()["mastery"], 4) == 0.4612

    res2 = client.post(
        f"/api/v1/student/{student_id}/record_score",
        json=payload,
        headers=_auth_headers(student_id),
    )
    assert res2.status_code == 200
    assert res2.json().get("replayed") is True
    assert round(res2.json()["mastery"], 4) == 0.4612
    assert res2.json()["attempts"] == 4
    assert len(fake_db["scores"].docs) == 1
    assert fake_db["student_states"].docs[0]["version"] == 2


def test_7_reconciliation_applies_pending_observations_once(monkeypatch):
    """7. Pending reconciliation processes multiple bkt_processed=False records chronologically once."""
    student_id = "S_RECON_ONCE"
    fake_db = _setup_isolated_env(
        monkeypatch,
        collections={
            "student_states": [
                {
                    "student_id": student_id,
                    "knowledge_state": api.get_initial_mastery_state(),
                }
            ],
            "scores": [
                {
                    "submission_id": "sub_pending_1",
                    "student_id": student_id,
                    "concept": "Functions",
                    "difficulty": "medium",
                    "bundle_average_score": 100.0,
                    "mcq_scores": [1.0],
                    "short_answer_score": 100.0,
                    "code_score": 0.0,
                    "timestamp": "2026-11-12T10:00:00.000Z",
                    "bkt_processed": False,
                    "bkt_processed_at": None,
                    "bkt_observations_applied": 0,
                }
            ],
        },
    )
    client = TestClient(api.app)
    res = client.post(
        f"/api/v1/student/{student_id}/record_score",
        json={
            "submission_id": "sub_pending_2",
            "concept": "Functions",
            "difficulty": "medium",
            "bundle_average_score": 0.0,
            "mcq_scores": [0.0],
            "short_answer_score": 0.0,
            "code_score": 0.0,
            "timestamp": "2026-11-12T10:05:00.000Z",
        },
        headers=_auth_headers(student_id),
    )
    assert res.status_code == 200
    data = res.json()
    # sub_pending_1 (legacy doc: 1 MCQ 1.0 -> 0.44) + sub_pending_2 (bundle: 3 MCQs 0.0 + 1 SA 0.0 -> 0.1915)
    assert round(data["mastery"], 4) == 0.1915
    assert data["attempts"] == 5
    assert all(d["bkt_processed"] is True for d in fake_db["scores"].docs)
    assert fake_db["scores"].docs[0]["bkt_observations_applied"] == 1
    assert fake_db["scores"].docs[1]["bkt_observations_applied"] == 4
    assert fake_db["student_states"].docs[0]["version"] == 2


def test_8_failed_state_persistence_does_not_duplicate_on_retry(monkeypatch):
    """8. Failed state persistence (409) leaves score unprocessed and retry applies observations once."""
    student_id = "S_FAIL_RETRY"
    fake_db = _setup_isolated_env(
        monkeypatch,
        collections={
            "student_states": [
                {
                    "student_id": student_id,
                    "knowledge_state": api.get_initial_mastery_state(),
                }
            ]
        },
    )
    orig_persist = api.persist_student_mastery_state

    async def fail_once(*args, **kwargs):
        raise HTTPException(status_code=409, detail="Simulated transient 409 lock conflict")

    monkeypatch.setattr(api, "persist_student_mastery_state", fail_once)
    client = TestClient(api.app)

    payload = {
        "submission_id": "sub_fail_then_retry",
        "concept": "Arrays",
        "difficulty": "medium",
        "bundle_average_score": 100.0,
        "mcq_scores": [1.0, 1.0, 1.0],
        "short_answer_score": 100.0,
        "code_score": 0.0,
    }
    res_fail = client.post(
        f"/api/v1/student/{student_id}/record_score",
        json=payload,
        headers=_auth_headers(student_id),
    )
    assert res_fail.status_code == 409
    assert len(fake_db["scores"].docs) == 1
    assert fake_db["scores"].docs[0]["bkt_processed"] is False
    assert fake_db["student_states"].docs[0]["knowledge_state"]["Arrays"]["mastery"] == 0.30

    # Restore persist and retry identical submission_id
    monkeypatch.setattr(api, "persist_student_mastery_state", orig_persist)
    res_ok = client.post(
        f"/api/v1/student/{student_id}/record_score",
        json=payload,
        headers=_auth_headers(student_id),
    )
    assert res_ok.status_code == 200
    data = res_ok.json()
    assert data["bkt_processed"] is True
    # Applied exactly once: 3 MCQs (1.0 -> 0.6416) + 1 SA (1.0 -> 0.7312)
    assert round(data["mastery"], 4) == 0.7312
    assert data["attempts"] == 4
    assert len(fake_db["scores"].docs) == 1
    assert fake_db["scores"].docs[0]["bkt_processed"] is True
    assert fake_db["scores"].docs[0]["bkt_observations_applied"] == 4


def test_9_existing_versioned_documents_preserve_versioning(monkeypatch):
    """9. Existing integer-versioned documents increment version monotonically (11 -> 12)."""
    student_id = "S_VER_11"
    fake_db = _setup_isolated_env(
        monkeypatch,
        collections={
            "student_states": [
                {
                    "student_id": student_id,
                    "knowledge_state": api.get_initial_mastery_state(),
                    "version": 11,
                }
            ]
        },
    )
    client = TestClient(api.app)
    res = client.post(
        f"/api/v1/student/{student_id}/record_score",
        json={
            "submission_id": "sub_ver_11_next",
            "concept": "OOP",
            "difficulty": "medium",
            "bundle_average_score": 80.0,
            "mcq_scores": [1.0],
            "short_answer_score": 50.0,
            "code_score": 0.0,
        },
        headers=_auth_headers(student_id),
    )
    assert res.status_code == 200
    assert fake_db["student_states"].docs[0]["version"] == 12


def test_10_direct_mastery_upsert_initializes_without_overwriting_version(monkeypatch):
    """10. POST /mastery initializes version=1 on insert and preserves existing integer versions."""
    fake_db = _setup_isolated_env(
        monkeypatch,
        collections={
            "student_states": [
                {
                    "student_id": "S_EXISTING_V5",
                    "knowledge_state": api.get_initial_mastery_state(),
                    "version": 5,
                }
            ]
        },
    )
    client = TestClient(api.app)

    # New student_states document via /mastery upsert -> gets version=1
    res_new = client.post(
        "/api/v1/student/S_NEW_UPSERT/mastery",
        json={"knowledge_state": api.get_initial_mastery_state(), "concept_difficulties": {}},
        headers=_auth_headers("S_NEW_UPSERT"),
    )
    assert res_new.status_code == 200
    new_doc = next(d for d in fake_db["student_states"].docs if d["student_id"] == "S_NEW_UPSERT")
    assert new_doc["version"] == 1

    # Existing versioned document via /mastery upsert -> version=5 must NOT be overwritten
    res_existing = client.post(
        "/api/v1/student/S_EXISTING_V5/mastery",
        json={"knowledge_state": api.get_initial_mastery_state(), "concept_difficulties": {}},
        headers=_auth_headers("S_EXISTING_V5"),
    )
    assert res_existing.status_code == 200
    existing_doc = next(d for d in fake_db["student_states"].docs if d["student_id"] == "S_EXISTING_V5")
    assert existing_doc["version"] == 5


def test_11_failed_update_interaction_does_not_mutate_caches_and_retry_succeeds(monkeypatch):
    """
    11. Failed update_interaction persistence (HTTP 409) leaves _student_trackers,
    student_concept_difficulty, and global tracker un-mutated, and retry succeeds once.
    """
    student_id = "S_UI_CACHE_SAFE"
    fake_db = _setup_isolated_env(
        monkeypatch,
        collections={
            "student_states": [
                {
                    "student_id": student_id,
                    "knowledge_state": api.get_initial_mastery_state(),
                    "concept_difficulties": {"Variables": "medium"},
                    "version": 1,
                }
            ]
        },
    )
    api.student_concept_difficulty[student_id] = {"Variables": "medium"}
    api.tracker.reset_state()
    baseline_global_attempts = api.tracker.state["Variables"]["attempts"]
    baseline_global_mastery = api.tracker.state["Variables"]["mastery"]

    orig_persist = api.persist_student_mastery_state

    async def fail_persist(*args, **kwargs):
        raise HTTPException(status_code=409, detail="Simulated 409 conflict on update_interaction")

    monkeypatch.setattr(api, "persist_student_mastery_state", fail_persist)
    client = TestClient(api.app)

    payload = {
        "student_id": student_id,
        "concept": "Variables",
        "activity_type": "MCQ",
        "student_response": "B",
        "difficulty": "easy",
        "question_id": "Variables_MCQ_Easy_1",
    }
    res_fail = client.post("/api/v1/update_interaction", json=payload, headers=_auth_headers(student_id))
    assert res_fail.status_code == 409

    # Caches and global tracker must reflect ONLY persisted DB state (0.30, 0 attempts)
    cached = api._student_trackers[student_id]
    assert cached.state["Variables"]["mastery"] == 0.30
    assert cached.state["Variables"]["attempts"] == 0
    assert api.student_concept_difficulty[student_id]["Variables"] == "medium"
    assert api.tracker.state["Variables"]["attempts"] == baseline_global_attempts
    assert api.tracker.state["Variables"]["mastery"] == baseline_global_mastery
    assert fake_db["student_states"].docs[0]["version"] == 1

    # Restore persistence and retry -> applies exactly 1 observation (0.30 -> 0.44)
    monkeypatch.setattr(api, "persist_student_mastery_state", orig_persist)
    res_ok = client.post("/api/v1/update_interaction", json=payload, headers=_auth_headers(student_id))
    assert res_ok.status_code == 200
    assert round(res_ok.json()["updated_mastery"], 4) == 0.4400
    assert api._student_trackers[student_id].state["Variables"]["attempts"] == 1
    assert round(api._student_trackers[student_id].state["Variables"]["mastery"], 4) == 0.4400
    assert fake_db["student_states"].docs[0]["version"] == 2


def test_12_failed_evaluate_bundle_does_not_mutate_caches_and_retry_succeeds(monkeypatch):
    """
    12. Failed evaluate_bundle persistence (HTTP 409) leaves caches, global tracker,
    and score ledger untouched, and retry applies the 3 MCQs exactly once.
    """
    student_id = "S_EB_CACHE_SAFE"
    fake_db = _setup_isolated_env(
        monkeypatch,
        collections={
            "student_states": [
                {
                    "student_id": student_id,
                    "knowledge_state": api.get_initial_mastery_state(),
                    "concept_difficulties": {"Functions": "medium"},
                    "version": 1,
                }
            ]
        },
    )
    api.student_concept_difficulty[student_id] = {"Functions": "medium"}
    api.tracker.reset_state()
    baseline_global_attempts = api.tracker.state["Functions"]["attempts"]

    monkeypatch.setattr(
        api.short_answer_analyzer,
        "evaluate",
        lambda student_response, reference_answer: {
            "evidence_score": 0.9,
            "similarity_percentage": 90.0,
            "missing_keywords": [],
            "is_acceptable": True,
            "feedback": "Strong answer",
            "model_used": "mock",
        },
    )

    orig_persist = api.persist_student_mastery_state

    async def fail_persist(*args, **kwargs):
        raise HTTPException(status_code=409, detail="Simulated 409 conflict on evaluate_bundle")

    monkeypatch.setattr(api, "persist_student_mastery_state", fail_persist)
    client = TestClient(api.app)

    bundle_payload = {
        "student_id": student_id,
        "concept": "Functions",
        "difficulty": "medium",
        "mcq_responses": ["B", "C", "A"],
        "short_answer_response": "Functions break programs into reusable blocks.",
        "code_response": "def factorial(n):\n    return 1\n",
        "passed_test_cases": 0,
        "total_test_cases": 3,
    }
    res_fail = client.post("/api/v1/evaluate_bundle", json=bundle_payload, headers=_auth_headers(student_id))
    assert res_fail.status_code == 409

    # Caches, global tracker, difficulty map, and scores must remain untouched
    cached = api._student_trackers[student_id]
    assert cached.state["Functions"]["mastery"] == 0.30
    assert cached.state["Functions"]["attempts"] == 0
    assert api.student_concept_difficulty[student_id]["Functions"] == "medium"
    assert api.tracker.state["Functions"]["attempts"] == baseline_global_attempts
    assert len(fake_db["scores"].docs) == 0
    assert fake_db["student_states"].docs[0]["version"] == 1

    # Retry after restoring persistence -> applies bundle once (3 MCQs + 1 Short Answer -> 0.7062)
    monkeypatch.setattr(api, "persist_student_mastery_state", orig_persist)
    res_ok = client.post("/api/v1/evaluate_bundle", json=bundle_payload, headers=_auth_headers(student_id))
    assert res_ok.status_code == 200
    assert round(res_ok.json()["updated_mastery"], 4) == 0.7062
    assert api._student_trackers[student_id].state["Functions"]["attempts"] == 4
    assert len(fake_db["scores"].docs) == 1
    assert fake_db["scores"].docs[0]["bkt_processed"] is True
    assert fake_db["student_states"].docs[0]["version"] == 2


def test_13_concurrent_initial_inserts_do_not_create_duplicate_student_states(monkeypatch):
    """
    13. Two concurrent initializations for the same student_id do not create duplicate
    student_states documents and preserve optimistic locking via HTTP 409.
    """
    student_id = "S_CONCURRENT_INIT"
    fake_db = _setup_isolated_env(monkeypatch)
    tracker_a = KnowledgeStateTracker()
    tracker_b = KnowledgeStateTracker()

    # Simulate Worker A inserting between Worker B's find_one(None) and insert_one()
    def simulate_competing_worker_insert(coll, doc):
        if doc.get("student_id") == student_id:
            coll.on_before_insert = None
            coll.docs.append(
                {
                    "_id": "worker_a_doc",
                    "student_id": student_id,
                    "knowledge_state": tracker_a.get_knowledge_state(),
                    "version": 1,
                }
            )

    fake_db["student_states"].on_before_insert = simulate_competing_worker_insert

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            api.persist_student_mastery_state(
                student_id=student_id,
                tracker_instance=tracker_b,
                expected_version=0,
            )
        )
    assert exc_info.value.status_code == 409
    matching = [d for d in fake_db["student_states"].docs if d["student_id"] == student_id]
    assert len(matching) == 1
    assert matching[0]["_id"] == "worker_a_doc"
    assert matching[0]["version"] == 1


def test_14_duplicate_key_race_recovery_on_initial_record_score(monkeypatch):
    """
    14. DuplicateKeyError during initial insert returns HTTP 409 cleanly without losing
    or duplicating the score, and a subsequent retry recovers from DB version=1.
    """
    student_id = "S_DUP_RACE_REC"
    fake_db = _setup_isolated_env(monkeypatch)
    client = TestClient(api.app)

    # Worker 1 wins the race to create student_states (version=1) right before Worker 2's insert_one
    def worker1_wins_insert(coll, doc):
        if doc.get("student_id") == student_id:
            coll.on_before_insert = None
            coll.docs.append(
                {
                    "_id": "worker1_state",
                    "student_id": student_id,
                    "knowledge_state": api.get_initial_mastery_state(),
                    "version": 1,
                }
            )

    fake_db["student_states"].on_before_insert = worker1_wins_insert

    payload = {
        "submission_id": "sub_dup_race_1",
        "concept": "Variables",
        "difficulty": "medium",
        "bundle_average_score": 100.0,
        "mcq_scores": [1.0],
        "short_answer_score": 100.0,
        "code_score": 0.0,
    }

    res_race = client.post(
        f"/api/v1/student/{student_id}/record_score",
        json=payload,
        headers=_auth_headers(student_id),
    )
    assert res_race.status_code == 409
    assert len(fake_db["student_states"].docs) == 1
    assert len(fake_db["scores"].docs) == 1
    assert fake_db["scores"].docs[0]["bkt_processed"] is False

    # Retry identical submission -> reloads Worker 1's version=1, applies once, increments to 2
    res_retry = client.post(
        f"/api/v1/student/{student_id}/record_score",
        json=payload,
        headers=_auth_headers(student_id),
    )
    assert res_retry.status_code == 200
    data = res_retry.json()
    assert data["bkt_processed"] is True
    assert round(data["mastery"], 4) == 0.4612
    assert data["attempts"] == 4
    assert len(fake_db["student_states"].docs) == 1
    assert fake_db["student_states"].docs[0]["version"] == 2
    assert len(fake_db["scores"].docs) == 1
    assert fake_db["scores"].docs[0]["bkt_processed"] is True


