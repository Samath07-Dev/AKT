"""
src/schemas/evidence.py

Canonical Pydantic schema for the Unified Multimodal Evidence Record.
Represents discrete student interactions across MCQ, Short Answer, and Coding
modalities for Adaptive Knowledge Tracing (AKT) and cognitive tracking models.

Adheres strictly to Phase 2A and Phase 2B research specifications.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional, Union, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, model_validator, ConfigDict


class ModalityType(str, Enum):
    """Supported assessment modalities."""
    MCQ = "MCQ"
    SHORT_ANSWER = "SHORT_ANSWER"
    CODING = "CODING"


class EvaluationLifecycle(str, Enum):
    """Lifecycle state of the evaluation event."""
    PENDING_EVALUATION = "PENDING_EVALUATION"
    EVALUATED_SUCCESS = "EVALUATED_SUCCESS"
    EVALUATION_ERROR_STUDENT_CODE = "EVALUATION_ERROR_STUDENT_CODE"
    EVALUATION_TIMEOUT_STUDENT_CODE = "EVALUATION_TIMEOUT_STUDENT_CODE"
    EVALUATION_FAILED_INFRASTRUCTURE = "EVALUATION_FAILED_INFRASTRUCTURE"


class AdmissionStatus(str, Enum):
    """Cognitive model mastery admission status."""
    PENDING_EVALUATION = "PENDING_EVALUATION"
    ADMITTED_BINARY = "ADMITTED_BINARY"
    ADMITTED_PARTIAL_CREDIT = "ADMITTED_PARTIAL_CREDIT"
    ADMITTED_FORMATIVE_ONLY = "ADMITTED_FORMATIVE_ONLY"
    PENDING_RESEARCH_POLICY = "PENDING_RESEARCH_POLICY"
    REJECTED_INFRASTRUCTURE_FAILURE = "REJECTED_INFRASTRUCTURE_FAILURE"


class MCQDetails(BaseModel):
    """Modality-specific details for Multiple Choice Questions."""
    model_config = ConfigDict(extra="forbid")

    selected_option_id: str = Field(..., description="Option identifier chosen by student")
    correct_option_id: str = Field(..., description="Canonical correct option identifier")


class ShortAnswerDetails(BaseModel):
    """Modality-specific details for Short Answer Questions."""
    model_config = ConfigDict(extra="forbid")

    submitted_text: str = Field(..., description="Raw text response written by student")
    sbert_cosine_similarity: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Raw continuous cosine similarity from SBERT model [-1.0, 1.0]"
    )
    embedding_model: str = Field(..., description="Identifier of the transformer embedding model")


class CodingDetails(BaseModel):
    """Modality-specific details for Coding Challenges."""
    model_config = ConfigDict(extra="forbid")

    submitted_code: str = Field(..., description="Source code submitted by student")
    tests_run: Optional[int] = Field(None, ge=0, description="Count of test cases actually executed")
    tests_passed: Optional[int] = Field(None, ge=0, description="Count of test cases successfully passed")
    tests_failed: Optional[int] = Field(None, ge=0, description="Count of test cases executed that failed")
    tests_not_run: Optional[int] = Field(None, ge=0, description="Count of test cases configured but unexecuted")
    total_test_cases: Optional[int] = Field(None, ge=0, description="Total test cases in problem definition")
    execution_duration_ms: Optional[float] = Field(None, ge=0.0, description="Sandbox container execution duration")
    sandbox_exit_code: Optional[int] = Field(None, description="Process exit code inside sandbox")
    infrastructure_error_message: Optional[str] = Field(None, description="Diagnostic error when infrastructure fails")


class ModalityDetails(BaseModel):
    """Container for modality-specific evaluation payloads."""
    model_config = ConfigDict(extra="forbid")

    mcq: Optional[MCQDetails] = None
    short_answer: Optional[ShortAnswerDetails] = None
    coding: Optional[CodingDetails] = None


class BehavioralTelemetry(BaseModel):
    """Client-side interaction telemetry captured during item resolution."""
    model_config = ConfigDict(extra="forbid")

    dwell_time_seconds: Optional[float] = Field(None, ge=0.0, description="Active time spent resolving item")
    hint_count: Optional[int] = Field(None, ge=0, description="Number of hint levels viewed")
    highest_hint_level: Optional[int] = Field(None, ge=0, description="Maximum progressive hint tier unlocked")
    answer_revision_count: Optional[int] = Field(None, ge=0, description="Count of answer modifications before submit")


class UnifiedEvidenceRecord(BaseModel):
    """
    Canonical Unified Multimodal Evidence Record for Adaptive Knowledge Tracing.
    Provides typed, validated representation across MCQ, Short Answer, and Coding modalities.
    """
    model_config = ConfigDict(extra="forbid")

    # A. Identity and Provenance
    evidence_id: str = Field(..., description="Unique discrete evidence identifier")
    submission_id: str = Field(..., description="Parent transaction / idempotency submission identifier")
    bundle_id: str = Field(..., description="Assessment bundle grouping identifier")
    student_id: str = Field(..., description="Student / user identifier")
    item_id: str = Field(..., description="Assessment question / challenge identifier")
    concept_id: str = Field(..., description="Target Knowledge Component (KC) identifier")
    item_attempt_number: Optional[int] = Field(
        None,
        ge=1,
        description="1-based ordinal submission count for this item (null if uninstrumented)"
    )
    concept_cumulative_attempt_number: Optional[int] = Field(
        None,
        ge=1,
        description="Cumulative historical interaction count across concept"
    )
    modality: ModalityType = Field(..., description="Assessment modality (MCQ, SHORT_ANSWER, CODING)")
    evaluator_version: Optional[str] = Field(None, description="Version string of evaluation engine")

    # Timestamps
    client_submission_timestamp: Optional[str] = Field(
        None,
        description="ISO 8601 UTC timestamp emitted by client (null if uninstrumented)"
    )
    server_receipt_timestamp: str = Field(..., description="ISO 8601 UTC timestamp recorded by gateway")
    evaluation_start_timestamp: Optional[str] = Field(None, description="ISO 8601 UTC timestamp evaluation began")
    evaluation_completion_timestamp: Optional[str] = Field(None, description="ISO 8601 UTC timestamp evaluation completed")

    # B. Evaluation Outcome
    evaluation_lifecycle: EvaluationLifecycle = Field(..., description="Lifecycle status of evaluation")
    admission_status: AdmissionStatus = Field(..., description="Cognitive model mastery admission status")
    raw_score: Optional[float] = Field(
        None,
        description="Uncalibrated raw performance metric (non-negative for MCQ/Coding, [-1.0, 1.0] for Short Answer)"
    )
    maximum_possible_score: Optional[float] = Field(None, ge=0.0, description="Maximum achievable raw score")
    normalized_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Bounded [0.0, 1.0] performance")
    correctness: Optional[bool] = Field(None, description="Calibrated binary correctness (null for uncalibrated/pending)")

    # Modality & Telemetry Details
    modality_details: Optional[ModalityDetails] = None
    behavioral_telemetry: Optional[BehavioralTelemetry] = None

    @model_validator(mode="after")
    def validate_lifecycle_and_admission_invariants(self) -> "UnifiedEvidenceRecord":
        """Enforces Phase 2A and Phase 2B invariants across lifecycles, modalities, and cognitive admission."""

        # 1. Infrastructure Failure Invariants
        if self.evaluation_lifecycle == EvaluationLifecycle.EVALUATION_FAILED_INFRASTRUCTURE:
            if self.raw_score is not None:
                raise ValueError("Infrastructure failure must not record a numeric raw_score.")
            if self.normalized_score is not None:
                raise ValueError("Infrastructure failure must not record a numeric normalized_score.")
            if self.correctness is not None:
                raise ValueError("Infrastructure failure must not record correctness boolean.")
            if self.evaluation_completion_timestamp is not None:
                raise ValueError("Infrastructure failure must have null evaluation_completion_timestamp.")
            if self.admission_status != AdmissionStatus.REJECTED_INFRASTRUCTURE_FAILURE:
                raise ValueError(
                    f"Infrastructure failure must have admission_status REJECTED_INFRASTRUCTURE_FAILURE, "
                    f"got {self.admission_status}."
                )
            if self.modality_details and self.modality_details.coding:
                coding = self.modality_details.coding
                if coding.tests_run is not None and coding.tests_run > 0:
                    raise ValueError("Infrastructure failure cannot have tests_run > 0.")
                if coding.tests_passed is not None:
                    raise ValueError("Infrastructure failure must have null tests_passed (unexecuted tests are not passed).")
                if coding.tests_failed is not None:
                    raise ValueError("Infrastructure failure must have null tests_failed (unexecuted tests are not failed).")

        # 2. Pending Evaluation Invariants
        elif self.evaluation_lifecycle == EvaluationLifecycle.PENDING_EVALUATION:
            if self.raw_score is not None:
                raise ValueError("Pending evaluation must have null raw_score.")
            if self.normalized_score is not None:
                raise ValueError("Pending evaluation must have null normalized_score.")
            if self.correctness is not None:
                raise ValueError("Pending evaluation must have null correctness.")
            if self.evaluation_completion_timestamp is not None:
                raise ValueError("Pending evaluation must have null evaluation_completion_timestamp.")
            if self.admission_status != AdmissionStatus.PENDING_EVALUATION:
                raise ValueError(
                    f"Pending evaluation must have admission_status PENDING_EVALUATION, got {self.admission_status}."
                )

        # 3. Successful Evaluation Invariants
        elif self.evaluation_lifecycle == EvaluationLifecycle.EVALUATED_SUCCESS:
            if self.evaluation_completion_timestamp is None:
                raise ValueError("Evaluated success must have an evaluation_completion_timestamp.")
            if self.normalized_score is None:
                raise ValueError("Evaluated success must have a normalized_score.")

        # 4. Modality-Specific Cognitive Admission Guardrails and Raw Score Constraints
        if self.raw_score is not None:
            if self.modality in (ModalityType.MCQ, ModalityType.CODING):
                if self.raw_score < 0.0:
                    raise ValueError(f"{self.modality.value} raw_score must be non-negative (>= 0.0), got {self.raw_score}.")
            elif self.modality == ModalityType.SHORT_ANSWER:
                if not (-1.0 <= self.raw_score <= 1.0):
                    raise ValueError(f"Short Answer raw_score must be within [-1.0, 1.0], got {self.raw_score}.")

        if self.modality == ModalityType.MCQ:
            if self.evaluation_lifecycle == EvaluationLifecycle.EVALUATED_SUCCESS:
                if self.admission_status not in (AdmissionStatus.ADMITTED_BINARY, AdmissionStatus.ADMITTED_FORMATIVE_ONLY):
                    raise ValueError(f"MCQ evaluated success cannot have admission status {self.admission_status}.")
        elif self.modality == ModalityType.SHORT_ANSWER:
            if self.admission_status == AdmissionStatus.ADMITTED_BINARY:
                raise ValueError("Short Answer cannot be admitted as ADMITTED_BINARY (uncalibrated semantic similarity).")
            if self.correctness is not None:
                raise ValueError("Short Answer correctness must remain null (continuous SBERT similarity is not binary).")
        elif self.modality == ModalityType.CODING:
            if self.admission_status == AdmissionStatus.ADMITTED_BINARY:
                raise ValueError("Coding evaluation cannot be admitted as ADMITTED_BINARY into live MCQ EMA tracker.")
            if self.evaluation_lifecycle == EvaluationLifecycle.EVALUATED_SUCCESS:
                if self.admission_status not in (AdmissionStatus.PENDING_RESEARCH_POLICY, AdmissionStatus.ADMITTED_FORMATIVE_ONLY):
                    raise ValueError(
                        f"Coding evaluated success must remain PENDING_RESEARCH_POLICY or ADMITTED_FORMATIVE_ONLY, "
                        f"got {self.admission_status}."
                    )

        # 5. Modality Details Consistency Check
        if self.modality_details is not None:
            if self.modality == ModalityType.MCQ and self.modality_details.mcq is None:
                raise ValueError("Modality is MCQ but modality_details.mcq is missing.")
            elif self.modality == ModalityType.SHORT_ANSWER and self.modality_details.short_answer is None:
                raise ValueError("Modality is SHORT_ANSWER but modality_details.short_answer is missing.")
            elif self.modality == ModalityType.CODING and self.modality_details.coding is None:
                raise ValueError("Modality is CODING but modality_details.coding is missing.")

        return self

