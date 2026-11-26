/**
 * frontend/test_practice_sandbox_status.mjs
 *
 * Regression tests for Practice Arena live sandbox status detection,
 * syntax-preview vs Docker-execution separation, and fail-closed behavior.
 */

import jiti from "jiti";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

const j = jiti(import.meta.url, {
  alias: {
    "@": fileURLToPath(new URL("./src", import.meta.url)),
  },
});

const { getPracticeSandboxPresentation } = j("./src/lib/practice-sandbox-ui.ts");
const {
  probeDockerSandboxAvailability,
  evaluatePracticeCodeStateless,
} = j("./src/lib/server/sandbox-status.ts");

console.log("============================================================");
console.log("     Practice Arena Sandbox Status & UI State Tests         ");
console.log("============================================================");

let passedCount = 0;

async function runTest(name, fn) {
  try {
    await fn();
    console.log(`✓ PASS: ${name}`);
    passedCount++;
  } catch (err) {
    console.error(`✗ FAIL: ${name}`);
    console.error(err);
    process.exitCode = 1;
  }
}

await runTest("1. Checking state fails closed (no Docker Ready or Executed labels)", () => {
  const p = getPracticeSandboxPresentation({
    sandboxStatus: "checking",
    resultMode: "none",
    isSubmitted: false,
    testsPassed: 0,
    testsTotal: 3,
  });
  assert.equal(p.badgeLabel, "Checking Sandbox...");
  assert.equal(p.canRunDockerTests, false);
  assert.equal(p.panelTitle, "Checking Docker Sandbox Status");
});

await runTest("2. Offline state shows Sandbox Offline (Preview Only) and disables Docker button", () => {
  const p = getPracticeSandboxPresentation({
    sandboxStatus: "offline",
    resultMode: "none",
    isSubmitted: false,
    testsPassed: 0,
    testsTotal: 3,
  });
  assert.equal(p.badgeLabel, "Sandbox Offline (Preview Only)");
  assert.equal(p.badgeVariant, "warning");
  assert.equal(p.canRunDockerTests, false);
  assert.equal(p.panelTitle, "Syntax & Formatting Check (Sandbox Offline)");
});

await runTest("3. Available state enables Docker Sandbox Ready and Run Tests button", () => {
  const p = getPracticeSandboxPresentation({
    sandboxStatus: "available",
    resultMode: "none",
    isSubmitted: false,
    testsPassed: 0,
    testsTotal: 3,
  });
  assert.equal(p.badgeLabel, "Docker Sandbox Ready");
  assert.equal(p.badgeVariant, "success");
  assert.equal(p.canRunDockerTests, true);
  assert.equal(p.panelTitle, "Docker Sandbox Test Specifications");
});

await runTest("4. Syntax preview stays distinct from live Docker execution even when Docker is ready", () => {
  const p = getPracticeSandboxPresentation({
    sandboxStatus: "available",
    resultMode: "syntax_preview",
    isSubmitted: false,
    testsPassed: 3,
    testsTotal: 3,
    codeScore: null,
  });
  assert.equal(p.panelTitle, "Syntax & Structure Preview (Not Executed)");
  assert.match(p.panelNotice, /NOT been executed in Docker yet/);
  assert.equal(p.counterLabel, "Preview: 3 / 3 (Syntax Preview Only)");
});

await runTest("5. Docker executed mode displays real passed/total tests and codeScore%", () => {
  const p = getPracticeSandboxPresentation({
    sandboxStatus: "available",
    resultMode: "docker_executed",
    isSubmitted: true,
    testsPassed: 2,
    testsTotal: 3,
    codeScore: 66.67,
  });
  assert.equal(p.panelTitle, "Isolated Docker Sandbox Results");
  assert.equal(p.counterLabel, "Passed: 2 / 3 (Docker Sandbox) · 66.7%");
  assert.equal(p.canRunDockerTests, false);
});

await runTest("6. Pending offline submission displays fail-closed Pending Secure Evaluation notice", () => {
  const p = getPracticeSandboxPresentation({
    sandboxStatus: "offline",
    resultMode: "pending_offline",
    isSubmitted: true,
    testsPassed: 0,
    testsTotal: 3,
  });
  assert.equal(p.panelTitle, "Python Execution Pending (Sandbox Offline)");
  assert.equal(p.counterLabel, "Execution: Not Performed (Pending Secure Evaluation)");
});

