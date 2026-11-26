/**
 * frontend/test_history_coding_evaluation.mjs
 *
 * Automated regression test suite for Assessment History coding evaluation
 * persistence mapping, status normalization, and dynamic test spec resolution.
 *
 * Covers:
 * 1. Pending status survives bundle evaluator -> FastAPI record payload -> history API -> frontend mapping -> display
 * 2. SANDBOX_OFFLINE and pending variants correctly display Pending Secure Evaluation
 * 3. Genuine evaluated zero coding score remains 0.0%
 * 4. Historical records with missing metadata remain Not evaluated while preserving recorded codeScore
 * 5. OOP Medium dynamically resolves to 2 test specifications
 * 6. All curriculum concepts retain their actual test specification counts
 * 7. Python execution notice truthful status mapping and fail-closed safety
 */

import jiti from "jiti";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

const j = jiti(import.meta.url, {
  alias: {
    "@": fileURLToPath(new URL("./src", import.meta.url)),
  },
});
const {
  resolveCodeTestsTotal,
  getCodingEvaluationDisplay,
  mapHistoryApiRecordToSession,
  getCodingExecutionNotice,
} = j("./src/lib/history-evaluation.ts");
const { evaluateAssessmentBundleServer } = j("./src/lib/server/bundle-evaluator.ts");
const { PUBLIC_BUNDLE_CATALOG } = j("./src/lib/mock-data/bundle-catalog.ts");

console.log("============================================================");
console.log("   Assessment History Coding Evaluation Regression Tests     ");
console.log("============================================================");

let passedCount = 0;
let totalCount = 0;

