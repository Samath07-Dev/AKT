/**
 * frontend/src/lib/server/bundle-evaluator.ts
 *
 * Server-only evaluation store and evaluation engine.
 * Isolates answer keys and grading logic completely from client bundles.
 * 
 * Safety Restrictions (Step 5):
 * - Live execution of untrusted student Python code is quarantined.
 * - Code execution is reported as SANDBOX_OFFLINE to prevent host exec/eval vulnerabilities.
 */

import { callFastApiBackend } from "../api/backend-client";
import { hasMeaningfulCode } from "../code-structure";
import { getPublicBundle, PublicCodingQuestion } from "../mock-data/bundle-catalog";

export interface ServerMCQResult {
  questionIndex: number;
  questionId: string;
  selectedOption: string | null;
  isCorrect: boolean;
  correctOption?: string; // Revealed only AFTER evaluation
}

export interface ServerCodeTestResult {
  testIndex: number;
  call: string;
  description: string;
  passed: boolean;
  error?: string | null;
  actualRepr?: string | null;
}

export interface ServerBundleEvaluationResult {
  concept: string;
  difficulty: "easy" | "medium" | "hard";
  mcqPassedCount: number;
  mcqScores: number[];
  mcqResults: ServerMCQResult[];
  shortAnswerStatus: "EVALUATED" | "UNAVAILABLE";
  shortAnswerScore: number | null;
  shortAnswerFeedback: string;
  codeScore: number;
  codeStatus: "PENDING_SECURE_EVALUATION" | "PENDING SECURE EVALUATION" | "SANDBOX_OFFLINE" | "EVALUATED";
  codeExecutionStatus: "NOT_PERFORMED" | "EXECUTED";
  codeFeedback: string;
  codeRuntimeError?: string | null;
  codeTestResults?: ServerCodeTestResult[];
  codeTestsPassed: number;
  codeTotalTests: number;
  syntaxPreviewPassed: boolean;
  syntaxPreviewCount: number;
  bundleAveragePercent: number | null;
  isPartialAssessment: boolean;
  assessmentLabel: "COMPLETE BUNDLE" | "PARTIAL ASSESSMENT" | "ASSESSMENT UNAVAILABLE";
  scaffoldingReason: string;
  nextDifficulty: "easy" | "medium" | "hard";
}

