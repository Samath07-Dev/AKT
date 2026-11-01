"""
test_api_kc_cycling.py

Verification script to test:
1. Complete overhauled structure of data/reference_answers.json:
   - 7 Python KCs (Variables, Conditionals, Loops, Functions, Arrays, Syntax, OOP)
   - 3 Difficulty levels ('easy', 'medium', 'hard') for every modality
   - Exactly 3 Easy MCQs, 3 Medium MCQs, 3 Hard MCQs per KC (9 MCQs each)
   - Exactly 1 Easy, 1 Medium, 1 Hard Short Answer per KC
   - Exactly 1 Easy, 1 Medium, 1 Hard Coding task per KC (with unit test cases)
2. MCQ unattempted cycling logic across difficulty levels
3. FastAPI endpoints: /api/v1/update_interaction, /api/v1/recommend, /api/v1/concept_bundle, /api/v1/evaluate_bundle
4. Difficulty scaffolding policy verification:
   - Evidence score < 0.5 routes to easier difficulty
   - Evidence score > 0.8 routes to harder difficulty
"""

import json
from fastapi.testclient import TestClient
from api import app, REFERENCE_ANSWERS, get_next_mcq_for_student, mark_mcq_attempted, student_concept_difficulty

client = TestClient(app)

def test_reference_answers_structure():
    print("=" * 60)
    print("      1. Verifying data/reference_answers.json Structure      ")
    print("=" * 60)
    
    expected_kcs = ["Variables", "Conditionals", "Loops", "Functions", "Arrays", "Syntax", "OOP"]
    difficulties = ["easy", "medium", "hard"]
    
    assert len(REFERENCE_ANSWERS) == 7, f"Expected 7 KCs, found {len(REFERENCE_ANSWERS)}"
    
    for kc in expected_kcs:
        assert kc in REFERENCE_ANSWERS, f"Missing KC: {kc}"
        kc_data = REFERENCE_ANSWERS[kc]
        
        # Check MCQs
        mcqs_data = kc_data.get("mcqs", {})
        assert isinstance(mcqs_data, dict), f"KC '{kc}' mcqs should be a dictionary of difficulty levels"
        for diff in difficulties:
            diff_mcqs = mcqs_data.get(diff, [])
            assert len(diff_mcqs) == 3, f"KC '{kc}' {diff} should have 3 MCQs, found {len(diff_mcqs)}"
            for m in diff_mcqs:
                assert "id" in m and "question" in m and "options" in m and "correct_option" in m
                assert len(m["options"]) == 4
        
        # Check Short Answer
        sa_data = kc_data.get("short_answer", {})
        assert isinstance(sa_data, dict), f"KC '{kc}' short_answer should be a dictionary of difficulty levels"
        for diff in difficulties:
            sa = sa_data.get(diff, {})
            assert "reference_answer" in sa and "question" in sa, f"KC '{kc}' {diff} missing short_answer details"
        
        # Check Coding Task
        code_data = kc_data.get("coding", {})
        assert isinstance(code_data, dict), f"KC '{kc}' coding should be a dictionary of difficulty levels"
        for diff in difficulties:
            code = code_data.get(diff, {})
            assert "problem" in code and "template" in code, f"KC '{kc}' {diff} missing coding details"
            test_cases = code.get("test_cases", [])
            assert len(test_cases) >= 1, f"KC '{kc}' {diff} coding task must have test cases"
        
        print(f"  ✓ KC '{kc}': 3 Easy/Med/Hard MCQs (9), 3 Short Answers, 3 Coding Tasks with test cases verified.")
    print("All 7 KCs verified successfully in reference_answers.json!\n")

def test_mcq_cycling():
    print("=" * 60)
    print("      2. Verifying Unattempted MCQ Cycling Logic      ")
    print("=" * 60)
    
    student_id = "S_TEST_CYCLE"
    kc = "Variables"
    diff = "easy"
    
    # 1st retrieval -> Easy MCQ 1
    mcq1 = get_next_mcq_for_student(student_id, kc, difficulty=diff)
    print(f"Attempt 1 ({diff}): {mcq1['id']}")
    assert mcq1['id'] == "Variables_MCQ_Easy_1"
    mark_mcq_attempted(student_id, kc, mcq1['id'], difficulty=diff)
    
    # 2nd retrieval -> Easy MCQ 2
    mcq2 = get_next_mcq_for_student(student_id, kc, difficulty=diff)
    print(f"Attempt 2 ({diff}): {mcq2['id']}")
    assert mcq2['id'] == "Variables_MCQ_Easy_2"
    mark_mcq_attempted(student_id, kc, mcq2['id'], difficulty=diff)
    
    # 3rd retrieval -> Easy MCQ 3
    mcq3 = get_next_mcq_for_student(student_id, kc, difficulty=diff)
    print(f"Attempt 3 ({diff}): {mcq3['id']}")
    assert mcq3['id'] == "Variables_MCQ_Easy_3"
    mark_mcq_attempted(student_id, kc, mcq3['id'], difficulty=diff)
    
    # 4th retrieval -> Should reset cycle back to Easy MCQ 1!
    mcq4 = get_next_mcq_for_student(student_id, kc, difficulty=diff)
    print(f"Attempt 4 (After Cycle Reset): {mcq4['id']}")
    assert mcq4['id'] == "Variables_MCQ_Easy_1"
    
    print("Unattempted MCQ cycling verified successfully!\n")

