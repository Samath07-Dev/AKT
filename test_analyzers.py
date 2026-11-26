"""
test_analyzers.py

Verification script for MCQAnalyzer, CodeAnalyzer, and ShortAnswerAnalyzer.
Includes Phase 7B-2 security regression tests verifying that host-process code
execution is permanently quarantined.
"""

import os
import builtins
import tempfile
from pathlib import Path
from src.analyzers import MCQAnalyzer, CodeAnalyzer, ShortAnswerAnalyzer


def test_analyzers():
    """Verifies baseline functionality across all three analyzers."""
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

    # 2. Test CodeAnalyzer (Quarantined)
    code_anal = CodeAnalyzer()
    valid_code = "def add(a, b):\n    return a + b\n"
    invalid_code = "def add(a, b\n    return a + b"

    res_code_valid = code_anal.evaluate(code_string=valid_code)
    res_code_invalid = code_anal.evaluate(code_string=invalid_code)

    print("\n2. Code Analyzer Results (Quarantined):")
    print(f"  - Valid Code Syntax Valid: {res_code_valid['syntax_valid']} (Expected: True)")
    print(f"  - Valid Code Passed Tests: {res_code_valid['passed_test_cases']} (Expected: 0)")
    print(f"  - Valid Code Pass Fraction: {res_code_valid['pass_fraction']} (Expected: 0.0)")
    print(f"  - Invalid Code Syntax Valid: {res_code_invalid['syntax_valid']} (Expected: False)")
    print(f"  - Invalid Code Syntax Error: {res_code_invalid['syntax_error']}")
    assert res_code_valid['syntax_valid'] is True
    assert res_code_valid['passed_test_cases'] == 0
    assert res_code_valid['total_test_cases'] == 0
    assert res_code_valid['pass_fraction'] == 0.0
    assert res_code_valid['evidence_score'] == 0.0

    assert res_code_invalid['syntax_valid'] is False
    assert res_code_invalid['syntax_error'] is not None
    assert res_code_invalid['pass_fraction'] == 0.0
    assert res_code_invalid['evidence_score'] == 0.0

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