// Canonical Answer Keys (Stored SERVER-ONLY, NEVER exported to client)
const PRIVATE_EVALUATION_STORE: Record<string, Record<"easy" | "medium" | "hard", { mcqAnswers: string[]; starterCode: string }>> = {
  "Variables": {
    "easy": {
      "mcqAnswers": ["B", "B", "C"],
      "starterCode": "def calculate_net_salary(gross_salary, tax_rate):\n    # Write your solution here\n    pass\n"
    },
    "medium": {
      "mcqAnswers": ["A", "B", "B"],
      "starterCode": "def convert_temperature(temp, unit):\n    # Write your solution here\n    pass\n"
    },
    "hard": {
      "mcqAnswers": ["B", "A", "B"],
      "starterCode": "def swap_and_aggregate(data_dict):\n    # Write your solution here\n    pass\n"
    }
  },
  "Conditionals": {
    "easy": {
      "mcqAnswers": ["B", "C", "A"],
      "starterCode": "def is_even(num):\n    # Write your solution here\n    pass\n"
    },
    "medium": {
      "mcqAnswers": ["A", "B", "B"],
      "starterCode": "def classify_triangle(a, b, c):\n    # Write your solution here\n    pass\n"
    },
    "hard": {
      "mcqAnswers": ["B", "B", "B"],
      "starterCode": "def validate_password(password):\n    # Write your solution here\n    pass\n"
    }
  },
  "Loops": {
    "easy": {
      "mcqAnswers": ["B", "C", "B"],
      "starterCode": "def sum_n(n):\n    # Write your solution here\n    pass\n"
    },
    "medium": {
      "mcqAnswers": ["B", "A", "B"],
      "starterCode": "def count_vowels(text):\n    # Write your solution here\n    pass\n"
    },
    "hard": {
      "mcqAnswers": ["B", "B", "C"],
      "starterCode": "def find_primes(n):\n    # Write your solution here\n    pass\n"
    }
  },
  "Functions": {
    "easy": {
      "mcqAnswers": ["B", "C", "A"],
      "starterCode": "def greet(name):\n    # Write your solution here\n    pass\n"
    },
    "medium": {
      "mcqAnswers": ["B", "C", "A"],
      "starterCode": "def factorial(n):\n    # Write your solution here\n    pass\n"
    },
    "hard": {
      "mcqAnswers": ["B", "B", "B"],
      "starterCode": "def memoize_fibonacci(n):\n    # Write your solution here\n    pass\n"
    }
  },
  "Arrays": {
    "easy": {
      "mcqAnswers": ["B", "A", "B"],
      "starterCode": "def find_max(numbers):\n    # Write your solution here\n    pass\n"
    },
    "medium": {
      "mcqAnswers": ["A", "A", "B"],
      "starterCode": "def filter_even(numbers):\n    # Write your solution here\n    pass\n"
    },
    "hard": {
      "mcqAnswers": ["B", "B", "A"],
      "starterCode": "def rotate_list(lst, k):\n    # Write your solution here\n    pass\n"
    }
  },
  "Syntax": {
    "easy": {
      "mcqAnswers": ["B", "C", "B"],
      "starterCode": "def fix_syntax():\n    # Write your solution here\n    pass\n"
    },
    "medium": {
      "mcqAnswers": ["B", "A", "A"],
      "starterCode": "def parse_key_values(kv_str):\n    # Write your solution here\n    pass\n"
    },
    "hard": {
      "mcqAnswers": ["B", "B", "B"],
      "starterCode": "def safe_eval_math(expr):\n    # Write your solution here\n    pass\n"
    }
  },
  "OOP": {
    "easy": {
      "mcqAnswers": ["C", "B", "A"],
      "starterCode": "class Person:\n    # Write your solution here\n    pass\n"
    },
    "medium": {
      "mcqAnswers": ["A", "B", "B"],
      "starterCode": "class BankAccount:\n    # Write your solution here\n    pass\n"
    },
    "hard": {
      "mcqAnswers": ["B", "B", "A"],
      "starterCode": "class Vehicle:\n    # Write your solution here\n    pass\n"
    }
  },
  "Dictionaries": {
    "easy": {
      "mcqAnswers": ["B", "C", "C"],
      "starterCode": "def get_value(d, key, default):\n    # Write your solution here\n    pass\n"
    },
    "medium": {
      "mcqAnswers": ["A", "B", "B"],
      "starterCode": "def merge_dicts(d1, d2):\n    # Write your solution here\n    pass\n"
    },
    "hard": {
      "mcqAnswers": ["B", "B", "C"],
      "starterCode": "def invert_dict(d):\n    # Write your solution here\n    pass\n"
    }
  },
  "File Handling": {
    "easy": {
      "mcqAnswers": ["B", "C", "B"],
      "starterCode": "def read_file_contents(filename):\n    # Write your solution here\n    pass\n"
    },
    "medium": {
      "mcqAnswers": ["A", "B", "B"],
      "starterCode": "def count_lines_in_file(filename):\n    # Write your solution here\n    pass\n"
    },
    "hard": {
      "mcqAnswers": ["B", "B", "A"],
      "starterCode": "def safe_file_write(filename, content):\n    # Write your solution here\n    pass\n"
    }
  },
  "Exception Handling": {
    "easy": {
      "mcqAnswers": ["B", "B", "B"],
      "starterCode": "def safe_divide(a, b):\n    # Write your solution here\n    pass\n"
    },
    "medium": {
      "mcqAnswers": ["B", "A", "B"],
      "starterCode": "def parse_integer(s):\n    # Write your solution here\n    pass\n"
    },
    "hard": {
      "mcqAnswers": ["B", "B", "B"],
      "starterCode": "def retry_operation(func, max_retries=3, fallback_value=None):\n    # Write your solution here\n    pass\n"
    }
  }
};

/**
 * Returns strictly verified binary scores (1.0 or 0.0) for MCQ results.
 * Guarantees no non-binary scores, NaNs, or nulls are ever passed to the BKT/EMA engine.
 */
export function getVerifiedBinaryMcqScores(results: ServerMCQResult[]): number[] {
  return results.map((r) => (r.isCorrect ? 1.0 : 0.0));
}

interface ShortAnswerSemanticEvaluation {
  status: "EVALUATED" | "UNAVAILABLE";
  score: number | null;
  feedback: string;
  isAcceptable: boolean;
  missingKeywords: string[];
  modelUsed?: string;
  fallbackActive?: boolean;
}

