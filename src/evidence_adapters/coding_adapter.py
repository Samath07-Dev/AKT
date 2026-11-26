"""
src/evidence_adapters/coding_adapter.py

Harmonization adapter for Coding evaluation outputs.
Converts SandboxEvaluationResult or CodeAnalyzer dictionary outputs into canonical UnifiedEvidenceRecord instances.
"""

from __future__ import annotations
from typing import Dict, Any, Optional, Union
from datetime import datetime, timezone

from src.schemas.evidence import (
    UnifiedEvidenceRecord,
    ModalityType,
    EvaluationLifecycle,
    AdmissionStatus,
    CodingDetails,
    ModalityDetails,
    BehavioralTelemetry,
)


def adapt_coding_evaluation(
    evaluator_output: Union[Dict[str, Any], Any],
    submitted_code: str,
    evidence_id: str,
    submission_id: str,
    bundle_id: str,
    student_id: str,
    item_id: str,
    concept_id: str,
    server_receipt_timestamp: str,
    total_test_cases: Optional[int] = None,
    client_submission_timestamp: Optional[str] = None,
    evaluation_start_timestamp: Optional[str] = None,
    evaluation_completion_timestamp: Optional[str] = None,
    item_attempt_number: Optional[int] = None,
    concept_cumulative_attempt_number: Optional[int] = None,
    evaluator_version: Optional[str] = "sandbox_runner_v2.0",
    execution_duration_ms: Optional[float] = None,
    sandbox_exit_code: Optional[int] = None,
    telemetry: Optional[BehavioralTelemetry] = None,
    force_infrastructure_failure: bool = False,
    force_pending: bool = False,
) -> UnifiedEvidenceRecord:
    """
    Transforms raw coding evaluation results into a canonical UnifiedEvidenceRecord.

    Requirements:
    - Distinguishes:
        * Infrastructure failure (Docker unavailable, socket down, daemon offline)
        * Pending evaluation (queued / deferred execution)
        * Student-code syntax error
        * Student-code timeout
        * Successfully completed evaluation (full or partial credit)
    - Unexecuted tests are never converted into failed tests.
    - Infrastructure failures and pending evaluations keep raw/normalized scores and correctness as None.
    - Completed coding evidence is set to PENDING_RESEARCH_POLICY (never ADMITTED_BINARY).
    - Preserves fail-closed security posture.
    """
    # Normalize evaluator_output to dictionary if it has to_dict() or asdict attributes
    if hasattr(evaluator_output, "to_dict"):
        output = evaluator_output.to_dict()
    elif hasattr(evaluator_output, "__dataclass_fields__"):
        from dataclasses import asdict
        output = asdict(evaluator_output)
    elif isinstance(evaluator_output, dict):
        output = dict(evaluator_output)
    else:
        raise ValueError(f"Coding evaluator_output must be a dictionary or dataclass, got {type(evaluator_output)}")

    code_status = str(output.get("code_status") or "").upper().strip()
    exec_status = str(output.get("code_execution_status") or "").upper().strip()
    feedback = str(output.get("feedback") or "")
    runtime_error = output.get("runtime_error")
    syntax_valid = output.get("syntax_valid")
    syntax_error = output.get("syntax_error")

    # Determine total configured test cases
    total_tests = total_test_cases
    if total_tests is None:
        total_tests = output.get("code_tests_total") or len(output.get("test_results") or []) or None

    passed_tests = output.get("code_tests_passed")

    # Detect Infrastructure Failure
    infra_keywords = [
        "daemon unavailable", "image or docker daemon unavailable",
        "sandbox daemon", "docker cli binary not found", "socket",
        "failed to verify docker sandbox daemon", "sandbox unavailable"
    ]
    is_infra_failure = force_infrastructure_failure or any(
        kw in feedback.lower() or (runtime_error and kw in str(runtime_error).lower())
        for kw in infra_keywords
    )

    if is_infra_failure:
        lifecycle = EvaluationLifecycle.EVALUATION_FAILED_INFRASTRUCTURE
        admission = AdmissionStatus.REJECTED_INFRASTRUCTURE_FAILURE
        raw_score = None
        norm_score = None
        max_score = None
        correctness = None
        comp_ts = None
        coding_details = CodingDetails(
            submitted_code=str(submitted_code or ""),
            tests_run=0,
            tests_passed=None,
            tests_failed=None,
            tests_not_run=total_tests,
            total_test_cases=total_tests,
            execution_duration_ms=None,
            sandbox_exit_code=None,
            infrastructure_error_message=feedback or str(runtime_error or "Docker infrastructure failure"),
        )

    elif force_pending or (code_status == "PENDING_SECURE_EVALUATION" and exec_status == "NOT_PERFORMED"):
        lifecycle = EvaluationLifecycle.PENDING_EVALUATION
        admission = AdmissionStatus.PENDING_EVALUATION
        raw_score = None
        norm_score = None
        max_score = None
        correctness = None
        comp_ts = None
        coding_details = CodingDetails(
            submitted_code=str(submitted_code or ""),
            tests_run=None,
            tests_passed=None,
            tests_failed=None,
            tests_not_run=total_tests,
            total_test_cases=total_tests,
            execution_duration_ms=None,
            sandbox_exit_code=None,
            infrastructure_error_message=None,
        )

    elif syntax_valid is False and syntax_error:
        lifecycle = EvaluationLifecycle.EVALUATION_ERROR_STUDENT_CODE
        admission = AdmissionStatus.PENDING_RESEARCH_POLICY
        raw_score = 0.0
        norm_score = 0.0
        max_score = float(total_tests) if total_tests is not None else None
        correctness = False
        comp_ts = evaluation_completion_timestamp or datetime.now(timezone.utc).isoformat()
        coding_details = CodingDetails(
            submitted_code=str(submitted_code or ""),
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            tests_not_run=total_tests,
            total_test_cases=total_tests,
            execution_duration_ms=execution_duration_ms,
            sandbox_exit_code=sandbox_exit_code,
            infrastructure_error_message=None,
        )

    elif runtime_error and ("timed out" in str(runtime_error).lower() or "timeout" in str(runtime_error).lower()):
        lifecycle = EvaluationLifecycle.EVALUATION_TIMEOUT_STUDENT_CODE
        admission = AdmissionStatus.PENDING_RESEARCH_POLICY
        raw_score = 0.0
        norm_score = 0.0
        max_score = float(total_tests) if total_tests is not None else None
        correctness = False
        comp_ts = evaluation_completion_timestamp or datetime.now(timezone.utc).isoformat()
        run_count = int(passed_tests or 0)
        coding_details = CodingDetails(
            submitted_code=str(submitted_code or ""),
            tests_run=run_count,
            tests_passed=run_count,
            tests_failed=0,
            tests_not_run=(total_tests - run_count) if total_tests is not None else None,
            total_test_cases=total_tests,
            execution_duration_ms=execution_duration_ms,
            sandbox_exit_code=sandbox_exit_code,
            infrastructure_error_message=None,
        )

    elif runtime_error and exec_status == "EXECUTED":
        lifecycle = EvaluationLifecycle.EVALUATION_ERROR_STUDENT_CODE
        admission = AdmissionStatus.PENDING_RESEARCH_POLICY
        raw_score = float(passed_tests or 0)
        max_score = float(total_tests) if total_tests is not None else None
        norm_score = float(raw_score / total_tests) if (total_tests and total_tests > 0) else 0.0
        correctness = False
        comp_ts = evaluation_completion_timestamp or datetime.now(timezone.utc).isoformat()
        run_count = total_tests or 0
        coding_details = CodingDetails(
            submitted_code=str(submitted_code or ""),
            tests_run=run_count,
            tests_passed=int(raw_score),
            tests_failed=int(run_count - raw_score),
            tests_not_run=0,
            total_test_cases=total_tests,
            execution_duration_ms=execution_duration_ms,
            sandbox_exit_code=sandbox_exit_code,
            infrastructure_error_message=None,
        )

    else:
        # Completed Execution
        lifecycle = EvaluationLifecycle.EVALUATED_SUCCESS
        admission = AdmissionStatus.PENDING_RESEARCH_POLICY
        passed_val = int(passed_tests if passed_tests is not None else 0)
        total_val = int(total_tests if total_tests is not None else passed_val)

        raw_score = float(passed_val)
        max_score = float(total_val)
        norm_score = float(passed_val / total_val) if total_val > 0 else 0.0
        correctness = bool(passed_val == total_val and total_val > 0)
        comp_ts = evaluation_completion_timestamp or datetime.now(timezone.utc).isoformat()

        coding_details = CodingDetails(
            submitted_code=str(submitted_code or ""),
            tests_run=total_val,
            tests_passed=passed_val,
            tests_failed=int(total_val - passed_val),
            tests_not_run=0,
            total_test_cases=total_val,
            execution_duration_ms=execution_duration_ms,
            sandbox_exit_code=sandbox_exit_code or 0,
            infrastructure_error_message=None,
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
        modality=ModalityType.CODING,
        evaluator_version=evaluator_version,
        client_submission_timestamp=client_submission_timestamp,
        server_receipt_timestamp=server_receipt_timestamp,
        evaluation_start_timestamp=evaluation_start_timestamp,
        evaluation_completion_timestamp=comp_ts,
        evaluation_lifecycle=lifecycle,
        admission_status=admission,
        raw_score=raw_score,
        maximum_possible_score=max_score,
        normalized_score=norm_score,
        correctness=correctness,
        modality_details=ModalityDetails(coding=coding_details),
        behavioral_telemetry=telemetry,
    )

