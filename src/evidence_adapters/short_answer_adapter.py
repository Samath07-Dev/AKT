"""
src/evidence_adapters/short_answer_adapter.py

Harmonization adapter for Short Answer semantic evaluation outputs.
Converts raw dictionaries returned by ShortAnswerAnalyzer into canonical UnifiedEvidenceRecord instances.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from src.schemas.evidence import (
    UnifiedEvidenceRecord,
    ModalityType,
    EvaluationLifecycle,
    AdmissionStatus,
    ShortAnswerDetails,
    ModalityDetails,
    BehavioralTelemetry,
)


def adapt_short_answer_evaluation(
    evaluator_output: Dict[str, Any],
    submitted_text: str,
    evidence_id: str,
    submission_id: str,
    bundle_id: str,
    student_id: str,
    item_id: str,
    concept_id: str,
    server_receipt_timestamp: str,
    client_submission_timestamp: Optional[str] = None,
    evaluation_start_timestamp: Optional[str] = None,
    evaluation_completion_timestamp: Optional[str] = None,
    item_attempt_number: Optional[int] = None,
    concept_cumulative_attempt_number: Optional[int] = None,
    evaluator_version: Optional[str] = "short_answer_analyzer_v1.0",
    telemetry: Optional[BehavioralTelemetry] = None,
) -> UnifiedEvidenceRecord:
    """
    Transforms raw ShortAnswerAnalyzer.evaluate output into a canonical UnifiedEvidenceRecord.

    Requirements:
    - Preserves exact raw SBERT cosine similarity across [-1.0, +1.0].
    - Normalizes score strictly to [0.0, 1.0] without fabricating binary correctness.
    - correctness is strictly None (uncalibrated continuous similarity is not binary).
    - admission_status is strictly ADMITTED_FORMATIVE_ONLY.
    - Preserves embedding model identifier.
    - Rejects malformed evaluator outputs.
    """
    if not isinstance(evaluator_output, dict):
        raise ValueError(f"Short answer evaluator_output must be a dictionary, got {type(evaluator_output)}")

    # Extract cosine similarity: either 'cosine_similarity' or 'evidence_score'
    if "cosine_similarity" in evaluator_output:
        raw_sim = float(evaluator_output["cosine_similarity"])
    elif "evidence_score" in evaluator_output:
        raw_sim = float(evaluator_output["evidence_score"])
    else:
        raise ValueError("Short answer evaluator_output missing 'cosine_similarity' or 'evidence_score'")

    if not (-1.0 <= raw_sim <= 1.0):
        raise ValueError(f"SBERT cosine similarity must be within [-1.0, 1.0], got {raw_sim}")

    embedding_model = str(evaluator_output.get("model_used") or "sentence-transformers/all-MiniLM-L6-v2")

    # Normalized score bounded to [0.0, 1.0]
    norm_score = max(0.0, min(1.0, raw_sim))

    comp_ts = evaluation_completion_timestamp or datetime.now(timezone.utc).isoformat()

    modality_details = ModalityDetails(
        short_answer=ShortAnswerDetails(
            submitted_text=str(submitted_text or ""),
            sbert_cosine_similarity=raw_sim,
            embedding_model=embedding_model,
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
        modality=ModalityType.SHORT_ANSWER,
        evaluator_version=evaluator_version,
        client_submission_timestamp=client_submission_timestamp,
        server_receipt_timestamp=server_receipt_timestamp,
        evaluation_start_timestamp=evaluation_start_timestamp,
        evaluation_completion_timestamp=comp_ts,
        evaluation_lifecycle=EvaluationLifecycle.EVALUATED_SUCCESS,
        admission_status=AdmissionStatus.ADMITTED_FORMATIVE_ONLY,
        raw_score=raw_sim,
        maximum_possible_score=1.0,
        normalized_score=norm_score,
        correctness=None,  # Continuous semantic evaluation has no binary correctness
        modality_details=modality_details,
        behavioral_telemetry=telemetry,
    )