/**
 * Evaluates short-answer responses semantically using the FastAPI ShortAnswerAnalyzer (SBERT).
 * - Empty submissions short-circuit immediately to 0.0% without model calls (EVALUATED zero).
 * - Authenticates server-to-server with X-Internal-Service-Secret via callFastApiBackend.
 * - Does not accept or leak ground-truth reference answers to the browser.
 * - Never fabricates scores or returns a silent 85% fallback.
 * - If backend evaluation fails or times out, returns status: "UNAVAILABLE" and score: null.
 * - Transparently reports if lexical token overlap fallback was used.
 */
export async function evaluateShortAnswerSemantic(
  concept: string,
  difficulty: "easy" | "medium" | "hard",
  response: string
): Promise<ShortAnswerSemanticEvaluation> {
  const trimmed = (response || "").trim();
  if (!trimmed) {
    return {
      status: "EVALUATED",
      score: 0.0,
      feedback: "Short answer submission is empty.",
      isAcceptable: false,
      missingKeywords: [],
      modelUsed: "none",
      fallbackActive: true,
    };
  }

  try {
    const res = await callFastApiBackend<any>("/api/v1/analyze_short_answer", {
      method: "POST",
      timeoutMs: 5000,
      body: JSON.stringify({
        concept,
        difficulty,
        student_response: trimmed,
      }),
    });

    if (!res.ok || !res.data) {
      return {
        status: "UNAVAILABLE",
        score: null,
        feedback: `Short answer evaluation unavailable: ${res.error || "analyzer service communication failed"}.`,
        isAcceptable: false,
        missingKeywords: [],
      };
    }

    const data = res.data;
    if (typeof data.similarity_percentage !== "number") {
      return {
        status: "UNAVAILABLE",
        score: null,
        feedback: "Short answer evaluation unavailable: invalid response payload received from analyzer.",
        isAcceptable: false,
        missingKeywords: [],
      };
    }

    const score = Number(data.similarity_percentage.toFixed(1));
    let feedback: string;
    if (data.fallback_active) {
      feedback = `Semantic response evaluated via lexical token overlap: ${score}% (Transformer offline).`;
    } else {
      feedback = `Semantic response validated via SBERT (${score}%).`;
    }

    return {
      status: "EVALUATED",
      score,
      feedback,
      isAcceptable: Boolean(data.is_acceptable),
      missingKeywords: Array.isArray(data.missing_keywords) ? data.missing_keywords : [],
      modelUsed: data.model_used,
      fallbackActive: Boolean(data.fallback_active),
    };
  } catch (err: any) {
    return {
      status: "UNAVAILABLE",
      score: null,
      feedback: `Short answer evaluation unavailable: ${err?.message || "unexpected error during analyzer execution"}.`,
      isAcceptable: false,
      missingKeywords: [],
    };
  }
}

interface SandboxCodeEvaluation {
  codeScore: number;
  codeStatus: "PENDING_SECURE_EVALUATION" | "EVALUATED";
  codeExecutionStatus: "NOT_PERFORMED" | "EXECUTED";
  codeFeedback: string;
  codeRuntimeError: string | null;
  codeTestResults: ServerCodeTestResult[];
  codeTestsPassed: number;
  codeTotalTests: number;
  syntaxValid: boolean;
}

/**
 * Evaluates untrusted Python code strictly server-to-server via FastAPI `/api/v1/evaluate_code`,
 * which executes code inside ephemeral hardened Docker containers.
 * Fails closed to PENDING_SECURE_EVALUATION / NOT_PERFORMED whenever offline or unavailable.
 */
