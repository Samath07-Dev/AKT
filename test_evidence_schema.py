"""
test_evidence_schema.py

Isolated unit tests for the canonical Pydantic UnifiedEvidenceRecord schema.
Verifies all Phase 2A and Phase 2B invariants:
- Four canonical Phase 2A example records
- Pending coding evaluation
- Infrastructure failure representation
- Admission status restrictions
- Identifier preservation (bundle_id, submission_id, evidence_id)
- Null score safety (no conversion to 0.0)
- Missing telemetry handling
- Invalid lifecycle combinations
- Serialization and deserialization roundtrips
"""

import pytest
import json
from pydantic import ValidationError

from src.schemas.evidence import (
    UnifiedEvidenceRecord,
    ModalityType,
    EvaluationLifecycle,
    AdmissionStatus,
    MCQDetails,
    ShortAnswerDetails,
    CodingDetails,
    ModalityDetails,
    BehavioralTelemetry,
)


@pytest.fixture
def mcq_record_data():
    """Phase 2A Approved Example Record 1: MCQ (Exact Match Binary)"""
    return {
        "evidence_id": "ev_mcq_8f92a10b-1934-4b51-9dc7-28d10398ef01",
        "submission_id": "sub_stu_research_042_attempt_001",
        "bundle_id": "bundle_py_vars_01",
        "student_id": "stu_research_042",
        "item_id": "mcq_var_decl_001",
        "concept_id": "python:variable_declaration",
        "item_attempt_number": 1,
        "concept_cumulative_attempt_number": 3,
        "modality": "MCQ",
        "evaluator_version": "mcq_analyzer_v1.0",
        "evaluation_lifecycle": "EVALUATED_SUCCESS",
        "admission_status": "ADMITTED_BINARY",
        "client_submission_timestamp": "2026-11-16T10:15:30.120Z",
        "server_receipt_timestamp": "2026-11-16T10:15:30.250Z",
        "evaluation_start_timestamp": "2026-11-16T10:15:30.255Z",
        "evaluation_completion_timestamp": "2026-11-16T10:15:30.260Z",
        "raw_score": 1.0,
        "maximum_possible_score": 1.0,
        "normalized_score": 1.0,
        "correctness": True,
        "modality_details": {
            "mcq": {
                "selected_option_id": "opt_b",
                "correct_option_id": "opt_b"
            },
            "short_answer": None,
            "coding": None
        },
        "behavioral_telemetry": {
            "dwell_time_seconds": 18.4,
            "hint_count": 0,
            "highest_hint_level": 0,
            "answer_revision_count": 1
        }
    }


@pytest.fixture
def short_answer_record_data():
    """Phase 2A Approved Example Record 2: Short Answer (Continuous Semantic Evaluation)"""
    return {
        "evidence_id": "ev_sa_3c82e44d-5872-4d18-b8cf-82e140d7c002",
        "submission_id": "sub_stu_research_042_attempt_001",
        "bundle_id": "bundle_py_vars_01",
        "student_id": "stu_research_042",
        "item_id": "sa_var_scope_002",
        "concept_id": "python:variable_scope",
        "item_attempt_number": 1,
        "concept_cumulative_attempt_number": 4,
        "modality": "SHORT_ANSWER",
        "evaluator_version": "sbert_minilm_v1",
        "evaluation_lifecycle": "EVALUATED_SUCCESS",
        "admission_status": "ADMITTED_FORMATIVE_ONLY",
        "client_submission_timestamp": "2026-11-16T10:17:15.000Z",
        "server_receipt_timestamp": "2026-11-16T10:17:15.180Z",
        "evaluation_start_timestamp": "2026-11-16T10:17:15.195Z",
        "evaluation_completion_timestamp": "2026-11-16T10:17:15.420Z",
        "raw_score": 0.8142,
        "maximum_possible_score": 1.0,
        "normalized_score": 0.8142,
        "correctness": None,
        "modality_details": {
            "mcq": None,
            "short_answer": {
                "submitted_text": "Local variables are only visible inside the function where they are created.",
                "sbert_cosine_similarity": 0.8142,
                "embedding_model": "all-MiniLM-L6-v2"
            },
            "coding": None
        },
        "behavioral_telemetry": {
            "dwell_time_seconds": 42.1,
            "hint_count": 1,
            "highest_hint_level": 1,
            "answer_revision_count": 2
        }
    }


