"""
test_app_optimization.py

Unit and performance tests verifying that app.py functions use proper caching
(@st.cache_data and @st.cache_resource) and that bundle retrieval correctly caches
and structures question bundles across concepts and difficulties.
"""

import json
import pytest
from app import (
    load_reference_answers,
    load_analyzers,
    check_api_status,
    fetch_concept_bundle_from_api_or_cache,
    compute_dashboard_metrics,
    get_cached_recommendation_info,
    build_radar_chart,
    build_priority_bar_chart,
    format_recommendation_card_html,
    format_test_cases_code_blocks,
    evaluate_mcq_cached,
    evaluate_short_answer_cached,
    evaluate_code_cached,
    get_cached_scaffold_difficulty
)

def test_cache_decorators_applied():
    """Verifies that all targeted performance-critical functions are decorated with caching."""
    # Check streamlit caching attributes or wrappers
    assert hasattr(load_reference_answers, "clear") or hasattr(load_reference_answers, "__wrapped__")
    assert hasattr(load_analyzers, "clear") or hasattr(load_analyzers, "__wrapped__")
    assert hasattr(fetch_concept_bundle_from_api_or_cache, "clear")
    assert hasattr(compute_dashboard_metrics, "clear")
    assert hasattr(get_cached_recommendation_info, "clear")
    assert hasattr(build_radar_chart, "clear")
    assert hasattr(build_priority_bar_chart, "clear")
    assert hasattr(format_recommendation_card_html, "clear")
    assert hasattr(format_test_cases_code_blocks, "clear")
    assert hasattr(evaluate_mcq_cached, "clear")
    assert hasattr(evaluate_short_answer_cached, "clear")
    assert hasattr(evaluate_code_cached, "clear")
    assert hasattr(get_cached_scaffold_difficulty, "clear")

def test_fetch_concept_bundle_structure():
    """Tests fetching concept bundles across multiple concepts and difficulty levels."""
    for concept in ["Variables", "Conditionals", "Loops"]:
        for diff in ["easy", "medium", "hard"]:
            bundle_data = fetch_concept_bundle_from_api_or_cache(concept=concept, difficulty=diff)
            assert "concept" in bundle_data
            assert bundle_data["concept"] == concept
            assert bundle_data["difficulty"] == diff
            assert "bundle" in bundle_data
            assert "source" in bundle_data
            
            bundle = bundle_data["bundle"]
            assert "mcqs" in bundle
            assert "short_answer" in bundle
            assert "coding" in bundle
            
            # Exactly 3 MCQs per bundle
            assert len(bundle["mcqs"]) == 3
            # Short answer question exists
            assert "question" in bundle["short_answer"]
            assert "reference_answer" in bundle["short_answer"]
            # Coding challenge exists
            assert "problem" in bundle["coding"]
            assert "test_cases" in bundle["coding"]

def test_dashboard_metrics_and_recommendation_cache():
    """Tests cached calculations for dashboard metrics and recommendation info."""
    masteries = (0.85, 0.60, 0.40, 0.55, 0.40, 0.88, 0.30)
    uncertainties = (0.15, 0.30, 0.50, 0.25, 0.45, 0.10, 0.55)
    concepts = ("Variables", "Conditionals", "Loops", "Functions", "Arrays", "Syntax", "OOP")
    
    avg_m, avg_u = compute_dashboard_metrics(masteries, uncertainties)
    assert 0.0 <= avg_m <= 1.0
    assert 0.0 <= avg_u <= 1.0
    
    state_sig = tuple((concepts[i], masteries[i], uncertainties[i]) for i in range(len(concepts)))
    rec_info = get_cached_recommendation_info(state_sig)
    assert "recommended_concept" in rec_info
    assert "priority_score" in rec_info
    assert "recommended_activity" in rec_info

def test_chart_builders():
    """Tests radar and bar chart builders returning Plotly Figures."""
    masteries = (0.85, 0.60, 0.40, 0.55, 0.40, 0.88, 0.30)
    uncertainties = (0.15, 0.30, 0.50, 0.25, 0.45, 0.10, 0.55)
    concepts = ("Variables", "Conditionals", "Loops", "Functions", "Arrays", "Syntax", "OOP")
    
    fig_radar = build_radar_chart(masteries, uncertainties, concepts)
    assert fig_radar is not None
    assert len(fig_radar.data) == 2  # Mastery and Uncertainty traces
    
    priorities_list = [
        {"concept": "Loops", "priority_score": 0.90},
        {"concept": "OOP", "priority_score": 0.85}
    ]
    priorities_tuples = tuple(tuple(item.items()) for item in priorities_list)
    fig_bar = build_priority_bar_chart(priorities_tuples)
    assert fig_bar is not None
    assert len(fig_bar.data) >= 1

def test_cached_evaluators():
    """Tests cached MCQ, SBERT, and Code analyzers."""
    # MCQ
    mcq_res = evaluate_mcq_cached("A", "A")
    assert mcq_res["is_correct"] is True
    assert mcq_res["evidence_score"] == 1.0
    
    # Short Answer
    sa_res = evaluate_short_answer_cached(
        student_response="Variables store data values in computer memory.",
        reference_answer="Variables store data values in computer memory."
    )
    assert sa_res["evidence_score"] > 0.8
    assert "similarity_percentage" in sa_res
    
    # Code
    code_str = "def add(a, b):\n    return a + b\n"
    test_cases_json = json.dumps([{"call": "add(1, 2)", "expected": 3, "description": "1+2=3"}])
    code_res = evaluate_code_cached(code_str, passed_tests=1, total_tests=1, test_cases_json=test_cases_json)
    assert code_res["evidence_score"] == 1.0
    assert code_res["is_compilable"] is True

def test_test_cases_formatter():
    """Tests code test cases formatting block."""
    tcs = [{"call": "f(1)", "expected": 2, "description": "test 1"}]
    formatted = format_test_cases_code_blocks(json.dumps(tcs))
    assert "assert f(1) == 2" in formatted
    assert "# Test 1: test 1" in formatted
