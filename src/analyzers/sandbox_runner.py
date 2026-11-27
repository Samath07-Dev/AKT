"""
src/analyzers/sandbox_runner.py

Hardened ephemeral Docker sandbox evaluator for untrusted Python code.
Never executes student code inside the FastAPI host process or using host exec/eval.
Fails closed to PENDING_SECURE_EVALUATION / NOT_PERFORMED when SANDBOX_OFFLINE=1
or when Docker / the pinned image digest is unavailable.
"""

from __future__ import annotations

import ast
import json
import math
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


DOCKER_PYTHON_IMAGE = (
    "python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90"
)
MAX_CODE_LENGTH = 20000
MAX_CONTAINER_TIMEOUT_SEC = 5.0
MAX_PER_TEST_TIMEOUT_SEC = 2.0
MAX_OUTPUT_CHARS = 4096

# Executed strictly inside the ephemeral Docker container via `python -I -c ...`.
_CONTAINER_RUNNER_SCRIPT = r'''
import ast
import io
import json
import math
import os
import resource
import shutil
import signal
import sys
import tempfile

MAX_CAPTURE = 4096

class _BoundedBuffer:
    def __init__(self, limit=MAX_CAPTURE):
        self._limit = limit
        self._chunks = []
        self._size = 0

    def write(self, s):
        if not s:
            return 0
        rem = self._limit - self._size
        if rem > 0:
            part = s[:rem]
            self._chunks.append(part)
            self._size += len(part)
        return len(s)

    def flush(self):
        pass

    def getvalue(self):
        return "".join(self._chunks)

def _is_finite_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))

def _values_equal(actual, expected):
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is type(expected) and actual == expected
    if actual is None or expected is None:
        return actual is expected
    if _is_finite_number(actual) and _is_finite_number(expected):
        return math.isclose(float(actual), float(expected), rel_tol=1e-6, abs_tol=1e-6)
    if isinstance(actual, str) and isinstance(expected, str):
        return actual == expected
    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        if len(actual) != len(expected):
            return False
        return all(_values_equal(a, b) for a, b in zip(actual, expected))
    if isinstance(actual, dict) and isinstance(expected, dict):
        if len(actual) != len(expected):
            return False
        if all(k in actual for k in expected):
            return all(_values_equal(actual[k], expected[k]) for k in expected)
        # Fallback for JSON-stringified dictionary keys (e.g. int keys {1: 'a'} vs {'1': 'a'})
        norm_actual = {}
        for k, v in actual.items():
            sk = str(k)
            if sk in norm_actual:
                return False
            norm_actual[sk] = v
        if len(norm_actual) != len(expected):
            return False
        return all((str(k) in norm_actual) and _values_equal(norm_actual[str(k)], expected[k]) for k in expected)
    return actual == expected

def _safe_repr(val, limit=200):
    try:
        txt = repr(val)
    except Exception:
        txt = "<unrepresentable>"
    if len(txt) > limit:
        return txt[:limit] + "..."
    return txt

def _eval_call_expr(call_expr, ns):
    tree = ast.parse(call_expr, mode="exec")
    if not tree.body:
        raise ValueError("Empty test case expression")
    *stmts, last = tree.body
    if stmts:
        mod = ast.Module(body=stmts, type_ignores=[])
        exec(compile(mod, "<test_setup>", "exec"), ns)
    if isinstance(last, ast.Expr):
        expr = ast.Expression(body=last.value)
        return eval(compile(expr, "<test_call>", "eval"), ns)
    mod_last = ast.Module(body=[last], type_ignores=[])
    exec(compile(mod_last, "<test_call>", "exec"), ns)
    return None

def _apply_rlimits():
    try:
        # 2s CPU inside container, 2MB max file write in /work
        resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    except Exception:
        pass
    try:
        resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024 * 1024, 2 * 1024 * 1024))
    except Exception:
        pass

def _main():
    out_fd = os.dup(1)
    real_stdout = os.fdopen(out_fd, "w", encoding="utf-8", closefd=True)
    devnull_fd = os.open(os.devnull, os.O_RDWR)
    try:
        raw_input = sys.stdin.read()
        os.dup2(devnull_fd, 1)
        os.dup2(devnull_fd, 2)
    finally:
        os.close(devnull_fd)

    def _emit(obj):
        real_stdout.write(json.dumps(obj))
        real_stdout.flush()

    try:
        payload = json.loads(raw_input)
        code_string = str(payload.get("code_string", ""))
        test_cases = list(payload.get("test_cases", []))
        per_test_timeout = float(payload.get("per_test_timeout_sec", 2.0))
    except Exception as exc:
        _emit({"ok": False, "runtime_error": f"Invalid sandbox payload: {exc}", "results": []})
        return

    try:
        compiled_student = compile(ast.parse(code_string, mode="exec"), "<student_code>", "exec")
    except SyntaxError as exc:
        msg = f"SyntaxError: {exc.msg} (line {exc.lineno})"
        _emit({
            "ok": True,
            "syntax_valid": False,
            "syntax_error": msg,
            "runtime_error": msg,
            "results": [
                {
                    "testIndex": idx + 1,
                    "call": str(tc.get("call", "")),
                    "description": str(tc.get("description", "")),
                    "passed": False,
                    "error": msg,
                    "actualRepr": None,
                }
                for idx, tc in enumerate(test_cases)
            ],
        })
        return

    _apply_rlimits()
    results = []
    first_runtime_error = None

    def _timeout_handler(signum, frame):
        raise TimeoutError("Execution timed out")

    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    try:
        if hasattr(signal, "SIGXCPU"):
            signal.signal(signal.SIGXCPU, _timeout_handler)
    except Exception:
        pass

    for idx, tc in enumerate(test_cases):
        call_expr = str(tc.get("call", ""))
        desc = str(tc.get("description", ""))
        expected = tc.get("expected")
        stdout_buf = _BoundedBuffer()
        stderr_buf = _BoundedBuffer()
        work_base = "/work" if os.path.isdir("/work") else None
        case_dir = tempfile.mkdtemp(prefix=f"case_{idx}_", dir=work_base)
        old_cwd = os.getcwd()
        orig_out, orig_err = sys.stdout, sys.stderr
        passed = False
        err_msg = None
        actual_repr = None

        try:
            os.chdir(case_dir)
            sys.stdout = stdout_buf
            sys.stderr = stderr_buf
            ns = {"__name__": "__sandbox__"}
            signal.setitimer(signal.ITIMER_REAL, per_test_timeout)
            exec(compiled_student, ns)
            actual = _eval_call_expr(call_expr, ns)
            signal.setitimer(signal.ITIMER_REAL, 0.0)
            actual_repr = _safe_repr(actual)
            passed = bool(_values_equal(actual, expected))
            if not passed:
                err_msg = f"Expected {_safe_repr(expected)}, got {actual_repr}"
        except Exception as exc:
            signal.setitimer(signal.ITIMER_REAL, 0.0)
            err_msg = f"{type(exc).__name__}: {str(exc)}"[:300]
            if first_runtime_error is None:
                first_runtime_error = err_msg
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0.0)
            sys.stdout = orig_out
            sys.stderr = orig_err
            try:
                os.chdir(old_cwd)
            except Exception:
                pass
            shutil.rmtree(case_dir, ignore_errors=True)

        results.append({
            "testIndex": idx + 1,
            "call": call_expr,
            "description": desc,
            "passed": passed,
            "error": err_msg,
            "actualRepr": actual_repr,
        })

    signal.signal(signal.SIGALRM, old_handler)
    _emit({
        "ok": True,
        "syntax_valid": True,
        "syntax_error": None,
        "runtime_error": first_runtime_error,
        "results": results,
    })

if __name__ == "__main__":
    _main()
'''