async function runTest(name, fn) {
  totalCount++;
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

// -----------------------------------------------------------------------------
// Test 1: Pending status survives evaluator -> payload -> history API -> frontend
// -----------------------------------------------------------------------------
await runTest("1. Pending status survives evaluator -> payload -> history API -> frontend", async () => {
  const evalResult = await evaluateAssessmentBundleServer("OOP", "medium", {
    q1: "A",
    q2: "B",
    q3: "B",
    q4: "", // Empty short answer short-circuits to 0.0% without external HTTP call
    q5: "class BankAccount:\n    def __init__(self):\n        self.balance = 0\n",
  });

  // Verify evaluator outputs (60% MCQ + 40% short answer untouched)
  assert.equal(evalResult.mcqPassedCount, 3);
  assert.equal(evalResult.shortAnswerScore, 0);
  assert.equal(evalResult.bundleAveragePercent, 60.0);
  assert.equal(evalResult.codeStatus, "PENDING_SECURE_EVALUATION");
  assert.equal(evalResult.codeExecutionStatus, "NOT_PERFORMED");
  assert.equal(evalResult.codeTestsPassed, 0);
  assert.equal(evalResult.codeTotalTests, 2);
  assert.equal(evalResult.codeScore, 0.0);

  // Simulate exact FastAPI score payload forwarded by /api/practice/evaluate and returned by /history
  const persistedApiRecord = {
    submission_id: "sub_S009_test_pending_oop",
    student_id: "S009",
    concept: evalResult.concept,
    difficulty: evalResult.difficulty,
    bundle_average_score: evalResult.bundleAveragePercent,
    mcq_scores: [1.0, 1.0, 1.0],
    short_answer_score: evalResult.shortAnswerScore,
    code_score: evalResult.codeScore,
    code_status: evalResult.codeStatus,
    code_execution_status: evalResult.codeExecutionStatus,
    code_tests_passed: evalResult.codeTestsPassed,
    code_tests_total: evalResult.codeTotalTests,
    syntax_preview_passed: evalResult.syntaxPreviewPassed,
    syntax_preview_count: evalResult.syntaxPreviewCount,
    next_difficulty: evalResult.nextDifficulty,
    scaffolding_reasoning: evalResult.scaffoldingReason,
    timestamp: "2026-11-12T12:00:00.000Z",
  };

  const sessionRecord = mapHistoryApiRecordToSession(persistedApiRecord, 0);
  assert.equal(sessionRecord.codeStatus, "PENDING_SECURE_EVALUATION");
  assert.equal(sessionRecord.codeExecutionStatus, "NOT_PERFORMED");
  assert.equal(sessionRecord.codeTestsPassed, 0);
  assert.equal(sessionRecord.codeTestsTotal, 2);
  assert.equal(sessionRecord.codeScore, 0);

  const display = getCodingEvaluationDisplay(sessionRecord);
  assert.equal(display.isPending, true);
  assert.equal(display.isEvaluated, false);
  assert.equal(display.isMissingMetadata, false);
  assert.equal(display.executionLabel, "Not performed");
  assert.equal(display.automatedTestsLabel, "Pending secure evaluation");
  assert.equal(display.codeScoreLabel, "Pending secure evaluation");
  assert.equal(display.tableCellLabel, "Pending evaluation");
  assert.equal(
    display.executionNotice,
    "Python execution was not performed because secure sandbox evaluation was unavailable."
  );
});

// -----------------------------------------------------------------------------
// Test 2: Pending / SANDBOX_OFFLINE coding evaluation & legacy format variants
// -----------------------------------------------------------------------------
await runTest("2. SANDBOX_OFFLINE and pending variants display Pending Secure Evaluation", () => {
  const pendingScenarios = [
    {
      label: "Explicit codeExecutionStatus NOT_PERFORMED with spaced status",
      record: {
        concept: "OOP",
        difficulty: "medium",
        codeScore: 0,
        codeStatus: "PENDING SECURE EVALUATION",
        codeExecutionStatus: "NOT_PERFORMED",
        codeTestsPassed: 0,
        codeTestsTotal: null,
      },
    },
    {
      label: "Explicit codeExecutionStatus SANDBOX_OFFLINE",
      record: {
        concept: "OOP",
        difficulty: "medium",
        codeScore: 0,
        codeStatus: "SANDBOX_OFFLINE",
        codeExecutionStatus: "SANDBOX_OFFLINE",
        codeTestsPassed: 0,
        codeTestsTotal: 2,
      },
    },
    {
      label: "Hyphenated lowercase legacy codeStatus",
      record: {
        concept: "Loops",
        difficulty: "medium",
        codeScore: 0,
        codeStatus: "pending-secure-evaluation",
        codeExecutionStatus: "not-performed",
        codeTestsPassed: 0,
        codeTestsTotal: 3,
      },
    },
    {
      label: "Explicit codeStatus NOT_EVALUATED",
      record: {
        concept: "Variables",
        difficulty: "easy",
        codeScore: 0,
        codeStatus: "NOT_EVALUATED",
        codeExecutionStatus: "NOT_EVALUATED",
        codeTestsPassed: 0,
        codeTestsTotal: null,
      },
    },
  ];

  for (const { label, record } of pendingScenarios) {
    const display = getCodingEvaluationDisplay(record);
    assert.equal(display.isPending, true, `${label}: isPending should be true`);
    assert.equal(display.isEvaluated, false, `${label}: isEvaluated should be false`);
    assert.equal(display.executionLabel, "Not performed", `${label}: executionLabel mismatch`);
    assert.equal(display.automatedTestsLabel, "Pending secure evaluation", `${label}: automatedTestsLabel mismatch`);
    assert.equal(display.codeScoreLabel, "Pending secure evaluation", `${label}: codeScoreLabel mismatch`);
    assert.equal(display.tableCellLabel, "Pending evaluation", `${label}: tableCellLabel mismatch`);
  }
});

// -----------------------------------------------------------------------------
// Test 3: Genuine evaluated zero coding score
// -----------------------------------------------------------------------------
await runTest("3. Genuine evaluated zero coding score remains 0.0%", () => {
  const mappedEvaluatedZero = mapHistoryApiRecordToSession(
    {
      submission_id: "sub_eval_zero",
      concept: "OOP",
      difficulty: "medium",
      bundle_average_score: 70.0,
      mcq_scores: [1.0, 1.0, 0.0],
      short_answer_score: 75.0,
      code_score: 0.0,
      code_status: "EVALUATED",
      code_execution_status: "EXECUTED",
      code_tests_passed: 0,
      code_tests_total: 2,
      timestamp: "2026-11-12T10:00:00.000Z",
    },
    0
  );

  const display = getCodingEvaluationDisplay(mappedEvaluatedZero);
  assert.equal(display.isPending, false, "isPending should be false");
  assert.equal(display.isEvaluated, true, "isEvaluated should be true");
  assert.equal(display.isMissingMetadata, false, "isMissingMetadata should be false");
  assert.equal(display.executionLabel, "Executed", "executionLabel mismatch");
  assert.equal(display.automatedTestsLabel, "0 / 2", "automatedTestsLabel mismatch");
  assert.equal(display.codeScoreLabel, "0.0%", "codeScoreLabel should preserve genuine 0.0%");
  assert.equal(display.tableCellLabel, "0 / 2", "tableCellLabel mismatch");
  assert.equal(
    display.executionNotice,
    "Python code was executed inside an isolated, network-disabled Docker container. Host execution remains disabled.",
    "executionNotice mismatch"
  );
});

// -----------------------------------------------------------------------------
// Test 4: Historical records with missing metadata
// -----------------------------------------------------------------------------
await runTest("4. Historical records with missing metadata remain Not evaluated and preserve score", () => {
  const historicalZeroFromApi = mapHistoryApiRecordToSession(
    {
      submission_id: "sub_legacy_zero",
      concept: "OOP",
      difficulty: "medium",
      bundle_average_score: 93.5,
      mcq_scores: [1.0, 1.0, 1.0],
      short_answer_score: 83.8,
      code_score: 0.0,
      timestamp: "2026-11-12T09:38:35.232Z",
    },
    0
  );

  const displayZero = getCodingEvaluationDisplay(historicalZeroFromApi);
  assert.equal(displayZero.isPending, false, "Historical record without pending marker should not be pending");
  assert.equal(displayZero.isEvaluated, false, "Historical record without evaluation marker should not be evaluated");
  assert.equal(displayZero.isMissingMetadata, true, "isMissingMetadata should be true");
  assert.equal(displayZero.executionLabel, "Not evaluated", "executionLabel should be 'Not evaluated'");
  assert.equal(displayZero.automatedTestsLabel, "Not evaluated", "automatedTestsLabel should be 'Not evaluated'");
  assert.equal(displayZero.codeScoreLabel, "0.0%", "codeScoreLabel should preserve recorded zero as 0.0%");
  assert.equal(displayZero.tableCellLabel, "Not evaluated", "tableCellLabel should NOT invent 0/3");
  assert.equal(
    displayZero.executionNotice,
    "Python execution status is unavailable or unverified. Host execution remains disabled.",
    "executionNotice should fail closed for missing metadata"
  );

  const historicalNonZero = getCodingEvaluationDisplay({
    concept: "Variables",
    difficulty: "easy",
    codeScore: 90.0,
    codeStatus: null,
    codeExecutionStatus: null,
    codeTestsPassed: null,
    codeTestsTotal: null,
  });
  assert.equal(historicalNonZero.executionLabel, "Not evaluated");
  assert.equal(historicalNonZero.automatedTestsLabel, "Not evaluated");
  assert.equal(historicalNonZero.codeScoreLabel, "90.0%", "Non-zero recorded score must be preserved");
  assert.equal(historicalNonZero.tableCellLabel, "Not evaluated");
  assert.equal(
    historicalNonZero.executionNotice,
    "Python execution status is unavailable or unverified. Host execution remains disabled.",
    "executionNotice should fail closed for missing metadata with non-zero score"
  );
});

// -----------------------------------------------------------------------------
// Test 5: OOP medium dynamic total resolution
// -----------------------------------------------------------------------------
await runTest("5. OOP medium dynamically resolves to 2 test specifications", () => {
  assert.equal(
    resolveCodeTestsTotal("OOP", "medium", null),
    2,
    "OOP medium must dynamically resolve to exactly 2 test specifications"
  );
  assert.equal(
    resolveCodeTestsTotal("OOP", "medium", 0),
    2,
    "Stored total 0 should fall back to OOP medium catalog count 2"
  );
  assert.equal(
    resolveCodeTestsTotal("OOP", "medium", 2),
    2,
    "Stored total 2 should be preserved"
  );
});

// -----------------------------------------------------------------------------
// Test 6: Other concepts retain their actual curriculum test counts
// -----------------------------------------------------------------------------
await runTest("6. All curriculum concepts retain their actual test specification counts", () => {
  for (const [concept, difficulties] of Object.entries(PUBLIC_BUNDLE_CATALOG)) {
    for (const [difficulty, bundle] of Object.entries(difficulties)) {
      const codingQ = bundle.questions.find((q) => q.type === "coding");
      const expectedCount = codingQ.testCases.length;
      const resolved = resolveCodeTestsTotal(concept, difficulty, null);
      assert.equal(
        resolved,
        expectedCount,
        `${concept} (${difficulty}) should resolve to ${expectedCount}, got ${resolved}`
      );
    }
  }
  assert.equal(resolveCodeTestsTotal("Variables", "easy", null), 3);
  assert.equal(resolveCodeTestsTotal("Syntax", "easy", null), 1);
  assert.equal(resolveCodeTestsTotal("OOP", "hard", null), 1);
  assert.equal(resolveCodeTestsTotal("UnknownConcept", "medium", null), null);
});

// -----------------------------------------------------------------------------
// Test 7: Truthful Python execution notices across all status variants & fail-closed safety
// -----------------------------------------------------------------------------
await runTest("7. Truthful Python execution notices across all status variants & fail-closed safety", () => {
  const EXECUTED_NOTICE =
    "Python code was executed inside an isolated, network-disabled Docker container. Host execution remains disabled.";
  const NOT_PERFORMED_NOTICE =
    "Python execution was not performed because secure sandbox evaluation was unavailable.";
  const PENDING_NOTICE =
    "Python execution is pending secure evaluation.";
  const UNVERIFIED_NOTICE =
    "Python execution status is unavailable or unverified. Host execution remains disabled.";

  // Scenario 1: EXECUTED
  assert.equal(
    getCodingExecutionNotice({ codeExecutionStatus: "EXECUTED" }),
    EXECUTED_NOTICE,
    "Scenario 1: EXECUTED must render container isolation notice"
  );
  assert.equal(
    getCodingExecutionNotice({ codeExecutionStatus: "executed" }),
    EXECUTED_NOTICE,
    "Scenario 1: Lowercase 'executed' must normalize to EXECUTED notice"
  );
  assert.equal(
    getCodingEvaluationDisplay({
      codeExecutionStatus: "EXECUTED",
      codeScore: 100,
      codeTestsPassed: 3,
      codeTestsTotal: 3,
    }).executionNotice,
    EXECUTED_NOTICE,
    "Scenario 1: getCodingEvaluationDisplay must return EXECUTED notice"
  );

  // Scenario 2: NOT_PERFORMED
  assert.equal(
    getCodingExecutionNotice({ codeExecutionStatus: "NOT_PERFORMED" }),
    NOT_PERFORMED_NOTICE,
    "Scenario 2: NOT_PERFORMED must render sandbox unavailable notice"
  );
  assert.equal(
    getCodingExecutionNotice({ codeExecutionStatus: "not-performed" }),
    NOT_PERFORMED_NOTICE,
    "Scenario 2: Hyphenated lowercase 'not-performed' must normalize to NOT_PERFORMED notice"
  );
  assert.equal(
    getCodingEvaluationDisplay({ codeExecutionStatus: "NOT_PERFORMED" }).executionNotice,
    NOT_PERFORMED_NOTICE,
    "Scenario 2: getCodingEvaluationDisplay must return NOT_PERFORMED notice"
  );

  // Scenario 3: SANDBOX_OFFLINE
  assert.equal(
    getCodingExecutionNotice({ codeExecutionStatus: "SANDBOX_OFFLINE" }),
    NOT_PERFORMED_NOTICE,
    "Scenario 3: SANDBOX_OFFLINE must render sandbox unavailable notice"
  );
  assert.equal(
    getCodingExecutionNotice({ codeExecutionStatus: "sandbox_offline" }),
    NOT_PERFORMED_NOTICE,
    "Scenario 3: Lowercase 'sandbox_offline' must normalize to NOT_PERFORMED notice"
  );
  assert.equal(
    getCodingEvaluationDisplay({ codeExecutionStatus: "SANDBOX_OFFLINE" }).executionNotice,
    NOT_PERFORMED_NOTICE,
    "Scenario 3: getCodingEvaluationDisplay must return SANDBOX_OFFLINE notice"
  );

  // Scenario 4: PENDING_SECURE_EVALUATION
  assert.equal(
    getCodingExecutionNotice({ codeExecutionStatus: "PENDING_SECURE_EVALUATION" }),
    PENDING_NOTICE,
    "Scenario 4: PENDING_SECURE_EVALUATION must render pending notice"
  );
  assert.equal(
    getCodingExecutionNotice({ codeExecutionStatus: "pending-secure-evaluation" }),
    PENDING_NOTICE,
    "Scenario 4: Hyphenated lowercase 'pending-secure-evaluation' must normalize to PENDING notice"
  );
  assert.equal(
    getCodingEvaluationDisplay({ codeExecutionStatus: "PENDING_SECURE_EVALUATION" }).executionNotice,
    PENDING_NOTICE,
    "Scenario 4: getCodingEvaluationDisplay must return PENDING notice"
  );

  // Scenario 5: Missing, null, or undefined execution status
  assert.equal(
    getCodingExecutionNotice({ codeExecutionStatus: null }),
    UNVERIFIED_NOTICE,
    "Scenario 5: null execution status must render unverified notice"
  );
  assert.equal(
    getCodingExecutionNotice({ codeExecutionStatus: undefined }),
    UNVERIFIED_NOTICE,
    "Scenario 5: undefined execution status must render unverified notice"
  );
  assert.equal(
    getCodingExecutionNotice({}),
    UNVERIFIED_NOTICE,
    "Scenario 5: empty record must render unverified notice"
  );
  assert.equal(
    getCodingExecutionNotice({ codeExecutionStatus: "" }),
    UNVERIFIED_NOTICE,
    "Scenario 5: empty string execution status must render unverified notice"
  );
  assert.equal(
    getCodingEvaluationDisplay({ codeExecutionStatus: null, codeStatus: null }).executionNotice,
    UNVERIFIED_NOTICE,
    "Scenario 5: getCodingEvaluationDisplay with null status must render unverified notice"
  );

  // Scenario 5 legacy fallbacks (when codeExecutionStatus is missing/null/undefined):
  assert.equal(
    getCodingExecutionNotice({ codeExecutionStatus: null, codeStatus: "PENDING_SECURE_EVALUATION" }),
    PENDING_NOTICE,
    "Scenario 5 fallback: legacy pending codeStatus must render pending notice"
  );
  assert.equal(
    getCodingExecutionNotice({ codeExecutionStatus: null, codeStatus: "pending-secure-evaluation" }),
    PENDING_NOTICE,
    "Scenario 5 fallback: legacy hyphenated pending codeStatus must render pending notice"
  );
  assert.equal(
    getCodingExecutionNotice({ codeExecutionStatus: null, codeStatus: "NOT_PERFORMED" }),
    NOT_PERFORMED_NOTICE,
    "Scenario 5 fallback: legacy not_performed codeStatus must render sandbox unavailable notice"
  );
  assert.equal(
    getCodingExecutionNotice({ codeExecutionStatus: null, codeStatus: "SANDBOX_OFFLINE" }),
    NOT_PERFORMED_NOTICE,
    "Scenario 5 fallback: legacy sandbox_offline codeStatus must render sandbox unavailable notice"
  );

  // Scenario 6: Unknown execution status
  assert.equal(
    getCodingExecutionNotice({ codeExecutionStatus: "UNKNOWN" }),
    UNVERIFIED_NOTICE,
    "Scenario 6: UNKNOWN status must fail safe to unverified notice"
  );
  assert.equal(
    getCodingExecutionNotice({ codeExecutionStatus: "CORRUPT_STATUS_VALUE" }),
    UNVERIFIED_NOTICE,
    "Scenario 6: Arbitrary unrecognized status must fail safe to unverified notice"
  );
  assert.equal(
    getCodingEvaluationDisplay({ codeExecutionStatus: "UNKNOWN" }).executionNotice,
    UNVERIFIED_NOTICE,
    "Scenario 6: getCodingEvaluationDisplay with unknown status must render unverified notice"
  );

  // Safety invariant: 100% coding score or 3/3 tests passed NEVER implies EXECUTED notice
  const highScoringRecordsWithoutExecution = [
    {
      label: "100% score and 3/3 tests with null codeExecutionStatus and legacy codeStatus EVALUATED",
      record: {
        concept: "Functions",
        difficulty: "easy",
        codeScore: 100.0,
        codeTestsPassed: 3,
        codeTestsTotal: 3,
        codeExecutionStatus: null,
        codeStatus: "EVALUATED",
      },
      expectedNotice: UNVERIFIED_NOTICE,
    },
    {
      label: "100% score and 3/3 tests with undefined codeExecutionStatus and missing codeStatus",
      record: {
        concept: "Functions",
        difficulty: "easy",
        codeScore: 100.0,
        codeTestsPassed: 3,
        codeTestsTotal: 3,
      },
      expectedNotice: UNVERIFIED_NOTICE,
    },
    {
      label: "100% score and 3/3 tests with UNKNOWN codeExecutionStatus",
      record: {
        concept: "Functions",
        difficulty: "easy",
        codeScore: 100.0,
        codeTestsPassed: 3,
        codeTestsTotal: 3,
        codeExecutionStatus: "UNKNOWN",
        codeStatus: "EVALUATED",
      },
      expectedNotice: UNVERIFIED_NOTICE,
    },
    {
      label: "100% score and 3/3 tests with NOT_PERFORMED codeExecutionStatus",
      record: {
        concept: "Functions",
        difficulty: "easy",
        codeScore: 100.0,
        codeTestsPassed: 3,
        codeTestsTotal: 3,
        codeExecutionStatus: "NOT_PERFORMED",
      },
      expectedNotice: NOT_PERFORMED_NOTICE,
    },
    {
      label: "100% score and 3/3 tests with SANDBOX_OFFLINE codeExecutionStatus",
      record: {
        concept: "Functions",
        difficulty: "easy",
        codeScore: 100.0,
        codeTestsPassed: 3,
        codeTestsTotal: 3,
        codeExecutionStatus: "SANDBOX_OFFLINE",
      },
      expectedNotice: NOT_PERFORMED_NOTICE,
    },
    {
      label: "100% score and 3/3 tests with PENDING_SECURE_EVALUATION codeExecutionStatus",
      record: {
        concept: "Functions",
        difficulty: "easy",
        codeScore: 100.0,
        codeTestsPassed: 3,
        codeTestsTotal: 3,
        codeExecutionStatus: "PENDING_SECURE_EVALUATION",
      },
      expectedNotice: PENDING_NOTICE,
    },
  ];

  for (const { label, record, expectedNotice } of highScoringRecordsWithoutExecution) {
    const directNotice = getCodingExecutionNotice(record);
    const display = getCodingEvaluationDisplay(record);

    assert.notEqual(
      directNotice,
      EXECUTED_NOTICE,
      `${label}: direct notice MUST NOT claim EXECUTED`
    );
    assert.notEqual(
      display.executionNotice,
      EXECUTED_NOTICE,
      `${label}: display.executionNotice MUST NOT claim EXECUTED`
    );

    assert.equal(
      directNotice,
      expectedNotice,
      `${label}: direct notice mismatch`
    );
    assert.equal(
      display.executionNotice,
      expectedNotice,
      `${label}: display.executionNotice mismatch`
    );
  }
});

console.log("============================================================");
console.log(`✓ ALL ${passedCount}/${totalCount} Assessment History regression tests passed successfully!`);
