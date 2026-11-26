"""
test_short_answer_adapter.py

Isolated unit tests for ShortAnswerAdapter (src/evidence_adapters/short_answer_adapter.py).
Tests compatibility with ShortAnswerAnalyzer.evaluate() outputs and canonical UnifiedEvidenceRecord schema.
"""

import pytest
from src.analyzers.short_answer_analyzer import ShortAnswerAnalyzer
from src.evidence_adapters.short_answer_adapter import adapt_short_answer_evaluation
from src.schemas.evidence import (
    ModalityType,
    EvaluationLifecycle,
    AdmissionStatus,
)


@pytest.fixture
def analyzer():
    return ShortAnswerAnalyzer()


def test_short_answer_adapter_positive_similarity(analyzer):
    """Verifies adaptation of standard short answer evaluation."""
    raw_eval = analyzer.evaluate(
        student_response="Variables store data in computer memory.",
        reference_answer="A variable is a named storage location in memory."
    )
    record = adapt_short_answer_evaluation(
        evaluator_output=raw_eval,
        submitted_text="Variables store data in computer memory.",
        evidence_id="ev_sa_test_1",
        submission_id="sub_test_1",
        bundle_id="bundle_vars_1",
        student_id="S001",
        item_id="sa_1",
        concept_id="python:variables",
        server_receipt_timestamp="2026-11-16T17:00:00Z",
    )

    assert record.evidence_id == "ev_sa_test_1"
    assert record.modality == ModalityType.SHORT_ANSWER
    assert record.evaluation_lifecycle == EvaluationLifecycle.EVALUATED_SUCCESS
    assert record.admission_status == AdmissionStatus.ADMITTED_FORMATIVE_ONLY
    assert record.correctness is None
    assert 0.0 <= record.normalized_score <= 1.0
    assert record.raw_score == raw_eval["cosine_similarity"]
    assert record.modality_details.short_answer.submitted_text == "Variables store data in computer memory."
    assert record.modality_details.short_answer.embedding_model != ""


@pytest.mark.parametrize("cosine_val", [-1.0, -0.75, -0.2, 0.0, 0.5, 1.0])
def test_short_answer_adapter_preserves_full_cosine_range(cosine_val):
    """Verifies that negative and edge-case cosine similarities are preserved exactly."""
    mock_eval = {
        "cosine_similarity": cosine_val,
        "evidence_score": max(0.0, min(1.0, cosine_val)),
        "similarity_percentage": max(0.0, cosine_val * 100.0),
        "model_used": "sentence-transformers/all-MiniLM-L6-v2",
        "missing_keywords": ["memory"],
    }
    record = adapt_short_answer_evaluation(
        evaluator_output=mock_eval,
        submitted_text="Contradictory statement.",
        evidence_id="ev_sa_test_range",
        submission_id="sub_test_1",
        bundle_id="bundle_vars_1",
        student_id="S001",
        item_id="sa_range",
        concept_id="python:variables",
        server_receipt_timestamp="2026-11-16T17:00:00Z",
    )

    assert record.raw_score == cosine_val
    assert record.modality_details.short_answer.sbert_cosine_similarity == cosine_val
    assert record.correctness is None
    assert 0.0 <= record.normalized_score <= 1.0
    if cosine_val < 0.0:
        assert record.normalized_score == 0.0
    else:
        assert record.normalized_score == cosine_val


def test_short_answer_adapter_malformed_output():
    """Rejects evaluator output missing similarity metrics."""
    with pytest.raises(ValueError) as exc:
        adapt_short_answer_evaluation(
            evaluator_output={"feedback": "none"},
            submitted_text="Some text",
            evidence_id="ev_err",
            submission_id="sub_err",
            bundle_id="bun_err",
            student_id="s",
            item_id="i",
            concept_id="c",
            server_receipt_timestamp="2026-11-16T17:00:00Z",
        )
    assert "missing 'cosine_similarity' or 'evidence_score'" in str(exc.value)


def test_short_answer_adapter_out_of_bounds_similarity():
    """Rejects cosine similarity outside [-1.0, 1.0]."""
    with pytest.raises(ValueError) as exc:
        adapt_short_answer_evaluation(
            evaluator_output={"cosine_similarity": 1.5},
            submitted_text="Some text",
            evidence_id="ev_err",
            submission_id="sub_err",
            bundle_id="bun_err",
            student_id="s",
            item_id="i",
            concept_id="c",
            server_receipt_timestamp="2026-11-16T17:00:00Z",
        )
    assert "must be within [-1.0, 1.0]" in str(exc.value)


def test_short_answer_adapter_deterministic():
    """Verifies deterministic output across multiple invocations."""
    eval_out = {"cosine_similarity": 0.85, "model_used": "test_model"}
    r1 = adapt_short_answer_evaluation(
        evaluator_output=eval_out,
        submitted_text="Test",
        evidence_id="ev_det",
        submission_id="sub_det",
        bundle_id="bun_det",
        student_id="S001",
        item_id="i_det",
        concept_id="c_det",
        server_receipt_timestamp="2026-11-16T17:00:00Z",
        evaluation_completion_timestamp="2026-11-16T17:00:02Z",
    )
    r2 = adapt_short_answer_evaluation(
        evaluator_output=eval_out,
        submitted_text="Test",
        evidence_id="ev_det",
        submission_id="sub_det",
        bundle_id="bun_det",
        student_id="S001",
        item_id="i_det",
        concept_id="c_det",
        server_receipt_timestamp="2026-11-16T17:00:00Z",
        evaluation_completion_timestamp="2026-11-16T17:00:02Z",
    )
    assert r1 == r2