def test_api_endpoints_and_scaffolding():
    print("=" * 60)
    print("      3. Verifying FastAPI Endpoints & Difficulty Scaffolding      ")
    print("=" * 60)
    
    # Test Healthcheck
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert res_root.json()["total_kcs"] == 7
    assert "difficulties" in res_root.json()
    print(f"  ✓ Root endpoint healthcheck passed: {res_root.json()['system']}")
    
    # Test Concept Bundle endpoint with difficulty query parameter
    res_bundle = client.get("/api/v1/concept_bundle/Conditionals?difficulty=hard")
    assert res_bundle.status_code == 200
    bundle_data = res_bundle.json()
    assert bundle_data["difficulty"] == "hard"
    assert len(bundle_data["bundle"]["mcqs"]) == 3
    assert "test_cases" in bundle_data["bundle"]["coding"]
    print("  ✓ Concept bundle endpoint with difficulty filter verified.")

    # Test Short Answer via SBERT and Difficulty Scaffolding UP (> 0.8)
    student_id = "S_TEST_SCAFFOLD"
    student_concept_difficulty[student_id] = {"Variables": "easy"}
    
    sa_payload = {
        "student_id": student_id,
        "concept": "Variables",
        "activity_type": "Short Answer",
        "student_response": "A variable is a named container in computer memory used to store data values that can be referenced and modified throughout a program.",
        "difficulty": "easy"
    }
    res_sa = client.post("/api/v1/update_interaction", json=sa_payload)
    assert res_sa.status_code == 200
    sa_res = res_sa.json()
    print(f"  ✓ Short Answer SBERT Score: {sa_res['evidence_score']:.4f}")
    print(f"  ✓ Next Scaffolded Difficulty: {sa_res['next_recommended_difficulty']}")
    # High score > 0.8 should scaffold up from easy to medium!
    assert sa_res["evidence_score"] > 0.80
    assert sa_res["next_recommended_difficulty"] == "medium"
    assert "grading_details" in sa_res
    assert sa_res["grading_details"]["activity_type"] == "Short Answer"
    assert "similarity_percentage" in sa_res["grading_details"]
    assert "missing_keywords" in sa_res["grading_details"]

    # Test MCQ struggling score < 0.5 scaffolds DOWN (hard -> medium or medium -> easy)
    mcq_struggle_payload = {
        "student_id": student_id,
        "concept": "Variables",
        "activity_type": "MCQ",
        "student_response": "Z", # Incorrect option -> score 0.0
        "difficulty": "hard"
    }
    res_mcq = client.post("/api/v1/update_interaction", json=mcq_struggle_payload)
    assert res_mcq.status_code == 200
    mcq_res = res_mcq.json()
    print(f"  ✓ Struggle MCQ Evidence Score: {mcq_res['evidence_score']:.2f}")
    print(f"  ✓ Scaffolded Down Difficulty: {mcq_res['next_recommended_difficulty']}")
    # Score 0.0 < 0.5 scaffolds down from hard to medium
    assert mcq_res["evidence_score"] < 0.50
    assert mcq_res["next_recommended_difficulty"] == "medium"
    assert "grading_details" in mcq_res
    assert mcq_res["grading_details"]["is_correct"] is False
    assert "correct_option" in mcq_res["grading_details"]

    # Test Recommendation endpoint with difficulty scaffolding
    rec_payload = {
        "student_id": student_id,
        "target_concept_override": "Loops",
        "current_difficulty": "easy",
        "last_evidence_score": 0.95
    }
    res_rec = client.post("/api/v1/recommend", json=rec_payload)
    assert res_rec.status_code == 200
    rec_data = res_rec.json()
    print(f"  ✓ Recommended Concept: {rec_data['recommended_concept']}")
    print(f"  ✓ Recommended Difficulty: {rec_data['recommended_difficulty']} (Scaffolded up from easy to medium)")
    assert rec_data["recommended_difficulty"] == "medium"
    assert "question_details" in rec_data

    # Test 5-Question Bundle Assessment
    bundle_payload = {
        "student_id": student_id,
        "concept": "Functions",
        "difficulty": "medium",
        "mcq_responses": ["B", "C", "A"],
        "short_answer_response": "Functions break programs into modular reusable blocks of code.",
        "code_response": "def factorial(n):\n    result = 1\n    for i in range(2, n + 1):\n        result *= i\n    return result\n",
        "passed_test_cases": 10,
        "total_test_cases": 10
    }
    res_bundle_eval = client.post("/api/v1/evaluate_bundle", json=bundle_payload)
    assert res_bundle_eval.status_code == 200
    bundle_eval_data = res_bundle_eval.json()
    print(f"  ✓ Bundle Evaluation Average Score: {bundle_eval_data['bundle_average_score'] * 100:.1f}%")
    print(f"  ✓ Bundle Next Recommended Difficulty: {bundle_eval_data['next_recommended_difficulty']}")
    assert bundle_eval_data["bundle_average_score"] > 0.80
    assert bundle_eval_data["next_recommended_difficulty"] == "hard"
    
    # Verify Granular Grading Details in Bundle Response
    assert "grading_details" in bundle_eval_data
    gd = bundle_eval_data["grading_details"]
    assert "mcqs" in gd and len(gd["mcqs"]) == 3
    for mcq_d in gd["mcqs"]:
        assert "question_id" in mcq_d
        assert "is_correct" in mcq_d
        assert "correct_option" in mcq_d
    assert "short_answer" in gd
    assert "similarity_percentage" in gd["short_answer"]
    assert "missing_keywords" in gd["short_answer"]
    assert "coding" in gd
    assert "pass_fraction" in gd["coding"]
    assert "passed_test_cases" in gd["coding"]
    assert "syntax_valid" in gd["coding"]
    assert "syntax_error" in gd["coding"]
    print(f"  ✓ Granular Bundle Grading Details verified: 3 MCQs, SBERT SA ({gd['short_answer']['similarity_percentage']}%), Coding ({gd['coding']['pass_fraction']*100:.1f}%)")

    print("\nAll API endpoint & difficulty scaffolding tests passed cleanly with zero errors!")

