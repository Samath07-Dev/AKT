"""
src/evidence_adapters/bundle_builder.py

Builds canonical embedded multimodal evidence records for complete assessment bundles.
Combines 3 MCQs, 1 Short Answer, and 1 Coding challenge into UnifiedEvidenceRecord dictionaries.

Enforces Phase 5 Mandatory Safety Constraints:
- Option A: Embedded directly into the MongoDB `scores` document.
- Privacy & Data Retention: Raw student code and freeform text answers are strictly excluded
  from permanent persistence, replaced with standardized privacy exclusion tokens.
- Cognitive Isolation: MCQ items are marked ADMITTED_BINARY, Short Answer is ADMITTED_FORMATIVE_ONLY,
  and Coding items are PENDING_RESEARCH_POLICY or PENDING_EVALUATION.
"""

from __future__ import annotations
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

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
from src.evidence_adapters.mcq_adapter import adapt_mcq_evaluation
from src.evidence_adapters.short_answer_adapter import adapt_short_answer_evaluation
from src.evidence_adapters.coding_adapter import adapt_coding_evaluation

PRIVACY_EXCLUSION_TOKEN = "[EXCLUDED_PRIVACY_POLICY]"


def build_embedded_bundle_evidence(
    student_id: str,
    submission_id: str,
    concept: str,
    difficulty: str,
    mcq_scores: List[float],
    short_answer_score: float,
    code_score: float,
    code_status: Optional[str] = None,
    code_execution_status: Optional[str] = None,
    code_tests_passed: Optional[int] = None,
    code_tests_total: Optional[int] = None,
    server_receipt_timestamp: Optional[str] = None,
    client_submission_timestamp: Optional[str] = None,
    item_attempt_number: Optional[int] = None,
    concept_cumulative_attempt_number: Optional[int] = None,
    mcq_details_list: Optional[List[Dict[str, Any]]] = None,
    sa_evaluator_output: Optional[Dict[str, Any]] = None,
    coding_evaluator_output: Optional[Dict[str, Any]] = None,
    runtime_error: Optional[str] = None,
    feedback: Optional[str] = None,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """
    Constructs the canonical 5-item embedded evidence array for an assessment bundle.

    Returns:
    - List of 5 dictionaries serialized from validated UnifiedEvidenceRecord models:
        * Index 0: MCQ 1
        * Index 1: MCQ 2
        * Index 2: MCQ 3
        * Index 3: Short Answer (SBERT)
        * Index 4: Coding Challenge (Docker Sandbox / AST)
    """
    now_iso = server_receipt_timestamp or datetime.now(timezone.utc).isoformat()
    bundle_id = f"bundle_{concept.lower().replace(' ', '_')}_{difficulty.lower().strip()}"
    concept_id = f"python:{concept.lower().replace(' ', '_')}"
    records: List[Dict[str, Any]] = []

    # 1. Adapt 3 MCQ items
    for i in range(3):
        score_val = float(mcq_scores[i]) if i < len(mcq_scores) else 0.0
        details = mcq_details_list[i] if (mcq_details_list and i < len(mcq_details_list)) else {}
        selected_opt = str(details.get("selected_option") or details.get("selected_option_id") or "UNKNOWN")
        correct_opt = str(details.get("correct_option") or details.get("correct_option_id") or "UNKNOWN")

        eval_out = {
            "evidence_score": score_val,
            "is_correct": bool(score_val == 1.0),
            "feedback": details.get("feedback", "Automated MCQ grading"),
        }

        mcq_rec = adapt_mcq_evaluation(
            evaluator_output=eval_out,
            evidence_id=f"ev_{submission_id}_mcq_{i + 1}",
            submission_id=submission_id,
            bundle_id=bundle_id,
            student_id=student_id,
            item_id=f"{concept}_MCQ_{difficulty.title()}_{i + 1}",
            concept_id=concept_id,
            selected_option_id=selected_opt,
            correct_option_id=correct_opt,
            server_receipt_timestamp=now_iso,
            client_submission_timestamp=client_submission_timestamp,
            evaluation_completion_timestamp=now_iso,
            item_attempt_number=item_attempt_number,
            concept_cumulative_attempt_number=concept_cumulative_attempt_number,
        )
        records.append(mcq_rec.model_dump())

    # 2. Adapt 1 Short Answer item (Privacy: raw text excluded)
    sa_out = dict(sa_evaluator_output or {})
    if "cosine_similarity" not in sa_out and "evidence_score" not in sa_out:
        sa_val = float(short_answer_score)
        if sa_val > 1.0:
            sa_val = sa_val / 100.0
        sa_out["cosine_similarity"] = sa_val
        sa_out["evidence_score"] = sa_val

    sa_rec = adapt_short_answer_evaluation(
        evaluator_output=sa_out,
        submitted_text=PRIVACY_EXCLUSION_TOKEN,  # Permanent ledger excludes raw student essay text
        evidence_id=f"ev_{submission_id}_sa_1",
        submission_id=submission_id,
        bundle_id=bundle_id,
        student_id=student_id,
        item_id=f"{concept}_SA_{difficulty.title()}_1",
        concept_id=concept_id,
        server_receipt_timestamp=now_iso,
        client_submission_timestamp=client_submission_timestamp,
        evaluation_completion_timestamp=now_iso,
        item_attempt_number=item_attempt_number,
        concept_cumulative_attempt_number=concept_cumulative_attempt_number,
    )
    records.append(sa_rec.model_dump())

    # 3. Adapt 1 Coding Challenge item (Privacy: raw code excluded)
    if coding_evaluator_output:
        code_out = dict(coding_evaluator_output)
    else:
        code_out = {
            "code_status": code_status or "PENDING_SECURE_EVALUATION",
            "code_execution_status": code_execution_status or "NOT_PERFORMED",
            "code_score": float(code_score),
            "code_tests_passed": code_tests_passed,
            "code_tests_total": code_tests_total or 2,
            "syntax_valid": True,
            "runtime_error": runtime_error,
            "feedback": feedback or "Coding challenge evaluation",
        }

    is_infra_fail = (
        code_out.get("code_status") == "EVALUATION_FAILED_INFRASTRUCTURE"
        or code_out.get("code_execution_status") == "INFRASTRUCTURE_UNAVAILABLE"
        or kwargs.get("force_infrastructure_failure", False)
    )

    code_rec = adapt_coding_evaluation(
        evaluator_output=code_out,
        submitted_code=PRIVACY_EXCLUSION_TOKEN,  # Permanent ledger excludes raw student source code
        evidence_id=f"ev_{submission_id}_code_1",
        submission_id=submission_id,
        bundle_id=bundle_id,
        student_id=student_id,
        item_id=f"{concept}_Code_{difficulty.title()}_1",
        concept_id=concept_id,
        server_receipt_timestamp=now_iso,
        client_submission_timestamp=client_submission_timestamp,
        evaluation_completion_timestamp=now_iso if code_status == "EVALUATED" else None,
        item_attempt_number=item_attempt_number,
        concept_cumulative_attempt_number=concept_cumulative_attempt_number,
        total_test_cases=code_out.get("code_tests_total") or code_tests_total,
        force_infrastructure_failure=is_infra_fail,
    )
    records.append(code_rec.model_dump())

    return records