def test_code_analyzer_sentinel_file_prevention():
    """Verifies that a student code payload attempting filesystem writes cannot execute."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        sentinel_path = Path(tmp_dir) / "sentinel_should_not_exist.txt"
        assert not sentinel_path.exists()

        # Code payload that would create the sentinel file if executed
        malicious_payload = (
            f"import pathlib\n"
            f"pathlib.Path({repr(str(sentinel_path))}).write_text('SECURITY_BREACH')\n"
        )

        code_anal = CodeAnalyzer()
        test_cases = [{"call": "dummy()", "expected": 1, "description": "test case"}]
        res = code_anal.evaluate(code_string=malicious_payload, test_cases=test_cases)

        # 1. Sentinel file must NOT have been created
        assert not sentinel_path.exists(), "CRITICAL: Sentinel file was created! Host execution occurred!"

        # 2. Syntax validation occurred safely without execution
        assert res["syntax_valid"] is True
        assert res["syntax_error"] is None

        # 3. Execution metrics must report zero
        assert res["passed_test_cases"] == 0
        assert res["total_test_cases"] == 0
        assert res["evidence_score"] == 0.0
        assert res["pass_fraction"] == 0.0
        assert res["execution_status"] == "DISABLED"


def test_code_analyzer_monkeypatched_exec_eval_not_called():
    """Verifies that neither builtins.exec nor builtins.eval is ever invoked."""
    orig_exec = builtins.exec
    orig_eval = builtins.eval

    exec_calls = []
    eval_calls = []

    def mock_exec(*args, **kwargs):
        exec_calls.append(args)
        raise RuntimeError("exec() was invoked during code analysis!")

    def mock_eval(*args, **kwargs):
        eval_calls.append(args)
        raise RuntimeError("eval() was invoked during code analysis!")

    code_anal = CodeAnalyzer()
    sample_code = "def multiply(x, y):\n    return x * y\n"
    test_cases = [{"call": "multiply(2, 3)", "expected": 6, "description": "multiply test"}]

    builtins.exec = mock_exec
    builtins.eval = mock_eval
    try:
        # Evaluate must run cleanly using AST without calling exec or eval
        res_eval = code_anal.evaluate(code_string=sample_code, test_cases=test_cases)
        err_msg, passed, total, results = code_anal.execute_test_cases(sample_code, test_cases)

        assert len(exec_calls) == 0, f"exec() was unexpectedly called {len(exec_calls)} times!"
        assert len(eval_calls) == 0, f"eval() was unexpectedly called {len(eval_calls)} times!"
        assert res_eval["passed_test_cases"] == 0
        assert res_eval["total_test_cases"] == 0
        assert res_eval["evidence_score"] == 0.0
        assert passed == 0
        assert total == 0
    finally:
        builtins.exec = orig_exec
        builtins.eval = orig_eval


def test_code_analyzer_syntax_parsing_isolated_from_execution():
    """Verifies that AST syntax parsing accurately catches errors while isolating execution."""
    code_anal = CodeAnalyzer()

    # Valid syntax
    res_valid = code_anal.evaluate("x = [i for i in range(10)]\n")
    assert res_valid["syntax_valid"] is True
    assert res_valid["syntax_error"] is None
    assert res_valid["is_compilable"] is True
    assert res_valid["passed_test_cases"] == 0
    assert res_valid["evidence_score"] == 0.0

    # Invalid syntax
    res_invalid = code_anal.evaluate("x = [i for i in range(10\n")
    assert res_invalid["syntax_valid"] is False
    assert res_invalid["syntax_error"] is not None
    assert "Syntax Error" in res_invalid["syntax_error"]
    assert res_invalid["is_compilable"] is False
    assert res_invalid["passed_test_cases"] == 0
    assert res_invalid["evidence_score"] == 0.0

    # Empty submission
    res_empty = code_anal.evaluate("")
    assert res_empty["syntax_valid"] is False
    assert res_empty["syntax_error"] == "Empty code submission."


def test_code_analyzer_zero_tests_executed_and_passed():
    """Verifies that disabled execution never reports fabricated passes or scores."""
    code_anal = CodeAnalyzer()

    # Even if caller passes synthetic counts, execution disabled must report 0
    res = code_anal.evaluate(
        code_string="def foo(): return 1\n",
        passed_test_cases=10,
        total_test_cases=10,
        test_cases=[{"call": "foo()", "expected": 1}]
    )

    assert res["passed_test_cases"] == 0
    assert res["total_test_cases"] == 0
    assert res["pass_fraction"] == 0.0
    assert res["evidence_score"] == 0.0
    assert res["test_results"] == []


def test_sandbox_offline_zero_cannot_reenable_execution():
    """Verifies that setting SANDBOX_OFFLINE=0 does not re-enable host execution."""
    old_env = os.environ.get("SANDBOX_OFFLINE")
    try:
        os.environ["SANDBOX_OFFLINE"] = "0"

        # Instantiate analyzer under SANDBOX_OFFLINE=0
        code_anal = CodeAnalyzer()
        assert code_anal.host_execution_enabled is False

        with tempfile.TemporaryDirectory() as tmp_dir:
            sentinel_path = Path(tmp_dir) / "sentinel_env_zero.txt"
            code_payload = f"import pathlib\npathlib.Path({repr(str(sentinel_path))}).write_text('FAIL')\n"

            res = code_anal.evaluate(code_string=code_payload, test_cases=[{"call": "test()", "expected": 1}])

            assert not sentinel_path.exists(), "Host execution occurred with SANDBOX_OFFLINE=0!"
            assert res["passed_test_cases"] == 0
            assert res["total_test_cases"] == 0
            assert res["evidence_score"] == 0.0
            assert res["execution_status"] == "DISABLED"
    finally:
        if old_env is not None:
            os.environ["SANDBOX_OFFLINE"] = old_env
        else:
            os.environ.pop("SANDBOX_OFFLINE", None)


def test_code_analyzer_bank_account_and_parse_key_values():
    """Verifies safe AST analysis for BankAccount and parse_key_values under SANDBOX_OFFLINE."""
    code_anal = CodeAnalyzer()

    bank_account_code = (
        "class BankAccount:\n"
        "    def __init__(self):\n"
        "        self.balance = 0\n"
        "    def deposit(self, amount):\n"
        "        if amount > 0:\n"
        "            self.balance += amount\n"
        "    def withdraw(self, amount):\n"
        "        if 0 < amount <= self.balance:\n"
        "            self.balance -= amount\n"
        "            return True\n"
        "        return False\n"
        "    def get_balance(self):\n"
        "        return self.balance\n"
    )

    parse_key_values_code = (
        "def parse_key_values(kv_str):\n"
        "    if not kv_str.strip():\n"
        "        return {}\n"
        "    result = {}\n"
        "    for pair in kv_str.split(';'):\n"
        "        if '=' in pair:\n"
        "            k, v = pair.split('=', 1)\n"
        "            result[k.strip()] = v.strip()\n"
        "    return result\n"
    )

    res_bank = code_anal.evaluate(code_string=bank_account_code)
    assert res_bank["syntax_valid"] is True
    assert res_bank["is_compilable"] is True
    assert res_bank["passed_test_cases"] == 0
    assert res_bank["execution_status"] == "DISABLED"
    assert res_bank["evidence_score"] == 0.0

    res_pkv = code_anal.evaluate(code_string=parse_key_values_code)
    assert res_pkv["syntax_valid"] is True
    assert res_pkv["is_compilable"] is True
    assert res_pkv["passed_test_cases"] == 0
    assert res_pkv["execution_status"] == "DISABLED"
    assert res_pkv["evidence_score"] == 0.0

    # Stubs & empty checks
    res_empty = code_anal.evaluate(code_string="")
    assert res_empty["syntax_valid"] is False
    assert res_empty["passed_test_cases"] == 0

    res_stub = code_anal.evaluate(code_string="class BankAccount:\n    pass\n")
    assert res_stub["syntax_valid"] is True
    assert res_stub["passed_test_cases"] == 0
    assert res_stub["execution_status"] == "DISABLED"


if __name__ == "__main__":
    test_analyzers()
    test_code_analyzer_sentinel_file_prevention()
    test_code_analyzer_monkeypatched_exec_eval_not_called()
    test_code_analyzer_syntax_parsing_isolated_from_execution()
    test_code_analyzer_zero_tests_executed_and_passed()
    test_sandbox_offline_zero_cannot_reenable_execution()
    test_code_analyzer_bank_account_and_parse_key_values()
    print("\n✓ ALL security regression and analyzer tests passed successfully!")
