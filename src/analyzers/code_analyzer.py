"""
src/analyzers/code_analyzer.py

Code Submission Analyzer for Python Programming Tasks.
Performs safe AST syntax validation and code structural inspection.

SECURITY POLICY (Phase 7B-2):
Student-submitted Python code must NEVER execute inside the host process.
All execution paths (exec, eval, subprocess) are permanently disabled.
This restriction applies unconditionally regardless of environment variable settings.
"""

import ast
from typing import Dict, List, Any, Optional, Tuple


class CodeAnalyzer:
    """
    Analyzes student code submissions safely without host-process code execution.
    Inspects AST syntax properties and provides structural metrics.
    Host-process code execution is permanently disabled and quarantined.
    """
    def __init__(self):
        # Host execution is permanently quarantined; no environment variable can enable it
        self.host_execution_enabled = False

    def check_syntax(self, code_string: str) -> Tuple[bool, Optional[str]]:
        """
        Safely checks if Python code string compiles without syntax errors using ast.parse.
        Does not execute or evaluate the code string.
        """
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
        Permanently disabled: Host code execution is quarantined.
        Always returns zero executed and zero passed tests without invoking exec() or eval().
        """
        return "Host code execution is permanently disabled.", 0, 0, []

    def evaluate_test_cases(
        self,
        passed_test_cases: int,
        total_test_cases: int,
        is_compilable: bool = True
    ) -> float:
        """
        Calculates test-case pass fraction.
        When host execution is disabled, returns 0.0.
        """
        return 0.0

    def evaluate(
        self,
        code_string: str,
        passed_test_cases: int = 0,
        total_test_cases: int = 0,
        is_compilable: Optional[bool] = None,
        test_cases: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates code submission safely using AST syntax parsing only.
        Never executes student code or test cases in the host process.

        Parameters:
        - code_string: Raw Python code string submitted by student
        - passed_test_cases: Ignored (execution disabled)
        - total_test_cases: Ignored (execution disabled)
        - is_compilable: Optional boolean override (inferred from AST if None)
        - test_cases: Unit test case specifications (not executed)

        Returns:
        - Dict containing syntax validity, quarantined execution status, and structural metrics.
        """
        syntax_valid, syntax_error = self.check_syntax(code_string)
        compilable = syntax_valid if is_compilable is None else (bool(is_compilable) and syntax_valid)

        lines = code_string.splitlines() if code_string else []
        non_empty_lines = [line for line in lines if line.strip()]

        return {
            "evidence_score": 0.0,
            "pass_fraction": 0.0,
            "is_compilable": compilable,
            "syntax_valid": syntax_valid,
            "syntax_error": syntax_error,
            "runtime_error": "Host code execution is permanently disabled.",
            "passed_test_cases": 0,
            "total_test_cases": 0,
            "test_results": [],
            "execution_status": "DISABLED",
            "feedback": "Host code execution is permanently disabled. Tests not executed.",
            "num_lines": len(non_empty_lines)
        }
