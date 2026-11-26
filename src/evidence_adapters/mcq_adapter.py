"""
src/evidence_adapters/mcq_adapter.py

Harmonization adapter for Multiple Choice Question (MCQ) evaluation outputs.
Converts raw dictionaries returned by MCQAnalyzer into canonical UnifiedEvidenceRecord instances.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from src.schemas.evidence import (
    UnifiedEvidenceRecord,
    ModalityType,
    EvaluationLifecycle,
    AdmissionStatus,
    MCQDetails,
    ModalityDetails,
    BehavioralTelemetry,
)


def adapt_mcq_evaluation(
    evaluator_output: Dict[str, Any],
    evidence_id: str,
    submission_id: str,
    bundle_id: str,
    student_id: str,
    item_id: str,
    concept_id: str,
    selected_option_id: str,
    correct_option_id: str,
    server_receipt_timestamp: str,
    client_submission_timestamp: Optional[str] = None,
    evaluation_start_timestamp: Optional[str] = None,
    evaluation_completion_timestamp: Optional[str] = None,
    item_attempt_number: Optional[int] = None,
    concept_cumulative_attempt_number: Optional[int] = None,
    evaluator_version: Optional[str] = "mcq_analyzer_v1.0",
    telemetry: Optional[BehavioralTelemetry] = None,
) -> UnifiedEvidenceRecord:
    """
    Transforms raw MCQAnalyzer.evaluate output into a canonical UnifiedEvidenceRecord.

    Requirements:
    - Preserves exact score and boolean correctness.
    - Preserves selected_option_id and correct_option_id.
    - ADMITTED_BINARY used strictly for binary (0.0 or 1.0) scores.
    - Partial credit distractor scores mapped to ADMITTED_FORMATIVE_ONLY.
    - Rejects malformed or missing evaluation results.
    """
    if not isinstance(evaluator_output, dict):
        raise ValueError(f"MCQ evaluator_output must be a dictionary, got {type(evaluator_output)}")

    if "evidence_score" not in evaluator_output or "is_correct" not in evaluator_output:
        raise ValueError("MCQ evaluator_output missing required fields 'evidence_score' or 'is_correct'")

    if not selected_option_id or not correct_option_id:
        raise ValueError("MCQ selected_option_id and correct_option_id must not be empty")

    raw_score_val = float(evaluator_output["evidence_score"])
    if raw_score_val < 0.0 or raw_score_val > 1.0:
        raise ValueError(f"MCQ evidence_score must be between 0.0 and 1.0, got {raw_score_val}")

    is_correct_val = bool(evaluator_output["is_correct"])

    # Admission Policy: Only binary scores (0.0 or 1.0) admitted to live EMA pathway
    if raw_score_val in (0.0, 1.0):
        admission = AdmissionStatus.ADMITTED_BINARY
    else:
        admission = AdmissionStatus.ADMITTED_FORMATIVE_ONLY

    comp_ts = evaluation_completion_timestamp or datetime.now(timezone.utc).isoformat()

    modality_details = ModalityDetails(
        mcq=MCQDetails(
            selected_option_id=str(selected_option_id).strip(),
            correct_option_id=str(correct_option_id).strip(),
        )
    )

    return UnifiedEvidenceRecord(
        evidence_id=evidence_id,
        submission_id=submission_id,
        bundle_id=bundle_id,
        student_id=student_id,
        item_id=item_id,
        concept_id=concept_id,
        item_attempt_number=item_attempt_number,
        concept_cumulative_attempt_number=concept_cumulative_attempt_number,
        modality=ModalityType.MCQ,
        evaluator_version=evaluator_version,
        client_submission_timestamp=client_submission_timestamp,
        server_receipt_timestamp=server_receipt_timestamp,
        evaluation_start_timestamp=evaluation_start_timestamp,
        evaluation_completion_timestamp=comp_ts,
        evaluation_lifecycle=EvaluationLifecycle.EVALUATED_SUCCESS,
        admission_status=admission,
        raw_score=raw_score_val,
        maximum_possible_score=1.0,
        normalized_score=raw_score_val,
        correctness=is_correct_val,
        modality_details=modality_details,
        behavioral_telemetry=telemetry,
    )