@pytest.fixture
def coding_completed_record_data():
    """Phase 2A Approved Example Record 3: Coding (Completed Execution with Failed Tests)"""
    return {
        "evidence_id": "ev_code_71ab93f0-449e-4b72-8812-7901da38c003",
        "submission_id": "sub_stu_research_042_attempt_002",
        "bundle_id": "bundle_py_vars_01",
        "student_id": "stu_research_042",
        "item_id": "code_var_swap_003",
        "concept_id": "python:variable_swap",
        "item_attempt_number": 2,
        "concept_cumulative_attempt_number": 6,
        "modality": "CODING",
        "evaluator_version": "docker_sandbox_v2",
        "evaluation_lifecycle": "EVALUATED_SUCCESS",
        "admission_status": "PENDING_RESEARCH_POLICY",
        "client_submission_timestamp": "2026-11-16T10:22:04.500Z",
        "server_receipt_timestamp": "2026-11-16T10:22:04.710Z",
        "evaluation_start_timestamp": "2026-11-16T10:22:04.850Z",
        "evaluation_completion_timestamp": "2026-11-16T10:22:06.120Z",
        "raw_score": 2.0,
        "maximum_possible_score": 3.0,
        "normalized_score": 0.6667,
        "correctness": False,
        "modality_details": {
            "mcq": None,
            "short_answer": None,
            "coding": {
                "submitted_code": "def swap(a, b):\n    return b, a",
                "tests_run": 3,
                "tests_passed": 2,
                "tests_failed": 1,
                "tests_not_run": 0,
                "total_test_cases": 3,
                "execution_duration_ms": 1270.0,
                "sandbox_exit_code": 0,
                "infrastructure_error_message": None
            }
        },
        "behavioral_telemetry": {
            "dwell_time_seconds": 115.0,
            "hint_count": 2,
            "highest_hint_level": 2,
            "answer_revision_count": 4
        }
    }


@pytest.fixture
def coding_infrastructure_failure_data():
    """Phase 2A Approved Example Record 4: Coding (Infrastructure Failure - Docker Daemon Down)"""
    return {
        "evidence_id": "ev_code_9a0b12c3-1122-3344-5566-778899aabbcc",
        "submission_id": "sub_stu_research_042_attempt_003",
        "bundle_id": "bundle_py_vars_01",
        "student_id": "stu_research_042",
        "item_id": "code_var_swap_003",
        "concept_id": "python:variable_swap",
        "item_attempt_number": 3,
        "concept_cumulative_attempt_number": 7,
        "modality": "CODING",
        "evaluator_version": "docker_sandbox_v2",
        "evaluation_lifecycle": "EVALUATION_FAILED_INFRASTRUCTURE",
        "admission_status": "REJECTED_INFRASTRUCTURE_FAILURE",
        "client_submission_timestamp": "2026-11-16T10:25:00.000Z",
        "server_receipt_timestamp": "2026-11-16T10:25:00.210Z",
        "evaluation_start_timestamp": "2026-11-16T10:25:00.225Z",
        "evaluation_completion_timestamp": None,
        "raw_score": None,
        "maximum_possible_score": None,
        "normalized_score": None,
        "correctness": None,
        "modality_details": {
            "mcq": None,
            "short_answer": None,
            "coding": {
                "submitted_code": "def swap(a, b):\n    temp = a\n    a = b\n    b = temp\n    return a, b",
                "tests_run": 0,
                "tests_passed": None,
                "tests_failed": None,
                "tests_not_run": 3,
                "total_test_cases": 3,
                "execution_duration_ms": None,
                "sandbox_exit_code": None,
                "infrastructure_error_message": "Docker daemon unavailable at /Users/abdulsamath/.docker/run/docker.sock"
            }
        },
        "behavioral_telemetry": {
            "dwell_time_seconds": 88.0,
            "hint_count": 0,
            "highest_hint_level": 0,
            "answer_revision_count": 0
        }
    }


