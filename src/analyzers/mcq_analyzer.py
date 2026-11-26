"""
src/analyzers/mcq_analyzer.py

MCQ Response Analyzer for Multiple Choice Questions.
Evaluates student selected options against target correct keys, calculates binary or partial score,
and computes distractor analysis metrics.
"""

from typing import Dict, List, Any, Optional

class MCQAnalyzer:
    """
    Analyzes Multiple Choice Question (MCQ) interactions.
    Computes exact correctness (0.0 or 1.0) and response quality metadata.
    """
    def __init__(self):
        pass

    def evaluate(
        self,
        student_option: str,
        correct_option: str,
        distractor_weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates student MCQ selection.
        
        Parameters:
        - student_option: Option selected by student (e.g. 'A', 'B', 'option_1')
        - correct_option: Ground truth correct option key
        - distractor_weights: Optional partial credit mapping for near-correct options
        
        Returns:
        - Dict with 'evidence_score' (0.0 to 1.0), 'is_correct' (bool), and metadata.
        """
        if not student_option or not correct_option:
            return {
                "evidence_score": 0.0,
                "is_correct": False,
                "feedback": "Missing student selection or answer key."
            }

        s_opt = str(student_option).strip().upper()
        c_opt = str(correct_option).strip().upper()

        if s_opt == c_opt:
            return {
                "evidence_score": 1.0,
                "is_correct": True,
                "feedback": "Correct selection."
            }

        # Check partial credit distractor weights if provided
        if distractor_weights and s_opt in distractor_weights:
            score = float(distractor_weights[s_opt])
            score_clamped = max(0.0, min(1.0, score))
            return {
                "evidence_score": score_clamped,
                "is_correct": False,
                "feedback": f"Partial credit distractor selected (Score: {score_clamped:.2f})."
            }

        return {
            "evidence_score": 0.0,
            "is_correct": False,
            "feedback": "Incorrect option selected."
        }
