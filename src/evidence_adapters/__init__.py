"""
src/evidence_adapters package initialization.

Provides isolated adapters to transform raw evaluator outputs (MCQAnalyzer,
ShortAnswerAnalyzer, SecureDockerPythonEvaluator, CodeAnalyzer) into canonical
Phase 3 UnifiedEvidenceRecord instances, and builds complete embedded bundle evidence.
"""

from .mcq_adapter import adapt_mcq_evaluation
from .short_answer_adapter import adapt_short_answer_evaluation
from .coding_adapter import adapt_coding_evaluation
from .bundle_builder import build_embedded_bundle_evidence, PRIVACY_EXCLUSION_TOKEN

__all__ = [
    "adapt_mcq_evaluation",
    "adapt_short_answer_evaluation",
    "adapt_coding_evaluation",
    "build_embedded_bundle_evidence",
    "PRIVACY_EXCLUSION_TOKEN",
]
