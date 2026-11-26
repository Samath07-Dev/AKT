"""
test_history_coding_status.py

Isolated regression tests for FastAPI coding evaluation metadata persistence,
history retrieval normalization, sandbox quarantine, and BKT/EMA preservation.

Uses an in-memory async MongoDB double so no real database (`akt_tutor` or
`akt_tutor_test`) is ever written to or modified during test execution.
"""

import builtins
import copy
import os
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

import api
from conftest import TEST_SERVICE_SECRET
from src.analyzers import CodeAnalyzer


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
    def __init__(self, initial_docs=None):
        self.docs = [copy.deepcopy(d) for d in (initial_docs or [])]

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


def test_pending_coding_metadata_persisted_and_returned(monkeypatch):
    """
    Verifies that pending coding evaluation metadata forwarded to /record_score
    is persisted in db['scores'] and returned by /student/{id}/history.
    """
    student_id = "S_ISO_PENDING_1"
    fake_db = InMemoryMotorDB()
    monkeypatch.setattr(api, "get_motor_db", lambda: fake_db)
    api._student_trackers.pop(student_id, None)
    api._in_memory_scores.pop(student_id, None)

    client = TestClient(api.app)
    headers = _make_auth_headers(student_id)

    payload = {
        "submission_id": "sub_S_ISO_PENDING_1_oop",
        "student_id": student_id,
        "concept": "OOP",
        "difficulty": "medium",
        "bundle_average_score": 93.5,
        "mcq_scores": [1.0, 1.0, 1.0],
        "short_answer_score": 83.8,
        "code_score": 0.0,
        "code_status": "PENDING_SECURE_EVALUATION",
        "code_execution_status": "NOT_PERFORMED",
        "code_tests_passed": 0,
        "code_tests_total": 2,
        "syntax_preview_passed": True,
        "syntax_preview_count": 2,
        "next_difficulty": "hard",
        "scaffolding_reasoning": "High mastery demonstrated (>= 80%) -> Scaffolding up to Hard.",
        "timestamp": "2026-11-12T12:00:00.000Z",
    }

    post_res = client.post(
        f"/api/v1/student/{student_id}/record_score",
        json=payload,
        headers=headers,
    )
    assert post_res.status_code == 200
    post_data = post_res.json()
    assert post_data["status"] == "success"
    # Phase 7: Modality-Weighted Alpha updates (3 MCQs: 0.30 -> 0.44 -> 0.552 -> 0.6416; Short Answer 0.838: -> 0.6907)
    assert round(post_data["mastery"], 4) == 0.6907
    assert post_data["attempts"] == 4

    # Verify persisted MongoDB document directly
    stored_docs = fake_db["scores"].docs
    assert len(stored_docs) == 1
    doc = stored_docs[0]
    assert doc["code_status"] == "PENDING_SECURE_EVALUATION"
    assert doc["code_execution_status"] == "NOT_PERFORMED"
    assert doc["code_tests_passed"] == 0
    assert doc["code_tests_total"] == 2
    assert doc["code_score"] == 0.0

    # Verify history endpoint returns exact coding metadata
    hist_res = client.get(f"/api/v1/student/{student_id}/history", headers=headers)
    assert hist_res.status_code == 200
    history = hist_res.json()["history"]
    assert len(history) == 1
    item = history[0]
    assert item["code_status"] == "PENDING_SECURE_EVALUATION"
    assert item["code_execution_status"] == "NOT_PERFORMED"
    assert item["code_tests_passed"] == 0
    assert item["code_tests_total"] == 2
    assert item["code_score"] == 0.0


