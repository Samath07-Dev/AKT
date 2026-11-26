"""
test_sandbox_runner.py

Isolated security, correctness, and FastAPI integration tests for
src/analyzers/sandbox_runner.py and POST /api/v1/evaluate_code.
"""

import json
import os
import subprocess
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import api
from src.analyzers.code_analyzer import CodeAnalyzer
from src.analyzers.sandbox_runner import (
    DOCKER_PYTHON_IMAGE,
    MAX_CODE_LENGTH,
    SecureDockerPythonEvaluator,
    resolve_docker_binary,
)


def _sample_cases():
    return [
        {"call": "sum_two_numbers(2, 3)", "expected": 5, "description": "Positive addition"},
        {"call": "sum_two_numbers(-1, 1)", "expected": 0, "description": "Zero sum"},
        {"call": "sum_two_numbers(0, 0)", "expected": 0, "description": "Zeros"},
    ]


def test_code_analyzer_host_execution_remains_disabled():
    analyzer = CodeAnalyzer()
    assert analyzer.host_execution_enabled is False


def test_sandbox_offline_fails_closed(monkeypatch):
    monkeypatch.setenv("SANDBOX_OFFLINE", "1")
    ev = SecureDockerPythonEvaluator()
    res = ev.evaluate("def sum_two_numbers(a, b):\n    return a + b\n", _sample_cases())
    assert res.code_status == "PENDING_SECURE_EVALUATION"
    assert res.code_execution_status == "NOT_PERFORMED"
    assert res.code_score == 0.0
    assert res.code_tests_passed == 0
    assert res.code_tests_total == 3


def test_docker_unavailable_fails_closed(monkeypatch):
    monkeypatch.setenv("SANDBOX_OFFLINE", "0")
    ev = SecureDockerPythonEvaluator()
    with patch("src.analyzers.sandbox_runner.resolve_docker_binary", return_value=None):
        res = ev.evaluate("def sum_two_numbers(a, b):\n    return a + b\n", _sample_cases())
    assert res.code_status == "PENDING_SECURE_EVALUATION"
    assert res.code_execution_status == "NOT_PERFORMED"
    assert res.code_score == 0.0
    assert res.code_tests_passed == 0


def test_docker_exit_125_fails_closed(monkeypatch):
    monkeypatch.setenv("SANDBOX_OFFLINE", "0")
    ev = SecureDockerPythonEvaluator()
    fake_proc = subprocess.CompletedProcess(args=["docker"], returncode=125, stdout="", stderr="daemon err")
    with patch.object(ev, "is_sandbox_available", return_value=(True, "/usr/bin/docker", None)), patch(
        "src.analyzers.sandbox_runner.subprocess.run", return_value=fake_proc
    ):
        res = ev.evaluate("def sum_two_numbers(a, b):\n    return a + b\n", _sample_cases())
    assert res.code_status == "PENDING_SECURE_EVALUATION"
    assert res.code_execution_status == "NOT_PERFORMED"


def test_correct_and_partial_solutions_in_docker(monkeypatch):
    monkeypatch.setenv("SANDBOX_OFFLINE", "0")
    ev = SecureDockerPythonEvaluator()

    ok_res = ev.evaluate("def sum_two_numbers(a, b):\n    return a + b\n", _sample_cases())
    assert ok_res.code_status == "EVALUATED"
    assert ok_res.code_execution_status == "EXECUTED"
    assert ok_res.code_tests_passed == 3
    assert ok_res.code_tests_total == 3
    assert ok_res.code_score == 100.0
    assert ok_res.syntax_valid is True
    assert ok_res.runtime_error is None

    # Returns 0 cleanly only for (0, 0) and (-1, 1) -> 2/3 pass
    partial_res = ev.evaluate("def sum_two_numbers(a, b):\n    return 0\n", _sample_cases())
    assert partial_res.code_status == "EVALUATED"
    assert partial_res.code_execution_status == "EXECUTED"
    assert partial_res.code_tests_passed == 2
    assert partial_res.code_tests_total == 3
    assert partial_res.code_score == 66.67


def test_all_reference_curriculum_coding_tasks_pass_in_docker(monkeypatch):
    monkeypatch.setenv("SANDBOX_OFFLINE", "0")
    ev = SecureDockerPythonEvaluator()
    with open("data/reference_answers.json", "r", encoding="utf-8") as f:
        refs = json.load(f)

    total_tasks = 0
    for concept, block in refs.items():
        for diff, task in block.get("coding", {}).items():
            total_tasks += 1
            res = ev.evaluate(task["template"], task["test_cases"])
            assert res.code_status == "EVALUATED", f"{concept} {diff} failed status: {res}"
            assert res.code_execution_status == "EXECUTED", f"{concept} {diff} failed exec: {res}"
            assert res.code_tests_passed == res.code_tests_total, f"{concept} {diff} failed tests: {res}"
            assert res.code_score == 100.0
    assert total_tasks == 30


