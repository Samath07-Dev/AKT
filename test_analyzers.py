"""
test_analyzers.py

Verification script for MCQAnalyzer, CodeAnalyzer, and ShortAnswerAnalyzer.
"""

from src.analyzers import MCQAnalyzer, CodeAnalyzer, ShortAnswerAnalyzer

def test_analyzers():
    print("=" * 60)
    print("         Verifying Interaction Analyzers         ")
    print("=" * 60)

    # 1. Test MCQAnalyzer
    mcq = MCQAnalyzer()
    res_mcq_correct = mcq.evaluate(student_option="B", correct_option="B")
    res_mcq_wrong = mcq.evaluate(student_option="A", correct_option="B")
    
    print("\n1. MCQ Analyzer Results:")
    print(f"  - Correct Selection Score: {res_mcq_correct['evidence_score']} (Expected: 1.0)")
    print(f"  - Incorrect Selection Score: {res_mcq_wrong['evidence_score']} (Expected: 0.0)")
    assert res_mcq_correct['evidence_score'] == 1.0
    assert res_mcq_wrong['evidence_score'] == 0.0

    # 2. Test CodeAnalyzer
    code_anal = CodeAnalyzer()
    valid_code = "def add(a, b):\n    return a + b\n"
    invalid_code = "def add(a, b\n    return a + b"
    
    res_code_valid = code_anal.evaluate(code_string=valid_code, passed_test_cases=8, total_test_cases=10)
    res_code_invalid = code_anal.evaluate(code_string=invalid_code, passed_test_cases=0, total_test_cases=10)
    
    print("\n2. Code Analyzer Results:")
    print(f"  - Valid Code Pass Fraction: {res_code_valid['pass_fraction']} (Expected: 0.8)")
    print(f"  - Invalid Code Pass Fraction: {res_code_invalid['pass_fraction']} (Expected: 0.0)")
    print(f"  - Syntax Error Info: {res_code_invalid['syntax_error']}")
    assert abs(res_code_valid['pass_fraction'] - 0.8) < 1e-5
    assert res_code_invalid['pass_fraction'] == 0.0

    # 3. Test ShortAnswerAnalyzer
    sa_anal = ShortAnswerAnalyzer(model_name="sentence-transformers/all-MiniLM-L6-v2")
    student_ans = "A variable is a container for storing data values in memory."
    ref_ans = "Variables store data values in computer memory."
    
    res_sa = sa_anal.evaluate(student_response=student_ans, reference_answer=ref_ans)
    
    print("\n3. Short Answer Analyzer Results:")
    print(f"  - Model Used: {res_sa['model_used']}")
    print(f"  - Cosine Similarity: {res_sa['cosine_similarity']:.4f}")
    print(f"  - Evidence Score: {res_sa['evidence_score']:.4f}")
    print(f"  - Feedback: {res_sa['feedback']}")
    
    # Verify score is strictly bounded in [0.0, 1.0]
    assert 0.0 <= res_sa['evidence_score'] <= 1.0
    assert res_sa['evidence_score'] > 0.6  # Semantic similarity should be high for matching conceptual definition

    print("\nAll 3 analyzers verified successfully with zero errors!")

if __name__ == "__main__":
    test_analyzers()