# ============================================================================
# 1. Validation of the Four Canonical Example Records
# ============================================================================

def test_mcq_canonical_record_validates(mcq_record_data):
    """Verifies that Record 1 (MCQ Exact Match) parses and validates cleanly."""
    record = UnifiedEvidenceRecord.model_validate(mcq_record_data)
    assert record.modality == ModalityType.MCQ
    assert record.admission_status == AdmissionStatus.ADMITTED_BINARY
    assert record.raw_score == 1.0
    assert record.correctness is True
    assert record.modality_details.mcq.selected_option_id == "opt_b"


def test_short_answer_canonical_record_validates(short_answer_record_data):
    """Verifies that Record 2 (Short Answer Semantic) parses and validates cleanly."""
    record = UnifiedEvidenceRecord.model_validate(short_answer_record_data)
    assert record.modality == ModalityType.SHORT_ANSWER
    assert record.admission_status == AdmissionStatus.ADMITTED_FORMATIVE_ONLY
    assert record.raw_score == 0.8142
    assert record.correctness is None  # Must remain None for continuous semantic similarity
    assert record.modality_details.short_answer.sbert_cosine_similarity == 0.8142


def test_coding_completed_canonical_record_validates(coding_completed_record_data):
    """Verifies that Record 3 (Coding Completed with Failed Tests) parses and validates cleanly."""
    record = UnifiedEvidenceRecord.model_validate(coding_completed_record_data)
    assert record.modality == ModalityType.CODING
    assert record.admission_status == AdmissionStatus.PENDING_RESEARCH_POLICY
    assert record.raw_score == 2.0
    assert record.maximum_possible_score == 3.0
    assert record.correctness is False
    assert record.modality_details.coding.tests_run == 3
    assert record.modality_details.coding.tests_passed == 2
    assert record.modality_details.coding.tests_failed == 1


def test_coding_infrastructure_failure_validates(coding_infrastructure_failure_data):
    """Verifies that Record 4 (Docker Offline) parses and validates cleanly."""
    record = UnifiedEvidenceRecord.model_validate(coding_infrastructure_failure_data)
    assert record.modality == ModalityType.CODING
    assert record.evaluation_lifecycle == EvaluationLifecycle.EVALUATION_FAILED_INFRASTRUCTURE
    assert record.admission_status == AdmissionStatus.REJECTED_INFRASTRUCTURE_FAILURE
    assert record.raw_score is None
    assert record.normalized_score is None
    assert record.correctness is None
    assert record.evaluation_completion_timestamp is None
    assert record.modality_details.coding.tests_run == 0
    assert record.modality_details.coding.tests_passed is None
    assert record.modality_details.coding.tests_not_run == 3


# ============================================================================
# 2. Pending Coding Evaluation & Null Score Handling
# ============================================================================

def test_pending_coding_evaluation_validates(coding_completed_record_data):
    """Verifies that a PENDING coding evaluation cleanly validates with null scores."""
    pending_data = dict(coding_completed_record_data)
    pending_data["evaluation_lifecycle"] = "PENDING_EVALUATION"
    pending_data["admission_status"] = "PENDING_EVALUATION"
    pending_data["evaluation_completion_timestamp"] = None
    pending_data["raw_score"] = None
    pending_data["normalized_score"] = None
    pending_data["correctness"] = None
    pending_data["modality_details"]["coding"]["tests_run"] = None
    pending_data["modality_details"]["coding"]["tests_passed"] = None
    pending_data["modality_details"]["coding"]["tests_failed"] = None

    record = UnifiedEvidenceRecord.model_validate(pending_data)
    assert record.evaluation_lifecycle == EvaluationLifecycle.PENDING_EVALUATION
    assert record.admission_status == AdmissionStatus.PENDING_EVALUATION
    assert record.raw_score is None
    assert record.normalized_score is None
    assert record.correctness is None
    assert record.evaluation_completion_timestamp is None