def test_incorrect_solution_and_bool_int_distinction(monkeypatch):
    monkeypatch.setenv("SANDBOX_OFFLINE", "0")
    ev = SecureDockerPythonEvaluator()

    wrong_res = ev.evaluate("def sum_two_numbers(a, b):\n    return a - b\n", _sample_cases())
    assert wrong_res.code_status == "EVALUATED"
    assert wrong_res.code_execution_status == "EXECUTED"
    # Note: 0 - 0 == 0 passes test case 3; test cases 1 and 2 fail
    assert wrong_res.code_tests_passed == 1

    # Bool True must NOT equal integer 1
    bool_cases = [{"call": "ret_val()", "expected": 1, "description": "Expect int 1"}]
    bool_res = ev.evaluate("def ret_val():\n    return True\n", bool_cases)
    assert bool_res.code_tests_passed == 0
    assert bool_res.code_score == 0.0


def test_syntax_error_handled_safely(monkeypatch):
    monkeypatch.setenv("SANDBOX_OFFLINE", "0")
    ev = SecureDockerPythonEvaluator()
    res = ev.evaluate("def broken(:\n    return 1\n", _sample_cases())
    assert res.code_status == "EVALUATED"
    assert res.code_execution_status == "EXECUTED"
    assert res.syntax_valid is False
    assert res.syntax_error and "SyntaxError" in res.syntax_error
    assert res.code_tests_passed == 0
    assert res.code_score == 0.0


def test_runtime_exception_handled_safely(monkeypatch):
    monkeypatch.setenv("SANDBOX_OFFLINE", "0")
    ev = SecureDockerPythonEvaluator()
    res = ev.evaluate("def sum_two_numbers(a, b):\n    return a / 0\n", _sample_cases())
    assert res.code_status == "EVALUATED"
    assert res.code_execution_status == "EXECUTED"
    assert res.code_tests_passed == 0
    assert res.code_score == 0.0
    assert res.runtime_error and "ZeroDivisionError" in res.runtime_error


def test_infinite_loop_timeout_and_container_cleanup(monkeypatch):
    monkeypatch.setenv("SANDBOX_OFFLINE", "0")
    ev = SecureDockerPythonEvaluator(container_timeout_sec=2.5, per_test_timeout_sec=1.5)
    res = ev.evaluate("def sum_two_numbers(a, b):\n    while True:\n        pass\n", _sample_cases())
    assert res.code_status == "EVALUATED"
    assert res.code_execution_status == "EXECUTED"
    assert res.code_tests_passed == 0
    assert res.code_score == 0.0
    assert res.runtime_error and "timed out" in res.runtime_error.lower()

    docker_bin = resolve_docker_binary()
    ps = subprocess.run([docker_bin, "ps", "-a", "--filter", "name=akt_sandbox_", "--format", "{{.Names}}"], capture_output=True, text=True)
    assert ps.stdout.strip() == ""


def test_memory_exhaustion_blocked(monkeypatch):
    monkeypatch.setenv("SANDBOX_OFFLINE", "0")
    ev = SecureDockerPythonEvaluator(container_timeout_sec=4.0, per_test_timeout_sec=3.0)
    res = ev.evaluate(
        "def sum_two_numbers(a, b):\n    data = bytearray(256 * 1024 * 1024)\n    return len(data)\n",
        _sample_cases(),
    )
    assert res.code_status == "EVALUATED"
    assert res.code_execution_status == "EXECUTED"
    assert res.code_tests_passed == 0
    assert res.code_score == 0.0
    assert res.runtime_error is not None


def test_network_access_blocked_inside_container(monkeypatch):
    monkeypatch.setenv("SANDBOX_OFFLINE", "0")
    ev = SecureDockerPythonEvaluator(container_timeout_sec=4.0, per_test_timeout_sec=2.0)
    code = (
        "import socket\n"
        "def try_net():\n"
        "    s = socket.create_connection(('1.1.1.1', 80), timeout=1)\n"
        "    s.close()\n"
        "    return 'connected'\n"
    )
    cases = [{"call": "try_net()", "expected": "connected", "description": "Network check"}]
    res = ev.evaluate(code, cases)
    assert res.code_status == "EVALUATED"
    assert res.code_execution_status == "EXECUTED"
    assert res.code_tests_passed == 0
    assert res.runtime_error is not None


