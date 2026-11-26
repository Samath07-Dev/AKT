"""
test_coding_adapter.py

Isolated unit tests for CodingAdapter (src/evidence_adapters/coding_adapter.py).
Tests compatibility with SecureDockerPythonEvaluator / SandboxEvaluationResult outputs
and canonical UnifiedEvidenceRecord schema.
"""

import pytest
from src.evidence_adapters.coding_adapter import adapt_coding_evaluation
from src.schemas.evidence import (
    ModalityType,
    EvaluationLifecycle,
    AdmissionStatus,
)


def test_coding_adapter_successful_execution():
    """Verifies adaptation of full test success (3/3 tests passed)."""
    mock_eval = {
        "code_status": "EVALUATED",
        "code_execution_status": "EXECUTED",
        "code_score": 1.0,
        "code_tests_passed": 3,
        "code_tests_total": 3,
        "syntax_valid": True,
        "syntax_error": None,
        "runtime_error": None,
        "test_results": [{"passed": True}, {"passed": True}, {"passed": True}],
        "feedback": "All tests passed."
    }
    record = adapt_coding_evaluation(
        evaluator_output=mock_eval,
        submitted_code="def add(a, b): return a + b",
        evidence_id="ev_code_success",
        submission_id="sub_test_1",
        bundle_id="bundle_vars_1",
        student_id="S001",
        item_id="code_1",
        concept_id="python:functions",
        server_receipt_timestamp="2026-11-16T17:00:00Z",
    )

    assert record.evidence_id == "ev_code_success"
    assert record.modality == ModalityType.CODING
    assert record.evaluation_lifecycle == EvaluationLifecycle.EVALUATED_SUCCESS
    assert record.admission_status == AdmissionStatus.PENDING_RESEARCH_POLICY
    assert record.raw_score == 3.0
    assert record.maximum_possible_score == 3.0
    assert record.normalized_score == 1.0
    assert record.correctness is True
    assert record.modality_details.coding.tests_run == 3
    assert record.modality_details.coding.tests_passed == 3
    assert record.modality_details.coding.tests_failed == 0
    assert record.modality_details.coding.tests_not_run == 0


def test_coding_adapter_partial_success():
    """Verifies adaptation of partial test success (2/3 tests passed)."""
    mock_eval = {
        "code_status": "EVALUATED",
        "code_execution_status": "EXECUTED",
        "code_score": 0.67,
        "code_tests_passed": 2,
        "code_tests_total": 3,
        "syntax_valid": True,
        "syntax_error": None,
        "runtime_error": None,
        "test_results": [{"passed": True}, {"passed": True}, {"passed": False}],
        "feedback": "Passed 2/3 tests."
    }
    record = adapt_coding_evaluation(
        evaluator_output=mock_eval,
        submitted_code="def swap(a, b): return b, a",
        evidence_id="ev_code_partial",
        submission_id="sub_test_1",
        bundle_id="bundle_vars_1",
        student_id="S001",
        item_id="code_2",
        concept_id="python:variables",
        server_receipt_timestamp="2026-11-16T17:00:00Z",
    )

    assert record.evaluation_lifecycle == EvaluationLifecycle.EVALUATED_SUCCESS
    assert record.admission_status == AdmissionStatus.PENDING_RESEARCH_POLICY
    assert record.raw_score == 2.0
    assert record.maximum_possible_score == 3.0
    assert abs(record.normalized_score - (2.0 / 3.0)) < 1e-4
    assert record.correctness is False
    assert record.modality_details.coding.tests_run == 3
    assert record.modality_details.coding.tests_passed == 2
    assert record.modality_details.coding.tests_failed == 1
    assert record.modality_details.coding.tests_not_run == 0


def test_coding_adapter_pending_evaluation():
    """Verifies adaptation of pending evaluation (execution deferred)."""
    mock_eval = {
        "code_status": "PENDING_SECURE_EVALUATION",
        "code_execution_status": "NOT_PERFORMED",
        "code_score": 0.0,
        "code_tests_passed": 0,
        "code_tests_total": 4,
        "syntax_valid": True,
        "syntax_error": None,
        "runtime_error": None,
        "test_results": [],
        "feedback": "Evaluation deferred to background queue."
    }
    record = adapt_coding_evaluation(
        evaluator_output=mock_eval,
        submitted_code="def foo(): pass",
        evidence_id="ev_code_pending",
        submission_id="sub_test_1",
        bundle_id="bundle_vars_1",
        student_id="S001",
        item_id="code_3",
        concept_id="python:functions",
        server_receipt_timestamp="2026-11-16T17:00:00Z",
    )

    assert record.evaluation_lifecycle == EvaluationLifecycle.PENDING_EVALUATION
    assert record.admission_status == AdmissionStatus.PENDING_EVALUATION
    assert record.raw_score is None
    assert record.normalized_score is None
    assert record.maximum_possible_score is None
    assert record.correctness is None
    assert record.evaluation_completion_timestamp is None
    assert record.modality_details.coding.tests_run is None
    assert record.modality_details.coding.tests_passed is None
    assert record.modality_details.coding.tests_not_run == 4


