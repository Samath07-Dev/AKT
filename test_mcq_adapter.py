"""
test_mcq_adapter.py

Isolated unit tests for MCQAdapter (src/evidence_adapters/mcq_adapter.py).
Tests compatibility with MCQAnalyzer.evaluate() outputs and canonical UnifiedEvidenceRecord schema.
"""

import pytest
from src.analyzers.mcq_analyzer import MCQAnalyzer
from src.evidence_adapters.mcq_adapter import adapt_mcq_evaluation
from src.schemas.evidence import (
    ModalityType,
    EvaluationLifecycle,
    AdmissionStatus,
)


@pytest.fixture
def analyzer():
    return MCQAnalyzer()


def test_mcq_adapter_correct_selection(analyzer):
    """Verifies adaptation of correct MCQ response to ADMITTED_BINARY."""
    raw_eval = analyzer.evaluate(student_option="B", correct_option="B")
    record = adapt_mcq_evaluation(
        evaluator_output=raw_eval,
        evidence_id="ev_mcq_test_1",
        submission_id="sub_test_1",
        bundle_id="bundle_vars_1",
        student_id="S001",
        item_id="mcq_1",
        concept_id="python:variables",
        selected_option_id="B",
        correct_option_id="B",
        server_receipt_timestamp="2026-11-16T17:00:00Z",
    )

    assert record.evidence_id == "ev_mcq_test_1"
    assert record.submission_id == "sub_test_1"
    assert record.modality == ModalityType.MCQ
    assert record.evaluation_lifecycle == EvaluationLifecycle.EVALUATED_SUCCESS
    assert record.admission_status == AdmissionStatus.ADMITTED_BINARY
    assert record.raw_score == 1.0
    assert record.normalized_score == 1.0
    assert record.maximum_possible_score == 1.0
    assert record.correctness is True
    assert record.modality_details.mcq.selected_option_id == "B"
    assert record.modality_details.mcq.correct_option_id == "B"
    assert record.client_submission_timestamp is None
    assert record.item_attempt_number is None


def test_mcq_adapter_incorrect_selection(analyzer):
    """Verifies adaptation of incorrect MCQ response to 0.0 binary score."""
    raw_eval = analyzer.evaluate(student_option="A", correct_option="C")
    record = adapt_mcq_evaluation(
        evaluator_output=raw_eval,
        evidence_id="ev_mcq_test_2",
        submission_id="sub_test_1",
        bundle_id="bundle_vars_1",
        student_id="S001",
        item_id="mcq_2",
        concept_id="python:variables",
        selected_option_id="A",
        correct_option_id="C",
        server_receipt_timestamp="2026-11-16T17:00:00Z",
        item_attempt_number=2,
    )

    assert record.raw_score == 0.0
    assert record.normalized_score == 0.0
    assert record.correctness is False
    assert record.admission_status == AdmissionStatus.ADMITTED_BINARY
    assert record.item_attempt_number == 2


def test_mcq_adapter_distractor_partial_credit(analyzer):
    """Verifies that non-binary distractor scores are gated to ADMITTED_FORMATIVE_ONLY."""
    weights = {"A": 0.5, "B": 1.0, "C": 0.0}
    raw_eval = analyzer.evaluate(student_option="A", correct_option="B", distractor_weights=weights)
    record = adapt_mcq_evaluation(
        evaluator_output=raw_eval,
        evidence_id="ev_mcq_test_3",
        submission_id="sub_test_1",
        bundle_id="bundle_vars_1",
        student_id="S001",
        item_id="mcq_3",
        concept_id="python:variables",
        selected_option_id="A",
        correct_option_id="B",
        server_receipt_timestamp="2026-11-16T17:00:00Z",
    )

    assert record.raw_score == 0.5
    assert record.normalized_score == 0.5
    assert record.correctness is False
    assert record.admission_status == AdmissionStatus.ADMITTED_FORMATIVE_ONLY


def test_mcq_adapter_malformed_evaluator_output():
    """Rejects missing required fields from evaluator_output."""
    with pytest.raises(ValueError) as exc:
        adapt_mcq_evaluation(
            evaluator_output={"some_other_field": 123},
            evidence_id="ev_err",
            submission_id="sub_err",
            bundle_id="bun_err",
            student_id="s",
            item_id="i",
            concept_id="c",
            selected_option_id="A",
            correct_option_id="B",
            server_receipt_timestamp="2026-11-16T17:00:00Z",
        )
    assert "missing required fields" in str(exc.value)


def test_mcq_adapter_deterministic_conversion(analyzer):
    """Repeated calls with identical metadata produce identical records."""
    raw_eval = analyzer.evaluate(student_option="B", correct_option="B")
    rec1 = adapt_mcq_evaluation(
        evaluator_output=raw_eval,
        evidence_id="ev_det",
        submission_id="sub_det",
        bundle_id="bun_det",
        student_id="S001",
        item_id="item_det",
        concept_id="python:loops",
        selected_option_id="B",
        correct_option_id="B",
        server_receipt_timestamp="2026-11-16T17:00:00Z",
        evaluation_completion_timestamp="2026-11-16T17:00:01Z",
    )
    rec2 = adapt_mcq_evaluation(
        evaluator_output=raw_eval,
        evidence_id="ev_det",
        submission_id="sub_det",
        bundle_id="bun_det",
        student_id="S001",
        item_id="item_det",
        concept_id="python:loops",
        selected_option_id="B",
        correct_option_id="B",
        server_receipt_timestamp="2026-11-16T17:00:00Z",
        evaluation_completion_timestamp="2026-11-16T17:00:01Z",
    )

    assert rec1 == rec2