def test_infrastructure_failure_rejects_numeric_scores(coding_infrastructure_failure_data):
    """Asserts that assigning numerical 0.0 to an infrastructure failure is strictly rejected."""
    bad_data = dict(coding_infrastructure_failure_data)
    bad_data["raw_score"] = 0.0  # Illegal: infrastructure failures must not be scored as zero!

    with pytest.raises(ValidationError) as exc_info:
        UnifiedEvidenceRecord.model_validate(bad_data)
    assert "Infrastructure failure must not record a numeric raw_score" in str(exc_info.value)


def test_pending_evaluation_rejects_numeric_scores(coding_completed_record_data):
    """Asserts that assigning a numeric score to a pending evaluation is strictly rejected."""
    bad_data = dict(coding_completed_record_data)
    bad_data["evaluation_lifecycle"] = "PENDING_EVALUATION"
    bad_data["admission_status"] = "PENDING_EVALUATION"
    bad_data["raw_score"] = 0.0

    with pytest.raises(ValidationError) as exc_info:
        UnifiedEvidenceRecord.model_validate(bad_data)
    assert "Pending evaluation must have null raw_score" in str(exc_info.value)


# ============================================================================
# 3. Cognitive Admission Safety Guardrails
# ============================================================================

def test_short_answer_cannot_be_admitted_binary(short_answer_record_data):
    """Short Answer SBERT similarity cannot bypass into ADMITTED_BINARY."""
    bad_data = dict(short_answer_record_data)
    bad_data["admission_status"] = "ADMITTED_BINARY"

    with pytest.raises(ValidationError) as exc_info:
        UnifiedEvidenceRecord.model_validate(bad_data)
    assert "Short Answer cannot be admitted as ADMITTED_BINARY" in str(exc_info.value)


def test_short_answer_cannot_have_binary_correctness(short_answer_record_data):
    """Short Answer correctness cannot be coerced to a boolean."""
    bad_data = dict(short_answer_record_data)
    bad_data["correctness"] = True

    with pytest.raises(ValidationError) as exc_info:
        UnifiedEvidenceRecord.model_validate(bad_data)
    assert "Short Answer correctness must remain null" in str(exc_info.value)


def test_coding_cannot_be_admitted_binary(coding_completed_record_data):
    """Coding submissions cannot be admitted as ADMITTED_BINARY into live MCQ EMA tracker."""
    bad_data = dict(coding_completed_record_data)
    bad_data["admission_status"] = "ADMITTED_BINARY"

    with pytest.raises(ValidationError) as exc_info:
        UnifiedEvidenceRecord.model_validate(bad_data)
    assert "Coding evaluation cannot be admitted as ADMITTED_BINARY" in str(exc_info.value)


def test_infrastructure_failure_requires_rejected_admission(coding_infrastructure_failure_data):
    """Infrastructure failure cannot have admission_status other than REJECTED_INFRASTRUCTURE_FAILURE."""
    bad_data = dict(coding_infrastructure_failure_data)
    bad_data["admission_status"] = "PENDING_RESEARCH_POLICY"

    with pytest.raises(ValidationError) as exc_info:
        UnifiedEvidenceRecord.model_validate(bad_data)
    assert "Infrastructure failure must have admission_status REJECTED_INFRASTRUCTURE_FAILURE" in str(exc_info.value)


# ============================================================================
# 4. Missing Behavioural Telemetry
# ============================================================================

