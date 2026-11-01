"""
src/analyzers/code_analyzer.py

Code Submission Analyzer for Python Programming Tasks.
Evaluates test-case pass fractions, checks AST syntax validity, detects runtime errors,
and calculates code structural metrics for multi-response knowledge tracing.
"""

import ast
from typing import Dict, List, Any, Optional, Tuple

class CodeAnalyzer:
    """
    Analyzes student code submissions.
    Calculates exact test-case pass fraction [0.0, 1.0], checks AST syntax properties,
    and safely executes code in a sandboxed namespace to detect runtime errors.
    """
    def __init__(self):
        pass

    def check_syntax(self, code_string: str) -> Tuple[bool, Optional[str]]:
        """Checks if Python code string compiles without syntax errors."""
        if not code_string or not str(code_string).strip():
            return False, "Empty code submission."
        try:
            ast.parse(code_string)
            return True, None
        except SyntaxError as e:
            return False, f"Syntax Error: {e.msg} at line {e.lineno}"
        except Exception as e:
            return False, f"Parse Error: {str(e)}"

    def execute_test_cases(
        self,
        code_string: str,
        test_cases: List[Dict[str, Any]]
    ) -> Tuple[Optional[str], int, int, List[Dict[str, Any]]]:
        """
        Executes code safely in a local namespace against unit test cases to catch runtime errors
        and evaluate pass/fail per test case.
        """
        if not code_string or not str(code_string).strip():
            return "Empty code submission.", 0, len(test_cases) if test_cases else 0, []

        local_env = {"__builtins__": __builtins__}
        try:
            compiled = compile(code_string, "<student_code>", "exec")
            exec(compiled, local_env)
        except Exception as e:
            return f"{type(e).__name__}: {str(e)}", 0, len(test_cases) if test_cases else 0, []

        if not test_cases:
            return None, 0, 0, []

        passed = 0
        total = len(test_cases)
        first_runtime_error = None
        results = []

        for idx, tc in enumerate(test_cases):
            call_expr = tc.get("call", tc.get("input", ""))
            expected = tc.get("expected")
            desc = tc.get("description", "")
            try:
                actual = eval(call_expr, local_env)
                if actual == expected:
                    passed += 1
                    results.append({"test_index": idx + 1, "passed": True, "call": call_expr, "actual": actual, "expected": expected, "desc": desc})
                else:
                    if first_runtime_error is None:
                        first_runtime_error = f"Assertion Mismatch on '{call_expr}': produced {repr(actual)}, expected {repr(expected)}"
                    results.append({"test_index": idx + 1, "passed": False, "call": call_expr, "actual": actual, "expected": expected, "error": "Value mismatch", "desc": desc})
            except Exception as e:
                err_msg = f"{type(e).__name__} on '{call_expr}': {str(e)}"
                if first_runtime_error is None:
                    first_runtime_error = err_msg
                results.append({"test_index": idx + 1, "passed": False, "call": call_expr, "expected": expected, "error": err_msg, "desc": desc})

        return first_runtime_error, passed, total, results

    def evaluate_test_cases(
        self,
        passed_test_cases: int,
        total_test_cases: int,
        is_compilable: bool = True
    ) -> float:
        """
        Calculates test-case pass fraction:
        pass_fraction = passed_test_cases / total_test_cases
        Bounded strictly to [0.0, 1.0].
        """
        if not is_compilable or total_test_cases <= 0:
            return 0.0
        
        passed = max(0, int(passed_test_cases))
        total = max(1, int(total_test_cases))
        
        pass_fraction = float(passed) / float(total)
        return float(min(1.0, max(0.0, pass_fraction)))

    def evaluate(
        self,
        code_string: str,
        passed_test_cases: int = 0,
        total_test_cases: int = 0,
        is_compilable: Optional[bool] = None,
        test_cases: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates code submission and returns comprehensive evidence vector dictionary.
        
        Parameters:
        - code_string: Raw Python code string submitted by student
        - passed_test_cases: Count of unit test cases passed
        - total_test_cases: Total count of unit test cases executed
        - is_compilable: Optional boolean compilation status (inferred from AST if None)
        - test_cases: Optional list of unit test case dicts to execute directly
        
        Returns:
        - Dict containing 'evidence_score', syntax validity, runtime errors, and test metrics.
        """
        syntax_valid, syntax_error = self.check_syntax(code_string)
        runtime_error = None
        test_results = []

        if syntax_valid and test_cases:
            runtime_error, exec_passed, exec_total, test_results = self.execute_test_cases(code_string, test_cases)
            if passed_test_cases == 0 and total_test_cases == 0:
                passed_test_cases = exec_passed
                total_test_cases = exec_total
            elif exec_total > 0 and (passed_test_cases != exec_passed or total_test_cases != exec_total):
                passed_test_cases = exec_passed
                total_test_cases = exec_total
        elif syntax_valid and not test_cases:
            try:
                local_env = {"__builtins__": __builtins__}
                exec(compile(code_string, "<student_code>", "exec"), local_env)
            except Exception as e:
                runtime_error = f"{type(e).__name__}: {str(e)}"

        if is_compilable is None:
            compilable = syntax_valid
        else:
            compilable = bool(is_compilable) and syntax_valid

        # Compute test case pass fraction
        if total_test_cases > 0:
            evidence_score = self.evaluate_test_cases(passed_test_cases, total_test_cases, compilable and (runtime_error is None or passed_test_cases > 0))
        else:
            evidence_score = 1.0 if (compilable and not runtime_error) else 0.0

        lines = code_string.splitlines() if code_string else []
        non_empty_lines = [line for line in lines if line.strip()]

        return {
            "evidence_score": float(evidence_score),
            "pass_fraction": float(evidence_score),
            "is_compilable": compilable,
            "syntax_valid": syntax_valid,
            "syntax_error": syntax_error,
            "runtime_error": runtime_error,
            "passed_test_cases": passed_test_cases,
            "total_test_cases": total_test_cases,
            "test_results": test_results,
            "num_lines": len(non_empty_lines)
        }