def test_legacy_and_historical_records_normalized_without_rewriting_db(monkeypatch):
    """
    Verifies that legacy spaced/hyphenated/camelCase records and historical records
    missing coding metadata are read safely without rewriting stored DB documents.
    """
    student_id = "S_ISO_LEGACY_1"
    legacy_spaced_doc = {
        "_id": "legacy_1",
        "submission_id": "sub_legacy_spaced",
        "student_id": student_id,
        "concept": "Loops",
        "difficulty": "medium",
        "bundle_average_score": 82.0,
        "mcq_scores": [1.0, 1.0, 0.0],
        "short_answer_score": 85.0,
        "code_score": 0.0,
        "codeStatus": "pending-secure evaluation",
        "codeExecutionStatus": "SANDBOX_OFFLINE",
        "codeTestsPassed": 0,
        "codeTestsTotal": 3,
        "timestamp": "2026-11-12T11:00:00.000Z",
    }
    historical_missing_meta_doc = {
        "_id": "legacy_2",
        "submission_id": "sub_historical_missing",
        "student_id": student_id,
        "concept": "OOP",
        "difficulty": "medium",
        "bundle_average_score": 93.5,
        "mcq_scores": [1.0, 1.0, 1.0],
        "short_answer_score": 83.8,
        "code_score": 0.0,
        "timestamp": "2026-11-12T09:38:35.232Z",
    }
    evaluated_zero_doc = {
        "_id": "eval_zero_1",
        "submission_id": "sub_eval_zero",
        "student_id": student_id,
        "concept": "OOP",
        "difficulty": "medium",
        "bundle_average_score": 70.0,
        "mcq_scores": [1.0, 1.0, 0.0],
        "short_answer_score": 75.0,
        "code_score": 0.0,
        "code_status": "EVALUATED",
        "code_execution_status": "EXECUTED",
        "code_tests_passed": 0,
        "code_tests_total": 2,
        "timestamp": "2026-11-12T10:00:00.000Z",
    }

    initial_scores = [legacy_spaced_doc, historical_missing_meta_doc, evaluated_zero_doc]
    snapshot_before = copy.deepcopy(initial_scores)

    fake_db = InMemoryMotorDB({"scores": initial_scores})
    monkeypatch.setattr(api, "get_motor_db", lambda: fake_db)
    api._in_memory_scores.pop(student_id, None)

    client = TestClient(api.app)
    headers = _make_auth_headers(student_id)

    hist_res = client.get(f"/api/v1/student/{student_id}/history", headers=headers)
    assert hist_res.status_code == 200
    history = hist_res.json()["history"]
    assert len(history) == 3

    by_id = {h["submission_id"]: h for h in history}

    # 1. Legacy spaced/hyphenated/camelCase normalized on read
    assert by_id["sub_legacy_spaced"]["code_status"] == "PENDING_SECURE_EVALUATION"
    assert by_id["sub_legacy_spaced"]["code_execution_status"] == "SANDBOX_OFFLINE"
    assert by_id["sub_legacy_spaced"]["code_tests_passed"] == 0
    assert by_id["sub_legacy_spaced"]["code_tests_total"] == 3

    # 2. Historical missing metadata must NOT fabricate status or test counts
    hist_missing = by_id["sub_historical_missing"]
    assert "code_status" not in hist_missing
    assert "code_execution_status" not in hist_missing
    assert "code_tests_passed" not in hist_missing
    assert "code_tests_total" not in hist_missing
    assert hist_missing["code_score"] == 0.0

    # 3. Genuine evaluated zero remains intact
    eval_zero = by_id["sub_eval_zero"]
    assert eval_zero["code_status"] == "EVALUATED"
    assert eval_zero["code_execution_status"] == "EXECUTED"
    assert eval_zero["code_tests_passed"] == 0
    assert eval_zero["code_tests_total"] == 2
    assert eval_zero["code_score"] == 0.0

    # 4. Stored DB documents were NOT rewritten
    assert fake_db["scores"].docs == snapshot_before


def test_sandbox_offline_security_remains_enforced():
    """Verifies SANDBOX_OFFLINE quarantine prevents host execution, exec(), and eval()."""
    orig_exec = builtins.exec
    orig_eval = builtins.eval
    calls = []

    def fail_exec(*args, **kwargs):
        calls.append("exec")
        raise AssertionError("exec() called")

    def fail_eval(*args, **kwargs):
        calls.append("eval")
        raise AssertionError("eval() called")

    with tempfile.TemporaryDirectory() as tmp_dir:
        sentinel = Path(tmp_dir) / "should_not_exist.txt"
        payload = f"import pathlib\npathlib.Path({repr(str(sentinel))}).write_text('BREACH')\n"
        analyzer = CodeAnalyzer()
        assert analyzer.host_execution_enabled is False

        builtins.exec = fail_exec
        builtins.eval = fail_eval
        try:
            res = analyzer.evaluate(
                code_string=payload,
                test_cases=[{"call": "dummy()", "expected": 1}],
            )
        finally:
            builtins.exec = orig_exec
            builtins.eval = orig_eval

        assert not sentinel.exists()
        assert calls == []
        assert res["execution_status"] == "DISABLED"
        assert res["evidence_score"] == 0.0
        assert res["passed_test_cases"] == 0
        assert res["total_test_cases"] == 0