def test_missing_telemetry_validates_cleanly(mcq_record_data):
    """Verifies that completely omitted or null telemetry parses without error."""
    data = dict(mcq_record_data)
    data["behavioral_telemetry"] = None

    record = UnifiedEvidenceRecord.model_validate(data)
    assert record.behavioral_telemetry is None

    # Test with empty telemetry object
    data["behavioral_telemetry"] = {}
    record2 = UnifiedEvidenceRecord.model_validate(data)
    assert record2.behavioral_telemetry.dwell_time_seconds is None
    assert record2.behavioral_telemetry.hint_count is None


# ============================================================================
# 5. Identifier Preservation & Validation
# ============================================================================

def test_identifier_preservation(mcq_record_data):
    """Asserts that bundle_id, submission_id, and evidence_id are strictly preserved."""
    record = UnifiedEvidenceRecord.model_validate(mcq_record_data)
    assert record.evidence_id == "ev_mcq_8f92a10b-1934-4b51-9dc7-28d10398ef01"
    assert record.submission_id == "sub_stu_research_042_attempt_001"
    assert record.bundle_id == "bundle_py_vars_01"
    assert record.student_id == "stu_research_042"
    assert record.item_id == "mcq_var_decl_001"
    assert record.concept_id == "python:variable_declaration"


def test_invalid_attempt_number_rejected(mcq_record_data):
    """Item attempt number must be >= 1."""
    bad_data = dict(mcq_record_data)
    bad_data["item_attempt_number"] = 0

    with pytest.raises(ValidationError):
        UnifiedEvidenceRecord.model_validate(bad_data)


# ============================================================================
# 6. Serialization and Deserialization Roundtrip
# ============================================================================

def test_json_roundtrip_mcq(mcq_record_data):
    """Verifies full serialization to JSON string and deserialization back to model."""
    record = UnifiedEvidenceRecord.model_validate(mcq_record_data)
    json_str = record.model_dump_json()

    # Re-parse from json string
    re_parsed = UnifiedEvidenceRecord.model_validate_json(json_str)
    assert re_parsed == record
    assert re_parsed.evidence_id == record.evidence_id
    assert re_parsed.modality == ModalityType.MCQ


def test_json_roundtrip_coding_failure(coding_infrastructure_failure_data):
    """Verifies serialization roundtrip preserves null fields in infrastructure failures."""
    record = UnifiedEvidenceRecord.model_validate(coding_infrastructure_failure_data)
    json_str = record.model_dump_json()
    re_parsed = UnifiedEvidenceRecord.model_validate_json(json_str)

    assert re_parsed.raw_score is None
    assert re_parsed.normalized_score is None
    assert re_parsed.modality_details.coding.tests_passed is None
    assert re_parsed.modality_details.coding.tests_not_run == 3
    assert re_parsed.admission_status == AdmissionStatus.REJECTED_INFRASTRUCTURE_FAILURE


# ============================================================================
# 7. Phase 3A Approved Schema Refinements Test Suite
# ============================================================================

@pytest.mark.parametrize("cosine_val", [-1.0, -0.5, 0.0, 1.0])
def test_short_answer_raw_score_range(short_answer_record_data, cosine_val):
    """Verifies that Short Answer accepts raw cosine similarity across full [-1.0, +1.0] range."""
    data = dict(short_answer_record_data)
    data["raw_score"] = cosine_val
    data["modality_details"]["short_answer"]["sbert_cosine_similarity"] = cosine_val

    record = UnifiedEvidenceRecord.model_validate(data)
    assert record.raw_score == cosine_val
    assert record.modality_details.short_answer.sbert_cosine_similarity == cosine_val
    assert record.correctness is None  # Uncalibrated SBERT similarity must not be boolean correctness