export async function evaluateCodeSandboxServer(
  concept: string,
  difficulty: "easy" | "medium" | "hard",
  codeString: string,
  fallbackTotalTests: number
): Promise<SandboxCodeEvaluation> {
  const pendingFallback = (reason: string): SandboxCodeEvaluation => ({
    codeScore: 0.0,
    codeStatus: "PENDING_SECURE_EVALUATION",
    codeExecutionStatus: "NOT_PERFORMED",
    codeFeedback: reason,
    codeRuntimeError: null,
    codeTestResults: [],
    codeTestsPassed: 0,
    codeTotalTests: fallbackTotalTests,
    syntaxValid: hasMeaningfulCode(codeString),
  });

  try {
    const res = await callFastApiBackend<any>("/api/v1/evaluate_code", {
      method: "POST",
      timeoutMs: 8000,
      body: JSON.stringify({
        concept,
        difficulty,
        code_string: codeString || "",
      }),
    });

    if (!res.ok || !res.data) {
      return pendingFallback(
        "Live Python execution is unavailable right now; coding evaluation is safely deferred as pending secure evaluation."
      );
    }

    const data = res.data;
    if (
      data.code_status === "EVALUATED" &&
      data.code_execution_status === "EXECUTED" &&
      typeof data.code_score === "number"
    ) {
      const total =
        typeof data.code_tests_total === "number" && data.code_tests_total >= 0
          ? data.code_tests_total
          : fallbackTotalTests;
      const passed =
        typeof data.code_tests_passed === "number" && data.code_tests_passed >= 0
          ? data.code_tests_passed
          : 0;
      const results: ServerCodeTestResult[] = Array.isArray(data.test_results)
        ? data.test_results.map((r: any, i: number) => ({
            testIndex: typeof r?.testIndex === "number" ? r.testIndex : i + 1,
            call: String(r?.call ?? ""),
            description: String(r?.description ?? ""),
            passed: Boolean(r?.passed),
            error: r?.error ? String(r.error) : null,
            actualRepr: r?.actualRepr ? String(r.actualRepr) : null,
          }))
        : [];

      return {
        codeScore: Number(data.code_score.toFixed(2)),
        codeStatus: "EVALUATED",
        codeExecutionStatus: "EXECUTED",
        codeFeedback: String(data.feedback || `Passed ${passed}/${total} isolated Python test cases.`),
        codeRuntimeError: data.runtime_error ? String(data.runtime_error) : null,
        codeTestResults: results,
        codeTestsPassed: passed,
        codeTotalTests: total,
        syntaxValid: Boolean(data.syntax_valid),
      };
    }

    return pendingFallback(
      String(
        data.feedback ||
          "Live Python execution is quarantined pending an isolated sandbox container. Syntax preview verified structure; actual coding execution is pending secure evaluation."
      )
    );
  } catch {
    return pendingFallback(
      "Live Python execution could not be reached; coding evaluation is deferred as pending secure evaluation."
    );
  }
}

/**
 * Server-only bundle evaluation adhering to safety constraints.
 * Evaluates MCQs and Short Answer asynchronously; isolates untrusted code execution.
 */