def test_auth_registration_and_login_mongodb():
    """Verifies student registration, login, and historical score endpoints with MongoDB."""
    import uuid
    rand_suffix = uuid.uuid4().hex[:6]
    test_user = f"student_{rand_suffix}"
    test_pass = "mypassword123"

    # 1. Register new student
    reg_payload = {
        "username": test_user,
        "password": test_pass,
        "full_name": "Test User",
        "email": f"{test_user}@test.edu"
    }
    res_reg = client.post("/register", json=reg_payload)
    assert res_reg.status_code == 200
    reg_data = res_reg.json()
    assert reg_data["status"] == "success"
    assert "student_id" in reg_data
    student_id = reg_data["student_id"]
    print(f"  ✓ Student registered: {test_user} -> {student_id}")

    # 2. Duplicate registration rejection
    res_dup = client.post("/register", json=reg_payload)
    assert res_dup.status_code == 400

    # 3. Successful Login
    login_payload = {
        "username": test_user,
        "password": test_pass
    }
    res_login = client.post("/login", json=login_payload)
    assert res_login.status_code == 200
    login_data = res_login.json()
    assert login_data["status"] == "success"
    assert login_data["student_id"] == student_id
    print(f"  ✓ Student login verified: {login_data['username']}")

    # 4. Invalid Login rejection
    res_bad = client.post("/login", json={"username": test_user, "password": "wrongpassword"})
    assert res_bad.status_code == 401

    # 5. History and Score Recording
    score_payload = {
        "concept": "Conditionals",
        "difficulty": "medium",
        "bundle_average_score": 0.90,
        "mcq_scores": [1.0, 1.0, 1.0],
        "short_answer_score": 0.85,
        "code_score": 0.85,
        "next_difficulty": "hard",
        "scaffolding_reasoning": "Mastery threshold reached."
    }
    res_score = client.post(f"/api/v1/student/{student_id}/record_score", json=score_payload)
    assert res_score.status_code == 200

    res_hist = client.get(f"/api/v1/student/{student_id}/history")
    assert res_hist.status_code == 200
    hist_data = res_hist.json()
    assert len(hist_data["history"]) >= 1
    assert hist_data["history"][0]["concept"] == "Conditionals"
    print(f"  ✓ Student score history verified in MongoDB for {student_id}")

if __name__ == "__main__":
    test_reference_answers_structure()
    test_mcq_cycling()
    test_api_endpoints_and_scaffolding()
    test_auth_registration_and_login_mongodb()
