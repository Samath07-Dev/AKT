"""
test_engine.py

Verification script for KnowledgeStateTracker and AdaptiveActivitySelector.
"""

from src.engine import KnowledgeStateTracker, AdaptiveActivitySelector

def test_adaptive_engine():
    print("=" * 60)
    print("      Verifying Adaptive Engine & Activity Selector      ")
    print("=" * 60)

    # 1. Initialize Tracker & Selector
    tracker = KnowledgeStateTracker()
    selector = AdaptiveActivitySelector()

    # Manually set test concept states
    # Concept 1: Low Mastery, High Uncertainty -> Should route to MCQ
    tracker.set_concept_state("Loops", mastery=0.20, uncertainty=0.60)
    
    # Concept 2: Mid Mastery, Low Uncertainty -> Should route to Short Answer
    tracker.set_concept_state("Conditionals", mastery=0.60, uncertainty=0.20)
    
    # Concept 3: High Mastery, Low Uncertainty -> Should route to Code
    tracker.set_concept_state("Variables", mastery=0.85, uncertainty=0.10)

    state_dict = tracker.get_knowledge_state()

    # 2. Test Priority Score formula: (1.0 - mastery) * (1.0 + uncertainty)
    p_loops = selector.compute_priority_score(0.20, 0.60)  # (1 - 0.2) * (1 + 0.6) = 0.8 * 1.6 = 1.28
    p_cond = selector.compute_priority_score(0.60, 0.20)   # (1 - 0.6) * (1 + 0.2) = 0.4 * 1.2 = 0.48
    p_vars = selector.compute_priority_score(0.85, 0.10)   # (1 - 0.85) * (1 + 0.1) = 0.15 * 1.1 = 0.165

    print("\n1. Concept Priority Scores:")
    print(f"  - Loops (m=0.20, u=0.60):        Priority = {p_loops:.4f} (Expected: 1.2800)")
    print(f"  - Conditionals (m=0.60, u=0.20): Priority = {p_cond:.4f} (Expected: 0.4800)")
    print(f"  - Variables (m=0.85, u=0.10):    Priority = {p_vars:.4f} (Expected: 0.1650)")

    assert abs(p_loops - 1.2800) < 1e-4
    assert abs(p_cond - 0.4800) < 1e-4
    assert abs(p_vars - 0.1650) < 1e-4

    # 3. Test Adaptive Recommendation Engine
    rec = selector.recommend_next_activity(state_dict)

    print("\n2. Adaptive Recommendation Result:")
    print(f"  - Recommended Concept:  {rec['recommended_concept']} (Expected: Loops)")
    print(f"  - Recommended Activity: {rec['recommended_activity']} (Expected: MCQ)")
    print(f"  - Activity Code:        {rec['activity_code']} (Expected: 0)")
    print(f"  - Priority Score:       {rec['priority_score']:.4f}")
    print(f"  - Policy Reasoning:     {rec['reasoning']}")

    assert rec['recommended_concept'] == "Loops"
    assert rec['recommended_activity'] == "MCQ"
    assert rec['activity_code'] == 0

    # 4. Test Threshold Routing for Mid-Range & High Mastery
    act_name_mid, act_code_mid, _ = selector.route_activity_type(mastery=0.60, uncertainty=0.20)
    act_name_high, act_code_high, _ = selector.route_activity_type(mastery=0.85, uncertainty=0.10)

    print("\n3. Threshold Routing Policy Validation:")
    print(f"  - Mid-Range Mastery (m=0.60, u=0.20) -> Activity: {act_name_mid} (Code: {act_code_mid}, Expected: Short Answer, 2)")
    print(f"  - High Mastery (m=0.85, u=0.10)      -> Activity: {act_name_high} (Code: {act_code_high}, Expected: Code, 1)")

    assert act_name_mid == "Short Answer" and act_code_mid == 2
    assert act_name_high == "Code" and act_code_high == 1

    # 5. Test Real-time Knowledge State Updating
    print("\n4. Real-time Knowledge State Updating:")
    pre_m, pre_u = tracker.get_concept_state("Loops")
    upd = tracker.update_state("Loops", evidence_score=1.0, activity_type=0)
    post_m, post_u = tracker.get_concept_state("Loops")
    
    print(f"  - Pre-update  Loops Mastery: {pre_m:.2f}, Uncertainty: {pre_u:.2f}")
    print(f"  - Post-update Loops Mastery: {post_m:.2f}, Uncertainty: {post_u:.2f}")

    assert post_m > pre_m
    assert post_u < pre_u

    # 6. Test Difficulty Scaffolding Policy:
    # - If score < 0.5 -> route to easier question
    # - If score > 0.8 -> route to harder question
    # - If 0.5 <= score <= 0.8 -> maintain difficulty
    print("\n5. Verifying Difficulty Scaffolding Policy:")
    
    # Downgrades (< 0.5)
    d_down_hard, _ = selector.scaffold_difficulty(last_evidence_score=0.40, current_difficulty="hard")
    d_down_med, _ = selector.scaffold_difficulty(last_evidence_score=0.20, current_difficulty="medium")
    d_down_easy, _ = selector.scaffold_difficulty(last_evidence_score=0.00, current_difficulty="easy")
    print(f"  - Score < 0.5: hard -> {d_down_hard} (Expected: medium)")
    print(f"  - Score < 0.5: medium -> {d_down_med} (Expected: easy)")
    print(f"  - Score < 0.5: easy -> {d_down_easy} (Expected: easy)")
    assert d_down_hard == "medium"
    assert d_down_med == "easy"
    assert d_down_easy == "easy"

    # Upgrades (> 0.8)
    d_up_easy, _ = selector.scaffold_difficulty(last_evidence_score=0.85, current_difficulty="easy")
    d_up_med, _ = selector.scaffold_difficulty(last_evidence_score=1.00, current_difficulty="medium")
    d_up_hard, _ = selector.scaffold_difficulty(last_evidence_score=0.95, current_difficulty="hard")
    print(f"  - Score > 0.8: easy -> {d_up_easy} (Expected: medium)")
    print(f"  - Score > 0.8: medium -> {d_up_med} (Expected: hard)")
    print(f"  - Score > 0.8: hard -> {d_up_hard} (Expected: hard)")
    assert d_up_easy == "medium"
    assert d_up_med == "hard"
    assert d_up_hard == "hard"

    # Maintains ([0.5, 0.8])
    d_nom_easy, _ = selector.scaffold_difficulty(last_evidence_score=0.65, current_difficulty="easy")
    d_nom_med, _ = selector.scaffold_difficulty(last_evidence_score=0.50, current_difficulty="medium")
    d_nom_hard, _ = selector.scaffold_difficulty(last_evidence_score=0.80, current_difficulty="hard")
    print(f"  - Score in [0.5, 0.8]: maintained at easy -> {d_nom_easy}, med -> {d_nom_med}, hard -> {d_nom_hard}")
    assert d_nom_easy == "easy"
    assert d_nom_med == "medium"
    assert d_nom_hard == "hard"

    # Recommendation integration with difficulty scaffolding
    rec_with_diff = selector.recommend_next_activity(
        state_dict,
        target_concept_override="Loops",
        current_difficulty="medium",
        last_evidence_score=0.90
    )
    print(f"  - Recommendation scaffolded difficulty: {rec_with_diff['recommended_difficulty']} (Expected: hard)")
    assert rec_with_diff['recommended_difficulty'] == "hard"

    # 7. Test Difficulty Floor Logic
    print("\n6. Verifying Difficulty Floor & Cycle Logic:")
    is_floor, action = selector.check_difficulty_floor(difficulty="easy", score=0.20)
    print(f"  - Score 0.20 on easy: is_floor={is_floor}, action={action} (Expected: True, 'cycle_unattempted')")
    assert is_floor is True
    assert action == "cycle_unattempted"
    
    rec_floor = selector.recommend_next_activity(
        state_dict,
        target_concept_override="Loops",
        current_difficulty="easy",
        last_evidence_score=0.20
    )
    assert rec_floor["recommended_difficulty"] == "easy"
    assert rec_floor["difficulty_floor_active"] is True
    assert rec_floor["cycle_unattempted"] is True
    print(f"  - Recommendation correctly maintains 'easy' floor with cycle_unattempted=True.")

    # 8. Test Modality Downgrade Logic
    print("\n7. Verifying Modality Downgrade Logic:")
    # Student has high mastery (normally routes to Code), but failed an 'easy' Coding task
    is_down, d_act, d_code, d_reason = selector.check_modality_downgrade(
        last_activity_type="Code",
        last_difficulty="easy",
        last_evidence_score=0.30
    )
    print(f"  - Failed easy Coding task -> Downgrade: {is_down}, Modality: {d_act} (code: {d_code})")
    assert is_down is True
    assert d_act == "MCQ"
    assert d_code == 0

    # Test via route_activity_type
    act_name_down, act_code_down, _ = selector.route_activity_type(
        mastery=0.90,  # High mastery normally gives Code
        uncertainty=0.10,
        last_activity_type=1,
        last_difficulty="easy",
        last_evidence_score=0.25
    )
    print(f"  - High mastery student routing with failed easy code: {act_name_down} (Expected: MCQ)")
    assert act_name_down == "MCQ"
    assert act_code_down == 0

    # Also test Short Answer failure on easy downgrades to MCQ
    act_sa_down, act_sa_code, _ = selector.route_activity_type(
        mastery=0.60,
        uncertainty=0.20,
        last_activity_type="Short Answer",
        last_difficulty="easy",
        last_evidence_score=0.40
    )
    assert act_sa_down == "MCQ"
    assert act_sa_code == 0
    print("  - Failed easy Short Answer correctly downgraded to MCQ.")

    # 9. Test Prerequisite Fallback Logic
    print("\n8. Verifying Prerequisite Fallback Logic:")
    # Loops is concept_id 3. Prerequisite should be Conditionals (concept_id 2).
    prereq_concept, prereq_id, can_fb = selector.get_prerequisite_concept("Loops")
    print(f"  - Loops (id=3) prerequisite: {prereq_concept} (id={prereq_id})")
    assert prereq_concept == "Conditionals"
    assert prereq_id == 2
    assert can_fb is True

    # Variables is concept_id 1. Cannot fallback further.
    var_prereq, var_id, var_can_fb = selector.get_prerequisite_concept("Variables")
    assert var_prereq == "Variables"
    assert var_id == 1
    assert var_can_fb is False

    # Simulate 3 consecutive easy failures on Loops in knowledge state
    fallback_state = {
        "Variables": {"concept_id": 1, "mastery": 0.50, "uncertainty": 0.30, "history": []},
        "Conditionals": {"concept_id": 2, "mastery": 0.40, "uncertainty": 0.40, "history": []},
        "Loops": {
            "concept_id": 3,
            "mastery": 0.20,
            "uncertainty": 0.60,
            "history": [
                {"difficulty": "easy", "evidence_score": 0.20},
                {"difficulty": "easy", "evidence_score": 0.10},
                {"difficulty": "easy", "evidence_score": 0.30}
            ],
            "consecutive_easy_failures": 3
        }
    }
    rec_fallback = selector.recommend_next_activity(
        fallback_state,
        target_concept_override="Loops"
    )
    print(f"  - Target concept was Loops, but failed 3 easy questions in a row.")
    print(f"  - Fallback Recommendation: {rec_fallback['recommended_concept']} (id={rec_fallback['concept_id']})")
    print(f"  - Fallback Applied: {rec_fallback['prerequisite_fallback_applied']}")
    assert rec_fallback["recommended_concept"] == "Conditionals"
    assert rec_fallback["concept_id"] == 2
    assert rec_fallback["prerequisite_fallback_applied"] is True

    print("\nAdaptive Engine & Activity Selector verified successfully with zero errors!")

def test_set_concept_state_with_history():
    """Verifies that set_concept_state correctly accepts history as an optional keyword argument."""
    tracker = KnowledgeStateTracker()
    test_history = [
        {"attempt": 1, "evidence_score": 0.85, "activity_type": 0, "difficulty": "easy"},
        {"attempt": 2, "evidence_score": 0.90, "activity_type": 1, "difficulty": "medium"}
    ]
    tracker.set_concept_state("Variables", mastery=0.88, uncertainty=0.15, history=test_history)
    state = tracker.get_knowledge_state()["Variables"]
    assert state["mastery"] == 0.88
    assert state["uncertainty"] == 0.15
    assert state["history"] == test_history
    assert state["attempts"] == 2

    # Verify calling without history preserves default empty list
    tracker.set_concept_state("Conditionals", mastery=0.70, uncertainty=0.25)
    cond_state = tracker.get_knowledge_state()["Conditionals"]
    assert cond_state["mastery"] == 0.70
    assert cond_state["uncertainty"] == 0.25
    assert cond_state["history"] == []

if __name__ == "__main__":
    test_adaptive_engine()
    test_set_concept_state_with_history()