def test_coding_adapter_infrastructure_failure():
    """Verifies adaptation of infrastructure failure (Docker offline)."""
    mock_eval = {
        "code_status": "PENDING_SECURE_EVALUATION",
        "code_execution_status": "NOT_PERFORMED",
        "code_score": 0.0,
        "code_tests_passed": 0,
        "code_tests_total": 3,
        "syntax_valid": True,
        "syntax_error": None,
        "runtime_error": "Pinned sandbox image or Docker daemon unavailable.",
        "test_results": [],
        "feedback": "Failed to verify Docker sandbox daemon."
    }
    record = adapt_coding_evaluation(
        evaluator_output=mock_eval,
        submitted_code="def bar(): return 42",
        evidence_id="ev_code_infra",
        submission_id="sub_test_1",
        bundle_id="bundle_vars_1",
        student_id="S001",
        item_id="code_4",
        concept_id="python:functions",
        server_receipt_timestamp="2026-11-16T17:00:00Z",
    )

    assert record.evaluation_lifecycle == EvaluationLifecycle.EVALUATED_FAILED_INFRASTRUCTURE if hasattr(EvaluationLifecycle, "EVALUATED_FAILED_INFRASTRUCTURE") else EvaluationLifecycle.EVALUATION_FAILED_INFRASTRUCTURE
    assert record.admission_status == AdmissionStatus.REJECTED_INFRASTRUCTURE_FAILURE
    assert record.raw_score is None
    assert record.normalized_score is None
    assert record.maximum_possible_score is None
    assert record.correctness is None
    assert record.evaluation_completion_timestamp is None
    assert record.modality_details.coding.tests_run == 0
    assert record.modality_details.coding.tests_passed is None
    assert record.modality_details.coding.tests_failed is None
    assert record.modality_details.coding.tests_not_run == 3


def test_coding_adapter_syntax_error():
    """Verifies adaptation of student syntax errors."""
    mock_eval = {
        "code_status": "EVALUATED",
        "code_execution_status": "NOT_PERFORMED",
        "code_score": 0.0,
        "code_tests_passed": 0,
        "code_tests_total": 3,
        "syntax_valid": False,
        "syntax_error": "SyntaxError: invalid syntax (line 1)",
        "runtime_error": None,
        "test_results": [],
        "feedback": "Syntax error in submitted code."
    }
    record = adapt_coding_evaluation(
        evaluator_output=mock_eval,
        submitted_code="def broken_syntax(:",
        evidence_id="ev_code_syntax",
        submission_id="sub_test_1",
        bundle_id="bundle_vars_1",
        student_id="S001",
        item_id="code_5",
        concept_id="python:syntax",
        server_receipt_timestamp="2026-11-16T17:00:00Z",
    )

    assert record.evaluation_lifecycle == EvaluationLifecycle.EVALUATION_ERROR_STUDENT_CODE
    assert record.admission_status == AdmissionStatus.PENDING_RESEARCH_POLICY
    assert record.raw_score == 0.0
    assert record.normalized_score == 0.0
    assert record.correctness is False
    assert record.modality_details.coding.tests_run == 0
    assert record.modality_details.coding.tests_passed == 0
    assert record.modality_details.coding.tests_not_run == 3


def test_coding_adapter_timeout_error():
    """Verifies adaptation of student code infinite loop / timeout."""
    mock_eval = {
        "code_status": "EVALUATED",
        "code_execution_status": "EXECUTED",
        "code_score": 0.0,
        "code_tests_passed": 0,
        "code_tests_total": 3,
        "syntax_valid": True,
        "syntax_error": None,
        "runtime_error": "Execution timed out after 3.0 seconds.",
        "test_results": [],
        "feedback": "Timeout exceeded."
    }
    record = adapt_coding_evaluation(
        evaluator_output=mock_eval,
        submitted_code="while True: pass",
        evidence_id="ev_code_timeout",
        submission_id="sub_test_1",
        bundle_id="bundle_vars_1",
        student_id="S001",
        item_id="code_6",
        concept_id="python:loops",
        server_receipt_timestamp="2026-11-16T17:00:00Z",
    )

    assert record.evaluation_lifecycle == EvaluationLifecycle.EVALUATION_TIMEOUT_STUDENT_CODE
    assert record.admission_status == AdmissionStatus.PENDING_RESEARCH_POLICY
    assert record.raw_score == 0.0
    assert record.normalized_score == 0.0
    assert record.correctness is False


def test_coding_adapter_deterministic():
    """Verifies deterministic output across multiple invocations."""
    mock_eval = {
        "code_status": "EVALUATED",
        "code_execution_status": "EXECUTED",
        "code_score": 1.0,
        "code_tests_passed": 2,
        "code_tests_total": 2,
        "syntax_valid": True,
        "syntax_error": None,
        "runtime_error": None,
        "test_results": [],
        "feedback": "Success."
    }
    r1 = adapt_coding_evaluation(
        evaluator_output=mock_eval,
        submitted_code="def ok(): pass",
        evidence_id="ev_det",
        submission_id="sub_det",
        bundle_id="bun_det",
        student_id="S001",
        item_id="item_det",
        concept_id="concept_det",
        server_receipt_timestamp="2026-11-16T17:00:00Z",
        evaluation_completion_timestamp="2026-11-16T17:00:03Z",
    )
    r2 = adapt_coding_evaluation(
        evaluator_output=mock_eval,
        submitted_code="def ok(): pass",
        evidence_id="ev_det",
        submission_id="sub_det",
        bundle_id="bun_det",
        student_id="S001",
        item_id="item_det",
        concept_id="concept_det",
        server_receipt_timestamp="2026-11-16T17:00:00Z",
        evaluation_completion_timestamp="2026-11-16T17:00:03Z",
    )

    assert r1 == r2

