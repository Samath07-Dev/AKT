"""
src/engine/knowledge_state.py

Real-Time Knowledge State Tracker for Adaptive Learning.
Tracks real-time mastery probabilities (mu) and uncertainty estimations (sigma) per concept.
Updates student state sequentially as interaction evidence vectors arrive.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any

class KnowledgeStateTracker:
    """
    Tracks and updates real-time mastery and uncertainty states per concept for a student.
    """
    def __init__(self, concept_map: Optional[Dict[str, int]] = None):
        self.concept_map = concept_map or {
            "Variables": 1,
            "Conditionals": 2,
            "Loops": 3,
            "Functions": 4,
            "Arrays": 5,
            "Syntax": 6,
            "OOP": 7,
            "Dictionaries": 8,
            "File Handling": 9,
            "Exception Handling": 10
        }
        self.id_to_concept = {v: k for k, v in self.concept_map.items()}
        
        # Initialize default knowledge state for each concept
        # mastery: prior = 0.30 (30%), uncertainty: prior = 0.50 (50%)
        self.state: Dict[str, Dict[str, Any]] = {}
        self.reset_state()

    def reset_state(self, initial_mastery: float = 0.30, initial_uncertainty: float = 0.50):
        """Resets or re-initializes knowledge state priors across all concepts."""
        self.state = {}
        for c_name in self.concept_map.keys():
            self.state[c_name] = {
                "concept_id": self.concept_map[c_name],
                "mastery": float(initial_mastery),
                "uncertainty": float(initial_uncertainty),
                "attempts": 0,
                "history": []
            }

    def set_concept_state(
        self,
        concept_name_or_id: Any,
        mastery: float,
        uncertainty: float,
        history: Optional[List[Dict[str, Any]]] = None,
        attempts: Optional[int] = None,
        **kwargs: Any
    ):
        """Manually sets or overwrites predicted mastery, uncertainty, and history for a concept."""
        c_name = self._resolve_concept_name(concept_name_or_id)
        if c_name not in self.state:
            self.state[c_name] = {
                "concept_id": self.concept_map.get(c_name, len(self.state) + 1),
                "mastery": 0.30,
                "uncertainty": 0.50,
                "attempts": 0,
                "history": []
            }
        self.state[c_name]["mastery"] = float(np.clip(mastery, 0.0, 1.0))
        self.state[c_name]["uncertainty"] = float(np.clip(uncertainty, 0.01, 1.0))
        if history is not None:
            self.state[c_name]["history"] = list(history)
            if attempts is None:
                self.state[c_name]["attempts"] = len(history)
        if attempts is not None:
            self.state[c_name]["attempts"] = int(attempts)
        for k, v in kwargs.items():
            self.state[c_name][k] = v

    def update_state(
        self,
        concept_name_or_id: Any,
        evidence_score: float,
        activity_type: int = 0,
        response_time_sec: float = 0.0,
        predicted_uncertainty: Optional[float] = None,
        difficulty: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Updates concept mastery and uncertainty in real-time following a student response interaction.
        
        Parameters:
        - concept_name_or_id: Concept key string or integer ID
        - evidence_score: Continuous correctness score [0.0, 1.0]
        - activity_type: MCQ=0, Code=1, Text=2
        - response_time_sec: Response time in seconds
        - predicted_uncertainty: Optional model MC Dropout uncertainty score
        - difficulty: Optional question difficulty level ('easy', 'medium', 'hard')
        
        Returns:
        - Updated Dict with new 'mastery' and 'uncertainty' for the concept.
        """
        c_name = self._resolve_concept_name(concept_name_or_id)
        if c_name not in self.state:
            # Dynamically add new concept
            self.state[c_name] = {
                "concept_id": self.concept_map.get(c_name, len(self.state) + 1),
                "mastery": 0.30,
                "uncertainty": 0.50,
                "attempts": 0,
                "history": []
            }

        curr = self.state[c_name]
        attempts = curr["attempts"] + 1
        curr_mastery = curr["mastery"]
        curr_unc = curr["uncertainty"]

        # Exponential moving update weighting evidence score against current mastery
        learning_rate = 0.25 if activity_type == 1 else 0.20  # Higher learning gain for code synthesis
        updated_mastery = curr_mastery + learning_rate * (evidence_score - curr_mastery)
        updated_mastery = float(np.clip(updated_mastery, 0.0, 1.0))

        # Update uncertainty: decreases with more attempts unless model provides explicit MC Dropout uncertainty
        if predicted_uncertainty is not None:
            updated_unc = float(np.clip(predicted_uncertainty, 0.01, 1.0))
        else:
            decay_factor = 0.85
            updated_unc = max(0.05, curr_unc * decay_factor)

        # Save to state history
        curr["mastery"] = updated_mastery
        curr["uncertainty"] = updated_unc
        curr["attempts"] = attempts
        curr["last_evidence_score"] = float(evidence_score)
        curr["last_activity_type"] = activity_type
        if difficulty:
            curr["last_difficulty"] = str(difficulty).lower().strip()

        # Track consecutive failures on easy difficulty
        is_easy = (str(difficulty).lower().strip() == "easy") if difficulty else False
        if is_easy and float(evidence_score) < 0.5:
            curr["consecutive_easy_failures"] = curr.get("consecutive_easy_failures", 0) + 1
        elif float(evidence_score) >= 0.5:
            curr["consecutive_easy_failures"] = 0

        curr["history"].append({
            "attempt": attempts,
            "evidence_score": float(evidence_score),
            "activity_type": activity_type,
            "difficulty": difficulty,
            "response_time_sec": float(response_time_sec),
            "post_mastery": updated_mastery,
            "post_uncertainty": updated_unc
        })

        return {
            "concept": c_name,
            "mastery": updated_mastery,
            "uncertainty": updated_unc,
            "attempts": attempts
        }

    def get_knowledge_state(self) -> Dict[str, Dict[str, Any]]:
        """Returns full copy of real-time knowledge states across all concepts."""
        return self.state

    def get_concept_state(self, concept_name_or_id: Any) -> Tuple[float, float]:
        """Returns (mastery, uncertainty) tuple for a specific concept."""
        c_name = self._resolve_concept_name(concept_name_or_id)
        if c_name in self.state:
            return self.state[c_name]["mastery"], self.state[c_name]["uncertainty"]
        return 0.30, 0.50

    def _resolve_concept_name(self, concept_name_or_id: Any) -> str:
        """Helper to resolve concept integer ID or string key to standard concept string."""
        if isinstance(concept_name_or_id, int):
            return self.id_to_concept.get(concept_name_or_id, f"Concept_{concept_name_or_id}")
        return str(concept_name_or_id).strip()