export async function evaluateAssessmentBundleServer(
  concept: string,
  difficulty: "easy" | "medium" | "hard",
  answers: {
    q1: string | null;
    q2: string | null;
    q3: string | null;
    q4: string;
    q5: string;
  }
): Promise<ServerBundleEvaluationResult> {
  const evalData = (PRIVATE_EVALUATION_STORE[concept] && PRIVATE_EVALUATION_STORE[concept][difficulty])
    ? PRIVATE_EVALUATION_STORE[concept][difficulty]
    : PRIVATE_EVALUATION_STORE["Loops"]["medium"];

  // 1. Evaluate MCQs
  const userOpts = [answers.q1, answers.q2, answers.q3];
  const mcqScores: number[] = [];
  const mcqResults: ServerMCQResult[] = evalData.mcqAnswers.map((correctOpt, idx) => {
    const selected = userOpts[idx];
    const isCorrect = Boolean(selected && selected.toUpperCase() === correctOpt.toUpperCase());
    const score = isCorrect ? 1.0 : 0.0;
    mcqScores.push(score);
    return {
      questionIndex: idx + 1,
      questionId: `${concept}_MCQ_${difficulty}_${idx + 1}`,
      selectedOption: selected,
      isCorrect,
      correctOption: correctOpt,
    };
  });

  const mcqPassedCount = mcqResults.filter((r) => r.isCorrect).length;
  const hasMcqResponses = userOpts.some((opt) => opt !== null && opt !== undefined && opt.trim() !== "");

  // 2. Evaluate Short Answer via FastAPI Semantic Analyzer asynchronously
  const saEval = await evaluateShortAnswerSemantic(concept, difficulty, answers.q4 || "");
  const shortAnswerStatus = saEval.status;
  const shortAnswerScore = saEval.score;
  const shortAnswerFeedback = saEval.feedback;

  // 3. Evaluate Coding Challenge via isolated FastAPI Docker sandbox (fails closed to PENDING_SECURE_EVALUATION)
  const rawCode = answers.q5 || "";
  const isMeaningful = hasMeaningfulCode(rawCode.trim());

  const publicBundle = getPublicBundle(concept, difficulty);
  const codingQ = publicBundle?.questions.find((q) => q.type === "coding") as PublicCodingQuestion | undefined;
  const fallbackTotalTests = codingQ && Array.isArray(codingQ.testCases) ? codingQ.testCases.length : 3;

  const codeEval = await evaluateCodeSandboxServer(concept, difficulty, rawCode, fallbackTotalTests);
  const codeStatus = codeEval.codeStatus;
  const codeExecutionStatus = codeEval.codeExecutionStatus;
  const codeFeedback = codeEval.codeFeedback;
  const codeScore = codeEval.codeScore;
  const codeTestsPassed = codeEval.codeTestsPassed;
  const codeTotalTests = codeEval.codeTotalTests;
  const codeRuntimeError = codeEval.codeRuntimeError;
  const codeTestResults = codeEval.codeTestResults;
  const syntaxPreviewPassed = isMeaningful && codeEval.syntaxValid;
  const syntaxPreviewCount = isMeaningful ? codeTotalTests : 0;

  // 4. Compute composite evidence score & Assessment Modality Labeling (Phase 6A)
  let bundleAveragePercent: number | null = null;
  let isPartialAssessment = false;
  let assessmentLabel: "COMPLETE BUNDLE" | "PARTIAL ASSESSMENT" | "ASSESSMENT UNAVAILABLE";
  let nextDifficulty: "easy" | "medium" | "hard" = difficulty;
  let scaffoldingReason = "Score within maintenance interval -> difficulty preserved.";

  const mcqFraction = mcqPassedCount / 3.0;

  if (shortAnswerStatus === "EVALUATED" && typeof shortAnswerScore === "number") {
    // Complete bundle evaluation: MCQs (60%) + Short Answer (40%)
    assessmentLabel = "COMPLETE BUNDLE";
    isPartialAssessment = false;
    const saFraction = shortAnswerScore / 100.0;
    const compositeEvidence = (mcqFraction * 0.6) + (saFraction * 0.4);
    bundleAveragePercent = Number((compositeEvidence * 100).toFixed(1));

    if (compositeEvidence >= 0.8) {
      if (difficulty === "easy") {
        nextDifficulty = "medium";
        scaffoldingReason = "Mastery demonstrated (>= 80%) -> Scaffolding up to Medium.";
      } else if (difficulty === "medium") {
        nextDifficulty = "hard";
        scaffoldingReason = "High mastery demonstrated (>= 80%) -> Scaffolding up to Hard.";
      } else {
        scaffoldingReason = "Maximum challenge level maintained (>= 80%).";
      }
    } else if (compositeEvidence < 0.5) {
      if (difficulty === "hard") {
        nextDifficulty = "medium";
        scaffoldingReason = "Evidence deficit (< 50%) -> Scaffolding down to Medium for foundational consolidation.";
      } else if (difficulty === "medium") {
        nextDifficulty = "easy";
        scaffoldingReason = "Evidence deficit (< 50%) -> Scaffolding down to Easy for fundamental remediation.";
      } else {
        scaffoldingReason = "Reinforcing foundational concepts at Easy level.";
      }
    }
  } else if (hasMcqResponses) {
    // Partial assessment: short-answer unavailable, verified MCQ evidence available
    assessmentLabel = "PARTIAL ASSESSMENT";
    isPartialAssessment = true;
    bundleAveragePercent = Number((mcqFraction * 100).toFixed(1));
    nextDifficulty = difficulty; // Preserve previous difficulty
    scaffoldingReason = `PARTIAL ASSESSMENT: Short-answer evaluation unavailable. Partial score calculated from verified MCQs only (${mcqPassedCount}/3). Difficulty preserved at ${difficulty.toUpperCase()} pending full evaluation.`;
  } else {
    // All evidence unavailable: no MCQs answered and short-answer unavailable
    assessmentLabel = "ASSESSMENT UNAVAILABLE";
    isPartialAssessment = true;
    bundleAveragePercent = null;
    nextDifficulty = difficulty; // Preserve previous difficulty
    scaffoldingReason = `ASSESSMENT UNAVAILABLE: Both MCQ and short-answer evidence are unavailable. No score fabricated. Difficulty preserved at ${difficulty.toUpperCase()}.`;
  }

  return {
    concept,
    difficulty,
    mcqPassedCount,
    mcqScores,
    mcqResults,
    shortAnswerStatus,
    shortAnswerScore,
    shortAnswerFeedback,
    codeScore,
    codeStatus,
    codeExecutionStatus,
    codeFeedback,
    codeRuntimeError,
    codeTestResults,
    codeTestsPassed,
    codeTotalTests,
    syntaxPreviewPassed,
    syntaxPreviewCount,
    bundleAveragePercent,
    isPartialAssessment,
    assessmentLabel,
    scaffoldingReason,
    nextDifficulty,
  };
}

