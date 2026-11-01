"""
src/engine/adaptive_selector.py

Uncertainty-Guided Adaptive Activity Selector Engine.
Selects target unmastered concepts using Priority Score: (1.0 - mastery) * (1.0 + uncertainty).
Routes activity modalities based on specific mastery & uncertainty thresholds:
- MCQ (0): High uncertainty / Low mastery (mastery < 0.50 or uncertainty >= 0.35)
- Short Answer (2): Mid-range mastery (0.50 <= mastery < 0.75 and uncertainty < 0.35)
- Coding (1): High mastery (mastery >= 0.75)

Features Adaptive Scaffolding:
1. Difficulty Scaffolding: Score < 0.5 downgrades difficulty; Score > 0.8 upgrades difficulty.
2. Difficulty Floor: Score < 0.5 on 'easy' maintains 'easy' floor and cycles to a new unattempted question.
3. Modality Downgrade: Failing (< 0.5) an 'easy' Coding or Short Answer task immediately downgrades modality to MCQ.
4. Prerequisite Fallback: Failing 3 'easy' questions in a row for a concept dynamically routes back to a lower concept_id.
"""

from typing import Dict, List, Tuple, Any, Optional

class AdaptiveActivitySelector:
    """
    Adaptive Policy Engine for Knowledge-Driven Activity Recommendation.
    Implements uncertainty-guided concept targeting, threshold activity routing,
    difficulty scaffolding with floor protection, modality downgrade, and prerequisite fallback.
    """
    DIFFICULTY_LEVELS = ["easy", "medium", "hard"]
    DIFFICULTY_DOWNGRADE = {"hard": "medium", "medium": "easy", "easy": "easy"}
    DIFFICULTY_UPGRADE = {"easy": "medium", "medium": "hard", "hard": "hard"}

    DEFAULT_CONCEPT_MAP = {
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

    def __init__(
        self,
        mcq_mastery_threshold: float = 0.50,
        high_uncertainty_threshold: float = 0.35,
        coding_mastery_threshold: float = 0.75,
        concept_map: Optional[Dict[str, int]] = None
    ):
        self.mcq_mastery_threshold = mcq_mastery_threshold
        self.high_uncertainty_threshold = high_uncertainty_threshold
        self.coding_mastery_threshold = coding_mastery_threshold
        self.concept_map = concept_map or self.DEFAULT_CONCEPT_MAP.copy()
        self.id_to_concept = {v: k for k, v in self.concept_map.items()}

    def compute_priority_score(self, mastery: float, uncertainty: float) -> float:
        """
        Calculates Concept Selection Priority Score:
        Priority = (1.0 - mastery) * (1.0 + uncertainty)
        
        Prioritizes unmastered concepts (low mastery) with high epistemic model uncertainty.
        """
        m = max(0.0, min(1.0, float(mastery)))
        u = max(0.0, min(1.0, float(uncertainty)))
        priority = (1.0 - m) * (1.0 + u)
        return float(priority)

    def check_difficulty_floor(
        self,
        difficulty: str,
        score: float
    ) -> Tuple[bool, str]:
        """
        Difficulty Floor Rule:
        If a student scores < 0.5 on an 'easy' question, the engine maintains the 'easy'
        difficulty floor and triggers cycling to a new unattempted question.
        
        Returns:
        - (is_floor_reached, action_recommendation)
        """
        diff = str(difficulty).lower().strip()
        is_floor = (diff == "easy" and float(score) < 0.5)
        action = "cycle_unattempted" if is_floor else "normal"
        return is_floor, action

    def check_modality_downgrade(
        self,
        last_activity_type: Optional[Any],
        last_difficulty: Optional[str],
        last_evidence_score: Optional[float]
    ) -> Tuple[bool, Optional[str], Optional[int], Optional[str]]:
        """
        Modality Downgrade Rule:
        If a student fails (< 0.5) an 'easy' Coding (code=1) or Short Answer (code=2) task,
        the engine must downgrade the activity_type to MCQ (code=0).
        
        Returns:
        - (is_downgraded, downgraded_act_name, downgraded_act_code, explanation)
        """
        if last_difficulty is None or last_evidence_score is None:
            return False, None, None, None

        is_easy = str(last_difficulty).lower().strip() == "easy"
        score = float(last_evidence_score)

        if not (is_easy and score < 0.5):
            return False, None, None, None

        # Check if previous task was Coding (1) or Short Answer (2)
        is_code = (last_activity_type == 1 or str(last_activity_type).lower().strip() in ["code", "coding", "1"])
        is_sa = (last_activity_type == 2 or str(last_activity_type).lower().strip() in ["short answer", "short_answer", "text", "2"])

        if is_code or is_sa:
            task_type_str = "Coding" if is_code else "Short Answer"
            reason = (
                f"Modality Downgrade Activated: Student failed an 'easy' {task_type_str} task "
                f"(evidence score {score:.2f} < 0.50). "
                f"Downgrading activity modality to MCQ for scaffolded conceptual remediation."
            )
            return True, "MCQ", 0, reason

        return False, None, None, None

    def route_activity_type(
        self,
        mastery: float,
        uncertainty: float,
        last_activity_type: Optional[Any] = None,
        last_difficulty: Optional[str] = None,
        last_evidence_score: Optional[float] = None
    ) -> Tuple[str, int, str]:
        """
        Routes activity modality based on mastery, uncertainty, and Modality Downgrade rules:
        - If student failed an 'easy' Coding or Short Answer task -> Modality Downgrade to MCQ (0)
        - Otherwise standard thresholds:
          - Low mastery / High uncertainty (mastery < 0.50 or uncertainty >= 0.35) -> MCQ (0)
          - Mid-range mastery (0.50 <= mastery < 0.75 and uncertainty < 0.35) -> Short Answer (2)
          - High mastery (mastery >= 0.75) -> Coding (1)
        
        Returns:
        - (activity_name, activity_code, reasoning_explanation)
        """
        # 1. Check Modality Downgrade override
        downgraded, d_name, d_code, d_reason = self.check_modality_downgrade(
            last_activity_type=last_activity_type,
            last_difficulty=last_difficulty,
            last_evidence_score=last_evidence_score
        )
        if downgraded:
            return d_name, d_code, d_reason

        # 2. Standard threshold routing
        m = float(mastery)
        u = float(uncertainty)

        if m < self.mcq_mastery_threshold or u >= self.high_uncertainty_threshold:
            act_name = "MCQ"
            act_code = 0
            reason = (
                f"Target concept has high uncertainty (sigma={u:.2f} >= {self.high_uncertainty_threshold:.2f}) "
                f"or low mastery (mu={m:.2f} < {self.mcq_mastery_threshold:.2f}). "
                "Routing to Multiple Choice Question (MCQ) for scaffolded conceptual remediation."
            )
        elif self.mcq_mastery_threshold <= m < self.coding_mastery_threshold and u < self.high_uncertainty_threshold:
            act_name = "Short Answer"
            act_code = 2
            reason = (
                f"Target concept is in developing mastery range ({self.mcq_mastery_threshold:.2f} <= mu={m:.2f} < {self.coding_mastery_threshold:.2f}). "
                "Routing to Natural Language Short Answer for conceptual explanation."
            )
        else:
            act_name = "Code"
            act_code = 1
            reason = (
                f"Target concept has high mastery (mu={m:.2f} >= {self.coding_mastery_threshold:.2f}). "
                "Routing to Python Coding Task for hands-on synthesis and unit-test problem solving."
            )

        return act_name, act_code, reason

    def scaffold_difficulty(
        self,
        last_evidence_score: Optional[float] = None,
        current_difficulty: str = "medium"
    ) -> Tuple[str, str]:
        """
        Implements difficulty scaffolding and Difficulty Floor:
        - If student's last evidence score for a concept was < 0.5:
          - If current_difficulty is 'easy': maintain 'easy' difficulty floor and cycle to new unattempted question.
          - Otherwise: route to an easier question ('hard' -> 'medium', 'medium' -> 'easy').
        - If > 0.8: route to a harder question ('easy' -> 'medium', 'medium' -> 'hard', 'hard' -> 'hard').
        - Otherwise (0.5 <= score <= 0.8) or if no last score: maintain current difficulty.
        
        Returns:
        - (recommended_difficulty, scaffolding_reasoning)
        """
        curr = str(current_difficulty).lower().strip() if current_difficulty else "medium"
        if curr not in self.DIFFICULTY_LEVELS:
            curr = "medium"

        if last_evidence_score is None:
            return curr, f"No previous interaction score recorded for concept. Baseline difficulty set to '{curr}'."

        score = float(last_evidence_score)
        if score < 0.5:
            if curr == "easy":
                # Difficulty Floor: maintain 'easy' difficulty but cycle to new unattempted question
                reason = (
                    f"Difficulty Floor Reached: Student scored {score:.2f} (< 0.50) on an 'easy' question. "
                    "Maintaining 'easy' difficulty floor and cycling to a new unattempted question."
                )
                return "easy", reason
            else:
                new_diff = self.DIFFICULTY_DOWNGRADE.get(curr, "easy")
                reason = (
                    f"Student struggled on prior task with evidence score {score:.2f} (< 0.50). "
                    f"Scaffolded difficulty down from '{curr}' to '{new_diff}'."
                )
                return new_diff, reason
        elif score > 0.8:
            new_diff = self.DIFFICULTY_UPGRADE.get(curr, "hard")
            reason = (
                f"Student demonstrated strong performance with evidence score {score:.2f} (> 0.80). "
                f"Scaffolded difficulty up from '{curr}' to '{new_diff}'."
            )
            return new_diff, reason
        else:
            reason = (
                f"Student performance is in nominal range with evidence score {score:.2f} ([0.50, 0.80]). "
                f"Maintained difficulty at '{curr}'."
            )
            return curr, reason

    def count_consecutive_easy_failures(self, concept_history: List[Dict[str, Any]]) -> int:
        """
        Counts consecutive failed attempts (evidence_score < 0.5) on 'easy' difficulty questions
        in reverse chronological order starting from the latest interaction.
        """
        count = 0
        for entry in reversed(concept_history):
            diff = str(entry.get("difficulty", "")).lower().strip()
            score = float(entry.get("evidence_score", 1.0))
            if diff == "easy" and score < 0.5:
                count += 1
            else:
                break
        return count

    def get_prerequisite_concept(self, concept_name: str) -> Tuple[str, int, bool]:
        """
        Finds the prerequisite concept (concept with lower concept_id).
        If concept is already at the lowest concept_id (1), stays at concept_id 1.
        
        Returns:
        - (target_concept_name, target_concept_id, was_fallback_applied)
        """
        curr_id = self.concept_map.get(concept_name, 1)
        if curr_id > 1:
            target_id = curr_id - 1
            target_concept = self.id_to_concept.get(target_id, concept_name)
            return target_concept, target_id, True
        else:
            return concept_name, 1, False

    def recommend_next_activity(
        self,
        knowledge_state_dict: Dict[str, Dict[str, Any]],
        target_concept_override: Optional[str] = None,
        current_difficulty: Optional[str] = None,
        last_evidence_score: Optional[float] = None,
        last_activity_type: Optional[Any] = None,
        consecutive_easy_failures: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Selects the optimal target concept, activity type, and scaffolded difficulty for a student.
        Enforces:
        - Priority ranking: (1.0 - mastery) * (1.0 + uncertainty)
        - Prerequisite Fallback: Routes to lower concept_id if student failed 3 'easy' questions in a row.
        - Difficulty Floor: Maintains 'easy' and cycles unattempted questions if score < 0.5 on easy.
        - Modality Downgrade: Downgrades to MCQ if student failed an easy Coding or Short Answer task.
        
        Parameters:
        - knowledge_state_dict: Dictionary mapping concept names to state dicts {'mastery', 'uncertainty'}
        - target_concept_override: Optional manual selection override
        - current_difficulty: Optional current difficulty level ('easy', 'medium', 'hard')
        - last_evidence_score: Optional last evidence score for difficulty scaffolding
        - last_activity_type: Optional last activity type code or name
        - consecutive_easy_failures: Optional count of consecutive easy failures
        
        Returns:
        - Comprehensive Recommendation Dictionary
        """
        if not knowledge_state_dict:
            raise ValueError("Knowledge state dictionary cannot be empty.")

        priorities = []
        for c_name, c_state in knowledge_state_dict.items():
            m = float(c_state.get("mastery", 0.30))
            u = float(c_state.get("uncertainty", 0.50))
            p_score = self.compute_priority_score(m, u)
            
            priorities.append({
                "concept": c_name,
                "mastery": m,
                "uncertainty": u,
                "priority_score": p_score
            })

        # Sort concepts by Priority Score descending
        priorities.sort(key=lambda x: x["priority_score"], reverse=True)

        if target_concept_override and target_concept_override in knowledge_state_dict:
            selected_concept_info = next(p for p in priorities if p["concept"] == target_concept_override)
        else:
            selected_concept_info = priorities[0]

        sel_concept = selected_concept_info["concept"]
        c_state = knowledge_state_dict.get(sel_concept, {})

        # -------------------------------------------------------------
        # 1. Prerequisite Fallback Check
        # -------------------------------------------------------------
        if consecutive_easy_failures is None:
            if "consecutive_easy_failures" in c_state:
                consecutive_easy_failures = int(c_state["consecutive_easy_failures"])
            else:
                consecutive_easy_failures = self.count_consecutive_easy_failures(c_state.get("history", []))

        prerequisite_fallback_applied = False
        original_concept = sel_concept
        fallback_reason = ""

        if consecutive_easy_failures >= 3:
            lower_concept, lower_id, can_fallback = self.get_prerequisite_concept(sel_concept)
            if can_fallback:
                prerequisite_fallback_applied = True
                curr_id = self.concept_map.get(sel_concept, 1)
                fallback_reason = (
                    f"Prerequisite Fallback Activated: Student failed {consecutive_easy_failures} 'easy' questions "
                    f"in a row on '{sel_concept}' (concept_id={curr_id}). "
                    f"Dynamically routing back to prerequisite concept '{lower_concept}' (concept_id={lower_id}) "
                    "for foundational remediation."
                )
                sel_concept = lower_concept
                c_state = knowledge_state_dict.get(sel_concept, {})
            else:
                fallback_reason = (
                    f"Prerequisite Floor: Student failed {consecutive_easy_failures} 'easy' questions in a row on '{sel_concept}', "
                    "which is already the foundational concept (concept_id=1). Remaining on this concept."
                )

        sel_mastery = float(c_state.get("mastery", 0.30))
        sel_uncertainty = float(c_state.get("uncertainty", 0.50))
        sel_priority = self.compute_priority_score(sel_mastery, sel_uncertainty)

        # -------------------------------------------------------------
        # 2. Extract State History for Scaffolding & Modality
        # -------------------------------------------------------------
        if last_evidence_score is None:
            if "last_evidence_score" in c_state:
                last_evidence_score = c_state["last_evidence_score"]
            elif c_state.get("history"):
                last_evidence_score = c_state["history"][-1].get("evidence_score")

        if current_difficulty is None:
            current_difficulty = c_state.get("last_difficulty", c_state.get("difficulty", "medium"))

        if last_activity_type is None:
            if "last_activity_type" in c_state:
                last_activity_type = c_state["last_activity_type"]
            elif c_state.get("history"):
                last_activity_type = c_state["history"][-1].get("activity_type")

        # -------------------------------------------------------------
        # 3. Difficulty Scaffolding with Difficulty Floor
        # -------------------------------------------------------------
        # If prerequisite fallback was just applied, set difficulty to easy for the prerequisite
        if prerequisite_fallback_applied:
            rec_difficulty = "easy"
            diff_reasoning = f"Set to 'easy' for prerequisite foundational review on '{sel_concept}'."
            cycle_unattempted = False
            difficulty_floor_active = False
        else:
            rec_difficulty, diff_reasoning = self.scaffold_difficulty(
                last_evidence_score=last_evidence_score,
                current_difficulty=current_difficulty
            )
            difficulty_floor_active, cycle_action = self.check_difficulty_floor(
                difficulty=current_difficulty,
                score=last_evidence_score if last_evidence_score is not None else 1.0
            )
            cycle_unattempted = (cycle_action == "cycle_unattempted")

        # -------------------------------------------------------------
        # 4. Modality Downgrade & Activity Routing
        # -------------------------------------------------------------
        if prerequisite_fallback_applied:
            # When falling back to prerequisite after repeated failures, route to MCQ
            act_name = "MCQ"
            act_code = 0
            act_reason = "Routing to Multiple Choice Question (MCQ) for scaffolded prerequisite mastery."
            modality_downgraded = False
        else:
            is_downgraded, d_name, d_code, d_reason = self.check_modality_downgrade(
                last_activity_type=last_activity_type,
                last_difficulty=current_difficulty,
                last_evidence_score=last_evidence_score
            )
            if is_downgraded:
                act_name = d_name
                act_code = d_code
                act_reason = d_reason
                modality_downgraded = True
            else:
                act_name, act_code, act_reason = self.route_activity_type(sel_mastery, sel_uncertainty)
                modality_downgraded = False

        # -------------------------------------------------------------
        # 5. Composite Policy Reasoning
        # -------------------------------------------------------------
        reasoning_parts = []
        if fallback_reason:
            reasoning_parts.append(fallback_reason)
        reasoning_parts.append(act_reason)
        reasoning_parts.append(f"Difficulty Scaffolding: {diff_reasoning}")
        full_reasoning = " | ".join(reasoning_parts)

        return {
            "recommended_concept": sel_concept,
            "concept_id": self.concept_map.get(sel_concept, 1),
            "priority_score": sel_priority,
            "recommended_activity": act_name,
            "activity_code": act_code,
            "concept_mastery": sel_mastery,
            "concept_uncertainty": sel_uncertainty,
            "recommended_difficulty": rec_difficulty,
            "scaffolding_reasoning": diff_reasoning,
            "difficulty_floor_active": difficulty_floor_active,
            "cycle_unattempted": cycle_unattempted,
            "modality_downgraded": modality_downgraded,
            "prerequisite_fallback_applied": prerequisite_fallback_applied,
            "original_concept": original_concept if prerequisite_fallback_applied else None,
            "consecutive_easy_failures": consecutive_easy_failures,
            "reasoning": full_reasoning,
            "all_concept_priorities": priorities
        }