await runTest("7. probeDockerSandboxAvailability & evaluatePracticeCodeStateless contract", async () => {
  const origFetch = globalThis.fetch;
  const origSecret = process.env.INTERNAL_SERVICE_SECRET;
  const origUrl = process.env.FASTAPI_BACKEND_URL;

  process.env.INTERNAL_SERVICE_SECRET = "test-internal-service-secret-at-least-32-chars";
  process.env.FASTAPI_BACKEND_URL = "http://127.0.0.1:8001";

  try {
    // a) Backend confirms Docker sandbox available
    globalThis.fetch = async (url, init) => {
      assert.ok(String(url).endsWith("/api/v1/evaluate_code"));
      assert.equal(init.method, "POST");
      const hdrs = new Headers(init.headers);
      assert.equal(hdrs.get("X-Internal-Service-Secret"), process.env.INTERNAL_SERVICE_SECRET);
      return new Response(
        JSON.stringify({
          code_status: "EVALUATED",
          code_execution_status: "EXECUTED",
          code_score: 0,
          code_tests_passed: 0,
          code_tests_total: 3,
          syntax_valid: false,
          test_results: [],
          feedback: "No Python solution submitted.",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };
    const ready = await probeDockerSandboxAvailability();
    assert.deepEqual(ready, {
      available: true,
      status: "READY",
      message: "Isolated Docker Python sandbox verified and ready.",
    });

    // b) Backend reports SANDBOX_OFFLINE / PENDING_SECURE_EVALUATION -> fails closed
    globalThis.fetch = async () =>
      new Response(
        JSON.stringify({
          code_status: "PENDING_SECURE_EVALUATION",
          code_execution_status: "NOT_PERFORMED",
          code_score: 0,
          code_tests_passed: 0,
          code_tests_total: 3,
          syntax_valid: true,
          test_results: [],
          feedback: "Secure Python sandbox unavailable (SANDBOX_OFFLINE is enabled.).",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    const offline = await probeDockerSandboxAvailability();
    assert.equal(offline.available, false);
    assert.equal(offline.status, "SANDBOX_OFFLINE");

    // c) Backend unreachable -> fails closed without throwing
    globalThis.fetch = async () => {
      throw new Error("ECONNREFUSED");
    };
    const networkErr = await probeDockerSandboxAvailability();
    assert.equal(networkErr.available, false);
    assert.equal(networkErr.status, "SANDBOX_OFFLINE");

    const evalFailClosed = await evaluatePracticeCodeStateless(
      "Variables",
      "easy",
      "def sum_two_numbers(a, b): return a + b"
    );
    assert.equal(evalFailClosed.codeStatus, "PENDING_SECURE_EVALUATION");
    assert.equal(evalFailClosed.codeExecutionStatus, "NOT_PERFORMED");
    assert.equal(evalFailClosed.codeScore, 0);
    assert.equal(evalFailClosed.codeTestsPassed, 0);

    // d) Stateless code evaluation forwards results faithfully
    globalThis.fetch = async (url, init) => {
      assert.ok(String(url).endsWith("/api/v1/evaluate_code"));
      const parsed = JSON.parse(init.body);
      assert.equal(parsed.concept, "Variables");
      assert.equal(parsed.difficulty, "easy");
      return new Response(
        JSON.stringify({
          code_status: "EVALUATED",
          code_execution_status: "EXECUTED",
          code_score: 100.0,
          code_tests_passed: 3,
          code_tests_total: 3,
          syntax_valid: true,
          runtime_error: null,
          test_results: [
            { testIndex: 1, call: "sum_two_numbers(2, 3)", description: "d1", passed: true },
            { testIndex: 2, call: "sum_two_numbers(-1, 1)", description: "d2", passed: true },
            { testIndex: 3, call: "sum_two_numbers(0, 0)", description: "d3", passed: true },
          ],
          feedback: "All 3/3 isolated Python test cases passed.",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };
    const evalOk = await evaluatePracticeCodeStateless(
      "Variables",
      "easy",
      "def sum_two_numbers(a, b):\n    return a + b\n"
    );
    assert.equal(evalOk.codeStatus, "EVALUATED");
    assert.equal(evalOk.codeExecutionStatus, "EXECUTED");
    assert.equal(evalOk.codeScore, 100);
    assert.equal(evalOk.codeTestsPassed, 3);
    assert.equal(evalOk.codeTotalTests, 3);
    assert.equal(evalOk.codeTestResults.length, 3);
  } finally {
    globalThis.fetch = origFetch;
    if (origSecret === undefined) delete process.env.INTERNAL_SERVICE_SECRET;
    else process.env.INTERNAL_SERVICE_SECRET = origSecret;
    if (origUrl === undefined) delete process.env.FASTAPI_BACKEND_URL;
    else process.env.FASTAPI_BACKEND_URL = origUrl;
  }
});

console.log("============================================================");
if (!process.exitCode) {
  console.log(`✓ ALL ${passedCount}/7 Practice sandbox status & UI state tests passed!`);
}