def test_mcq_negative_raw_score_rejected(mcq_record_data):
    """MCQ raw score cannot be negative."""
    data = dict(mcq_record_data)
    data["raw_score"] = -0.1

    with pytest.raises(ValidationError) as exc_info:
        UnifiedEvidenceRecord.model_validate(data)
    assert "MCQ raw_score must be non-negative" in str(exc_info.value)


def test_coding_negative_raw_score_rejected(coding_completed_record_data):
    """Coding raw score cannot be negative."""
    data = dict(coding_completed_record_data)
    data["raw_score"] = -1.0

    with pytest.raises(ValidationError) as exc_info:
        UnifiedEvidenceRecord.model_validate(data)
    assert "CODING raw_score must be non-negative" in str(exc_info.value)


@pytest.mark.parametrize("invalid_norm", [-0.01, 1.01, -1.0, 2.0])
def test_normalized_score_outside_unit_interval_rejected(mcq_record_data, invalid_norm):
    """Normalized score must be strictly within [0.0, 1.0]."""
    data = dict(mcq_record_data)
    data["normalized_score"] = invalid_norm

    with pytest.raises(ValidationError):
        UnifiedEvidenceRecord.model_validate(data)


def test_missing_client_timestamp_accepted(mcq_record_data):
    """client_submission_timestamp is nullable and can be None when client is uninstrumented."""
    data = dict(mcq_record_data)
    data["client_submission_timestamp"] = None

    record = UnifiedEvidenceRecord.model_validate(data)
    assert record.client_submission_timestamp is None


def test_valid_client_timestamp_accepted(mcq_record_data):
    """Valid ISO 8601 string client_submission_timestamp is preserved."""
    data = dict(mcq_record_data)
    data["client_submission_timestamp"] = "2026-11-16T17:05:00.000Z"

    record = UnifiedEvidenceRecord.model_validate(data)
    assert record.client_submission_timestamp == "2026-11-16T17:05:00.000Z"


def test_missing_server_receipt_timestamp_rejected(mcq_record_data):
    """server_receipt_timestamp remains strictly mandatory."""
    data = dict(mcq_record_data)
    del data["server_receipt_timestamp"]

    with pytest.raises(ValidationError) as exc_info:
        UnifiedEvidenceRecord.model_validate(data)
    assert "server_receipt_timestamp" in str(exc_info.value)


def test_missing_item_attempt_number_accepted(mcq_record_data):
    """item_attempt_number is optional and can be None when uninstrumented."""
    data = dict(mcq_record_data)
    data["item_attempt_number"] = None

    record = UnifiedEvidenceRecord.model_validate(data)
    assert record.item_attempt_number is None


def test_item_attempt_number_one_accepted(mcq_record_data):
    """item_attempt_number >= 1 is valid."""
    data = dict(mcq_record_data)
    data["item_attempt_number"] = 1

    record = UnifiedEvidenceRecord.model_validate(data)
    assert record.item_attempt_number == 1


def test_item_attempt_number_zero_rejected(mcq_record_data):
    """item_attempt_number cannot be 0 (must be >= 1 when provided)."""
    data = dict(mcq_record_data)
    data["item_attempt_number"] = 0

    with pytest.raises(ValidationError):
        UnifiedEvidenceRecord.model_validate(data)


def test_concept_cumulative_attempt_count_independent(mcq_record_data):
    """concept_cumulative_attempt_number is independent of item_attempt_number."""
    data = dict(mcq_record_data)
    data["item_attempt_number"] = None
    data["concept_cumulative_attempt_number"] = 5

    record = UnifiedEvidenceRecord.model_validate(data)
    assert record.item_attempt_number is None
    assert record.concept_cumulative_attempt_number == 5

    data2 = dict(mcq_record_data)
    data2["item_attempt_number"] = 2
    data2["concept_cumulative_attempt_number"] = None

    record2 = UnifiedEvidenceRecord.model_validate(data2)
    assert record2.item_attempt_number == 2
    assert record2.concept_cumulative_attempt_number is None