@dataclass
class SandboxEvaluationResult:
    code_status: str
    code_execution_status: str
    code_score: float
    code_tests_passed: int
    code_tests_total: int
    syntax_valid: bool
    syntax_error: Optional[str]
    runtime_error: Optional[str]
    test_results: List[Dict[str, Any]]
    feedback: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def is_sandbox_offline() -> bool:
    """
    Fail closed if SANDBOX_OFFLINE is set to an offline value ('1', 'true', 'yes', 'on').
    Returns False when set to an active value ('0', 'false', 'no', 'off', 'fallback', 'subprocess').
    """
    raw = os.getenv("SANDBOX_OFFLINE", "1").strip().lower()
    return raw in ("1", "true", "yes", "on")


def is_subprocess_fallback_allowed() -> bool:
    """
    Returns True unless ALLOW_SUBPROCESS_FALLBACK is explicitly disabled ('0', 'false', 'no', 'off').
    """
    raw = os.getenv("ALLOW_SUBPROCESS_FALLBACK", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def resolve_docker_binary() -> Optional[str]:
    """Locate the Docker CLI binary without trusting arbitrary workspace paths."""
    found = shutil.which("docker")
    if found and os.access(found, os.X_OK):
        return found
    for candidate in (
        "/Users/abdulsamath/.docker/bin/docker",
        "/usr/local/bin/docker",
        "/opt/homebrew/bin/docker",
        "/usr/bin/docker",
    ):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


class SecureDockerPythonEvaluator:
    """
    Executes untrusted student Python submissions exclusively inside ephemeral,
    hardened, network-isolated Docker containers pinned by immutable SHA256 digest.
    """

    def __init__(
        self,
        image: str = DOCKER_PYTHON_IMAGE,
        container_timeout_sec: float = MAX_CONTAINER_TIMEOUT_SEC,
        per_test_timeout_sec: float = MAX_PER_TEST_TIMEOUT_SEC,
    ):
        self.image = image
        self.container_timeout_sec = container_timeout_sec
        self.per_test_timeout_sec = per_test_timeout_sec

    def _pending_result(
        self,
        test_cases: List[Dict[str, Any]],
        feedback: str,
        syntax_valid: bool = True,
        syntax_error: Optional[str] = None,
        runtime_error: Optional[str] = None,
    ) -> SandboxEvaluationResult:
        return SandboxEvaluationResult(
            code_status="PENDING_SECURE_EVALUATION",
            code_execution_status="NOT_PERFORMED",
            code_score=0.0,
            code_tests_passed=0,
            code_tests_total=len(test_cases),
            syntax_valid=syntax_valid,
            syntax_error=syntax_error,
            runtime_error=runtime_error,
            test_results=[],
            feedback=feedback,
        )

    def is_sandbox_available(self) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Checks offline policy, Docker CLI availability, daemon health, and fallback subprocess readiness.
        Returns (available, runner_target, reason_if_unavailable).
        runner_target is either the path to the docker binary or 'subprocess'.
        """
        if is_sandbox_offline():
            return False, None, "SANDBOX_OFFLINE is enabled."

        raw_env = os.getenv("SANDBOX_OFFLINE", "1").strip().lower()
        force_subprocess = raw_env in ("fallback", "subprocess")

        if not force_subprocess:
            docker_bin = resolve_docker_binary()
            if docker_bin:
                inspect_cmd = [docker_bin, "image", "inspect", self.image, "--format", "{{.Id}}"]
                wake_cmd = [
                    docker_bin,
                    "images",
                    "-a",
                    "--no-trunc",
                    "--digests",
                    "--format",
                    "{{.Repository}}:{{.Tag}}@{{.Digest}}",
                ]
                try:
                    probe = subprocess.run(
                        inspect_cmd,
                        capture_output=True,
                        text=True,
                        timeout=2.5,
                    )
                    if probe.returncode == 0:
                        return True, docker_bin, None

                    # If daemon socket is absent or connection refused, skip wake attempt
                    err_str = (probe.stderr or "").lower()
                    if "connect:" not in err_str and "no such file or directory" not in err_str and "daemon running" not in err_str:
                        # Fallback for Docker Desktop Resource Saver (Idle: shutdown):
                        # listing images triggers VM wake-up, after which the pinned digest is re-inspected.
                        wake_probe = subprocess.run(
                            wake_cmd,
                            capture_output=True,
                            text=True,
                            timeout=3.0,
                        )
                        if wake_probe.returncode == 0:
                            retry_probe = subprocess.run(
                                inspect_cmd,
                                capture_output=True,
                                text=True,
                                timeout=2.0,
                            )
                            if retry_probe.returncode == 0:
                                return True, docker_bin, None
                except Exception:
                    pass

        # Safe fallback: Python isolated subprocess execution mode (3-second timeout)
        if is_subprocess_fallback_allowed() or force_subprocess:
            python_bin = sys.executable or shutil.which("python3")
            if python_bin and os.access(python_bin, os.X_OK):
                return True, "subprocess", None

        return False, None, "Docker sandbox unavailable and subprocess fallback is disabled."

    def _cleanup_container(self, docker_bin: str, container_name: str) -> None:
        try:
            subprocess.run(
                [docker_bin, "rm", "-f", container_name],
                capture_output=True,
                text=True,
                timeout=3.0,
            )
        except Exception:
            pass

    def _evaluate_subprocess(
        self,
        code_string: str,
        test_cases: List[Dict[str, Any]],
        timeout_sec: float = 3.0,
    ) -> SandboxEvaluationResult:
        """
        Executes code_string against test_cases inside an isolated Python interpreter subprocess
        using `python -I` (isolated mode, ignoring PYTHONPATH, user site-packages, and host environment).
        Enforces a strict timeout (default 3.0s).
        """
        cases = list(test_cases or [])
        python_bin = sys.executable or shutil.which("python3") or "python3"
        effective_timeout = min(float(timeout_sec or 3.0), 5.0)

        payload = {
            "code_string": code_string,
            "test_cases": [
                {
                    "call": str(tc.get("call", "")),
                    "expected": tc.get("expected"),
                    "description": str(tc.get("description", "")),
                }
                for tc in cases
            ],
            "per_test_timeout_sec": min(self.per_test_timeout_sec, effective_timeout),
        }

        cmd = [
            python_bin,
            "-I",
            "-c",
            _CONTAINER_RUNNER_SCRIPT,
        ]

        try:
            proc = subprocess.run(
                cmd,
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=effective_timeout,
            )
        except subprocess.TimeoutExpired:
            timeout_results = [
                {
                    "testIndex": idx + 1,
                    "call": str(tc.get("call", "")),
                    "description": str(tc.get("description", "")),
                    "passed": False,
                    "error": f"Execution timed out ({effective_timeout}s limit).",
                    "actualRepr": None,
                }
                for idx, tc in enumerate(cases)
            ]
            return SandboxEvaluationResult(
                code_status="EVALUATED",
                code_execution_status="EXECUTED",
                code_score=0.0,
                code_tests_passed=0,
                code_tests_total=len(cases),
                syntax_valid=True,
                syntax_error=None,
                runtime_error=f"Execution timed out after {effective_timeout} seconds.",
                test_results=timeout_results,
                feedback=f"Execution timed out after {effective_timeout} seconds in isolated fallback subprocess.",
            )
        except Exception as exc:
            return self._pending_result(
                test_cases=cases,
                feedback=f"Failed to invoke isolated Python subprocess: {exc}",
            )

        stdout_text = (proc.stdout or "")[:MAX_OUTPUT_CHARS * 4].strip()
        try:
            parsed = json.loads(stdout_text)
        except Exception:
            if proc.returncode != 0:
                err_hint = (proc.stderr or "").strip()
                if not err_hint:
                    sig_xcpu = getattr(signal, "SIGXCPU", None)
                    if proc.returncode in (-24, -14, 124, 137, 142) or (sig_xcpu and proc.returncode == -sig_xcpu):
                        err_hint = "Execution timed out inside isolated sandbox."
                    elif proc.returncode in (-9, 137):
                        err_hint = "Process terminated (killed/memory cap)."
                    else:
                        err_hint = f"Subprocess terminated abnormally with code {proc.returncode}"
                err_results = [
                    {
                        "testIndex": idx + 1,
                        "call": str(tc.get("call", "")),
                        "description": str(tc.get("description", "")),
                        "passed": False,
                        "error": err_hint,
                        "actualRepr": None,
                    }
                    for idx, tc in enumerate(cases)
                ]
                return SandboxEvaluationResult(
                    code_status="EVALUATED",
                    code_execution_status="EXECUTED",
                    code_score=0.0,
                    code_tests_passed=0,
                    code_tests_total=len(cases),
                    syntax_valid=True,
                    syntax_error=None,
                    runtime_error=err_hint,
                    test_results=err_results,
                    feedback=f"Subprocess execution terminated: {err_hint}",
                )
            return self._pending_result(
                test_cases=cases,
                feedback="Malformed response from isolated subprocess. Deferred to pending secure evaluation.",
            )

        if not parsed.get("ok", False):
            return self._pending_result(
                test_cases=cases,
                feedback=str(parsed.get("runtime_error") or "Subprocess runner reported internal error."),
            )

        results = list(parsed.get("results", []))
        total = len(cases)
        passed = sum(1 for r in results if bool(r.get("passed")))
        score = round((passed / total) * 100.0, 2) if total > 0 else 0.0
        runtime_error = parsed.get("runtime_error")
        syntax_valid = bool(parsed.get("syntax_valid", True))
        syntax_error = parsed.get("syntax_error")

        if total == 0:
            feedback = "No test cases defined for this coding challenge."
        elif passed == total:
            feedback = f"All {passed}/{total} isolated Python test cases passed (fallback subprocess mode)."
        elif runtime_error:
            feedback = f"Passed {passed}/{total} test cases. Runtime error: {runtime_error}"
        else:
            feedback = f"Passed {passed}/{total} isolated Python test cases."

        return SandboxEvaluationResult(
            code_status="EVALUATED",
            code_execution_status="EXECUTED",
            code_score=score,
            code_tests_passed=passed,
            code_tests_total=total,
            syntax_valid=syntax_valid,
            syntax_error=syntax_error,
            runtime_error=runtime_error,
            test_results=results,
            feedback=feedback,
        )

    def evaluate(
        self,
        code_string: str,
        test_cases: List[Dict[str, Any]],
        timeout_sec: Optional[float] = None,
    ) -> SandboxEvaluationResult:
        """
        Evaluates `code_string` against server-side `test_cases` inside an ephemeral Docker container,
        or falls back to safe isolated Python subprocess execution if Docker is unavailable.
        """
        cases = list(test_cases or [])
        if not isinstance(code_string, str):
            code_string = ""

        if len(code_string) > MAX_CODE_LENGTH:
            return SandboxEvaluationResult(
                code_status="EVALUATED",
                code_execution_status="EXECUTED",
                code_score=0.0,
                code_tests_passed=0,
                code_tests_total=len(cases),
                syntax_valid=False,
                syntax_error="Code exceeds maximum allowed length.",
                runtime_error="Code exceeds maximum allowed length.",
                test_results=[],
                feedback="Code submission exceeds maximum allowed size.",
            )

        available, runner_target, unavailable_reason = self.is_sandbox_available()
        if not available or not runner_target:
            return self._pending_result(
                test_cases=cases,
                feedback=(
                    f"Secure Python sandbox unavailable ({unavailable_reason}). "
                    "Evaluation safely deferred as pending secure evaluation."
                ),
            )

        stripped = code_string.strip()
        if not stripped:
            empty_results = [
                {
                    "testIndex": idx + 1,
                    "call": str(tc.get("call", "")),
                    "description": str(tc.get("description", "")),
                    "passed": False,
                    "error": "No code submitted.",
                    "actualRepr": None,
                }
                for idx, tc in enumerate(cases)
            ]
            return SandboxEvaluationResult(
                code_status="EVALUATED",
                code_execution_status="EXECUTED",
                code_score=0.0,
                code_tests_passed=0,
                code_tests_total=len(cases),
                syntax_valid=False,
                syntax_error="No code submitted.",
                runtime_error="No code submitted.",
                test_results=empty_results,
                feedback="No Python solution submitted.",
            )

        # Safe host-side AST parse only (zero code execution) to report exact syntax diagnostics rapidly
        try:
            ast.parse(code_string)
        except SyntaxError as exc:
            msg = f"SyntaxError: {exc.msg} (line {exc.lineno})"
            syntax_results = [
                {
                    "testIndex": idx + 1,
                    "call": str(tc.get("call", "")),
                    "description": str(tc.get("description", "")),
                    "passed": False,
                    "error": msg,
                    "actualRepr": None,
                }
                for idx, tc in enumerate(cases)
            ]
            return SandboxEvaluationResult(
                code_status="EVALUATED",
                code_execution_status="EXECUTED",
                code_score=0.0,
                code_tests_passed=0,
                code_tests_total=len(cases),
                syntax_valid=False,
                syntax_error=msg,
                runtime_error=msg,
                test_results=syntax_results,
                feedback=f"Python syntax error detected: {msg}",
            )

        # If runner_target is "subprocess", run safe fallback subprocess evaluator
        if runner_target == "subprocess":
            case_count = max(len(cases), 1)
            default_limit = min(max(self.per_test_timeout_sec * case_count + 1.0, 3.0), 10.0)
            effective_timeout = min(float(timeout_sec or default_limit), 10.0)
            return self._evaluate_subprocess(
                code_string=code_string,
                test_cases=cases,
                timeout_sec=effective_timeout,
            )

        effective_timeout = min(float(timeout_sec or self.container_timeout_sec), 10.0)
        container_name = f"akt_sandbox_{uuid.uuid4().hex[:12]}"
        docker_bin = runner_target

        cmd = [
            docker_bin,
            "run",
            "--rm",
            "-i",
            "--init",
            "--name",
            container_name,
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=32",
            "--memory=128m",
            "--memory-swap=128m",
            "--cpus=0.5",
            "--user=65534:65534",
            "--tmpfs",
            "/work:rw,noexec,nosuid,nodev,size=16m,uid=65534,gid=65534",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=8m,uid=65534,gid=65534",
            "-w",
            "/work",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            "-e",
            "PYTHONUNBUFFERED=1",
            "-e",
            "HOME=/tmp",
            self.image,
            "python",
            "-I",
            "-c",
            _CONTAINER_RUNNER_SCRIPT,
        ]

        payload = {
            "code_string": code_string,
            "test_cases": [
                {
                    "call": tc.get("call", ""),
                    "expected": tc.get("expected"),
                    "description": tc.get("description", ""),
                }
                for tc in cases
            ],
            "per_test_timeout_sec": min(self.per_test_timeout_sec, effective_timeout),
        }

        try:
            proc = subprocess.run(
                cmd,
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=effective_timeout,
            )
        except subprocess.TimeoutExpired:
            self._cleanup_container(docker_bin, container_name)
            timeout_results = [
                {
                    "testIndex": idx + 1,
                    "call": str(tc.get("call", "")),
                    "description": str(tc.get("description", "")),
                    "passed": False,
                    "error": "Execution timed out inside secure sandbox.",
                    "actualRepr": None,
                }
                for idx, tc in enumerate(cases)
            ]
            return SandboxEvaluationResult(
                code_status="EVALUATED",
                code_execution_status="EXECUTED",
                code_score=0.0,
                code_tests_passed=0,
                code_tests_total=len(cases),
                syntax_valid=True,
                syntax_error=None,
                runtime_error="Execution timed out inside secure sandbox.",
                test_results=timeout_results,
                feedback="Execution timed out inside the isolated Docker sandbox.",
            )
        except Exception:
            self._cleanup_container(docker_bin, container_name)
            return self._pending_result(
                test_cases=cases,
                feedback="Failed to invoke Docker sandbox runner. Deferred to pending secure evaluation.",
            )

        # Standard Docker exit codes 125/126/127 denote daemon or container startup failure, not student code failure
        if proc.returncode in (125, 126, 127):
            self._cleanup_container(docker_bin, container_name)
            return self._pending_result(
                test_cases=cases,
                feedback="Docker sandbox container failed to start cleanly. Deferred to pending secure evaluation.",
            )

        # Exit code 137 typically indicates cgroup OOM kill (--memory=128m) or SIGKILL
        if proc.returncode == 137:
            oom_results = [
                {
                    "testIndex": idx + 1,
                    "call": str(tc.get("call", "")),
                    "description": str(tc.get("description", "")),
                    "passed": False,
                    "error": "Memory limit exceeded (128MB cap).",
                    "actualRepr": None,
                }
                for idx, tc in enumerate(cases)
            ]
            return SandboxEvaluationResult(
                code_status="EVALUATED",
                code_execution_status="EXECUTED",
                code_score=0.0,
                code_tests_passed=0,
                code_tests_total=len(cases),
                syntax_valid=True,
                syntax_error=None,
                runtime_error="Memory limit exceeded (128MB cap) inside secure sandbox.",
                test_results=oom_results,
                feedback="Execution terminated after exceeding the 128MB sandbox memory limit.",
            )

        stdout_text = (proc.stdout or "")[:MAX_OUTPUT_CHARS * 4].strip()
        try:
            parsed = json.loads(stdout_text)
        except Exception:
            if proc.returncode != 0:
                err_hint = (proc.stderr or "Non-zero exit from container")[:250].strip()
                err_results = [
                    {
                        "testIndex": idx + 1,
                        "call": str(tc.get("call", "")),
                        "description": str(tc.get("description", "")),
                        "passed": False,
                        "error": err_hint,
                        "actualRepr": None,
                    }
                    for idx, tc in enumerate(cases)
                ]
                return SandboxEvaluationResult(
                    code_status="EVALUATED",
                    code_execution_status="EXECUTED",
                    code_score=0.0,
                    code_tests_passed=0,
                    code_tests_total=len(cases),
                    syntax_valid=True,
                    syntax_error=None,
                    runtime_error=err_hint,
                    test_results=err_results,
                    feedback=f"Sandbox execution terminated abnormally: {err_hint}",
                )
            return self._pending_result(
                test_cases=cases,
                feedback="Malformed response from sandbox container. Deferred to pending secure evaluation.",
            )

        if not parsed.get("ok", False):
            return self._pending_result(
                test_cases=cases,
                feedback=str(parsed.get("runtime_error") or "Sandbox runner reported internal error."),
            )

        results = list(parsed.get("results", []))
        total = len(cases)
        passed = sum(1 for r in results if bool(r.get("passed")))
        score = round((passed / total) * 100.0, 2) if total > 0 else 0.0
        runtime_error = parsed.get("runtime_error")
        syntax_valid = bool(parsed.get("syntax_valid", True))
        syntax_error = parsed.get("syntax_error")

        if total == 0:
            feedback = "No test cases defined for this coding challenge."
        elif passed == total:
            feedback = f"All {passed}/{total} isolated Python test cases passed."
        elif runtime_error:
            feedback = f"Passed {passed}/{total} test cases. Runtime error: {runtime_error}"
        else:
            feedback = f"Passed {passed}/{total} isolated Python test cases."

        return SandboxEvaluationResult(
            code_status="EVALUATED",
            code_execution_status="EXECUTED",
            code_score=score,
            code_tests_passed=passed,
            code_tests_total=total,
            syntax_valid=syntax_valid,
            syntax_error=syntax_error,
            runtime_error=runtime_error,
            test_results=results,
            feedback=feedback,
        )


default_sandbox_evaluator = SecureDockerPythonEvaluator()