def test_filesystem_restrictions_inside_container(monkeypatch):
    monkeypatch.setenv("SANDBOX_OFFLINE", "0")
    ev = SecureDockerPythonEvaluator()
    cases = [
        {"call": "probe_host()", "expected": "ok", "description": "Host absent"},
        {"call": "probe_rootfs_write()", "expected": "ok", "description": "Read-only rootfs"},
    ]
    code = (
        "import os\n"
        "def probe_host():\n"
        "    return 'leaked' if os.path.exists('/Users/abdulsamath/AKT-recovery-test/api.py') else 'ok'\n"
        "def probe_rootfs_write():\n"
        "    try:\n"
        "        with open('/etc/sandbox_probe', 'w') as f:\n"
        "            f.write('x')\n"
        "        return 'writable'\n"
        "    except OSError:\n"
        "        return 'ok'\n"
    )
    res = ev.evaluate(code, cases)
    assert res.code_status == "EVALUATED"
    assert res.code_execution_status == "EXECUTED"
    assert res.code_tests_passed == 2
    assert res.code_score == 100.0


def test_fastapi_evaluate_code_endpoint_auth_validation_and_hidden_tests(monkeypatch):
    secret = "test-internal-service-secret-32-chars-min"
    monkeypatch.setenv("INTERNAL_SERVICE_SECRET", secret)
    monkeypatch.setenv("SANDBOX_OFFLINE", "0")
    client = TestClient(api.app)

    # 1. Missing secret -> 403
    unauth = client.post(
        "/api/v1/evaluate_code",
        json={"concept": "Variables", "difficulty": "easy", "code_string": "def sum_two_numbers(a, b): return a + b"},
    )
    assert unauth.status_code == 403

    # 2. Invalid concept -> 400
    bad_concept = client.post(
        "/api/v1/evaluate_code",
        headers={"X-Internal-Service-Secret": secret},
        json={"concept": "NotARealConcept", "difficulty": "easy", "code_string": "x = 1"},
    )
    assert bad_concept.status_code == 400

    # 3. Oversized code -> 422 (Pydantic max_length)
    oversized = client.post(
        "/api/v1/evaluate_code",
        headers={"X-Internal-Service-Secret": secret},
        json={"concept": "Variables", "difficulty": "easy", "code_string": "x = 1\n" * (MAX_CODE_LENGTH // 5)},
    )
    assert oversized.status_code == 422

    # 4. Spoofed client expected outputs are ignored; server reference tests rule!
    spoofed = client.post(
        "/api/v1/evaluate_code",
        headers={"X-Internal-Service-Secret": secret},
        json={
            "concept": "Variables",
            "difficulty": "easy",
            "code_string": "def sum_two_numbers(a, b):\n    return 999\n",
            "test_cases": [{"call": "sum_two_numbers(2, 3)", "expected": 999}],
            "expected": 999,
        },
    )
    assert spoofed.status_code == 200
    data = spoofed.json()
    assert data["code_status"] == "EVALUATED"
    assert data["code_execution_status"] == "EXECUTED"
    assert data["code_tests_passed"] == 0
    assert data["code_tests_total"] == 3
    assert data["code_score"] == 0.0

    # 5. Valid solution returns 100.0
    valid = client.post(
        "/api/v1/evaluate_code",
        headers={"X-Internal-Service-Secret": secret},
        json={
            "concept": "Variables",
            "difficulty": "easy",
            "code_string": "def sum_two_numbers(a, b):\n    return a + b\n",
        },
    )
    assert valid.status_code == 200
    vdata = valid.json()
    assert vdata["code_status"] == "EVALUATED"
    assert vdata["code_execution_status"] == "EXECUTED"
    assert vdata["code_tests_passed"] == 3
    assert vdata["code_tests_total"] == 3
    assert vdata["code_score"] == 100.0

    # 6. SANDBOX_OFFLINE=1 via endpoint fails closed to PENDING_SECURE_EVALUATION / NOT_PERFORMED
    monkeypatch.setenv("SANDBOX_OFFLINE", "1")
    offline = client.post(
        "/api/v1/evaluate_code",
        headers={"X-Internal-Service-Secret": secret},
        json={
            "concept": "Variables",
            "difficulty": "easy",
            "code_string": "def sum_two_numbers(a, b):\n    return a + b\n",
        },
    )
    assert offline.status_code == 200
    odata = offline.json()
    assert odata["code_status"] == "PENDING_SECURE_EVALUATION"
    assert odata["code_execution_status"] == "NOT_PERFORMED"
    assert odata["code_score"] == 0.0
    assert DOCKER_PYTHON_IMAGE.startswith("python:3.13-slim@sha256:")

