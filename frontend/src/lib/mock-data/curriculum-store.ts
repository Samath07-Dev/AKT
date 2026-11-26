/**
 * frontend/src/lib/mock-data/curriculum-store.ts
 *
 * Centralized Canonical Demonstration Store for AKT-Project Frontend.
 * Ensures consistent demonstration data across Dashboard, Analytics,
 * Adaptive Learning, History, Profile, and Practice Arena.
 *
 * Strict Isolation: Client-side mock data only. Does not connect to live backend.
 */

export interface KnowledgeComponentItem {
  name: string;
  mastery: number;      // 0.0 to 100.0 (μ)
  uncertainty: number;  // 0.0 to 100.0 (σ)
  status: "Mastered" | "In Progress" | "Focus Area";
  difficulty: "easy" | "medium" | "hard";
  recommendedModality: string;
  explanation: string;
}

export interface DetailedSessionRecord {
  id: string;
  submissionId?: string;
  timestamp?: string;
  date: string;
  concept: string;
  difficulty: "easy" | "medium" | "hard";
  bundleScore: number;       // 0 to 100
  mcqScores: number[];       // e.g. [1.0, 1.0, 0.0]
  shortAnswerScore: number | null;  // 0 to 100, or null if not recorded
  codeScore: number;         // 0 to 100
  codeStatus?: string;
  codeExecutionStatus?: string;
  syntaxPreviewPassed?: boolean;
  codeTestsPassed: number;
  codeTestsTotal: number;
  nextDifficulty: "easy" | "medium" | "hard";
  scaffoldingReason: string;
  details: {
    mcqs: Array<{ question: string; selected: string; correct: string; isCorrect: boolean }>;
    shortAnswer: { question: string; studentAnswer: string; rubric: string; similarity: number | null };
    coding: { problem: string; passed: number; total: number; syntaxValid: boolean };
  };
}

// -----------------------------------------------------------------------------
// 1. CANONICAL 10 PYTHON KNOWLEDGE COMPONENTS
// -----------------------------------------------------------------------------
export const CANONICAL_KNOWLEDGE_COMPETENCIES: KnowledgeComponentItem[] = [
  {
    name: "Variables",
    mastery: 92.0,
    uncertainty: 12.0,
    status: "Mastered",
    difficulty: "hard",
    recommendedModality: "Python Coding Sandbox",
    explanation: "Mastery demonstrated (92%); lowest acquisition priority in curriculum matrix.",
  },
  {
    name: "Syntax",
    mastery: 88.0,
    uncertainty: 15.0,
    status: "Mastered",
    difficulty: "hard",
    recommendedModality: "Python Coding Sandbox",
    explanation: "Near-total mastery (88%) with confident model convergence.",
  },
  {
    name: "Conditionals",
    mastery: 78.0,
    uncertainty: 22.0,
    status: "Mastered",
    difficulty: "hard",
    recommendedModality: "Python Coding Sandbox",
    explanation: "Strong competence (78%) with low uncertainty promotes advanced procedural challenge.",
  },
  {
    name: "Functions",
    mastery: 72.0,
    uncertainty: 28.0,
    status: "In Progress",
    difficulty: "medium",
    recommendedModality: "Python Coding Sandbox",
    explanation: "High conceptual understanding (72%); procedural code execution sandbox test is appropriate.",
  },
  {
    name: "Arrays",
    mastery: 65.0,
    uncertainty: 34.0,
    status: "In Progress",
    difficulty: "medium",
    recommendedModality: "Conceptual Short Answer",
    explanation: "Progressing toward mastery (65%); semantic rubric analysis evaluates edge cases.",
  },
  {
    name: "Dictionaries",
    mastery: 58.0,
    uncertainty: 41.0,
    status: "In Progress",
    difficulty: "medium",
    recommendedModality: "Conceptual Short Answer",
    explanation: "Intermediate competence (58%); SBERT semantic explanation provides conceptual consolidation.",
  },
  {
    name: "Loops",
    mastery: 35.0,
    uncertainty: 52.0,
    status: "Focus Area",
    difficulty: "medium",
    recommendedModality: "Multiple Choice Question",
    explanation: "Low mastery (35%) and elevated uncertainty (52%) prioritize conceptual reinforcement.",
  },
  {
    name: "OOP",
    mastery: 30.0,
    uncertainty: 60.0,
    status: "Focus Area",
    difficulty: "easy",
    recommendedModality: "Multiple Choice Question",
    explanation: "Object-oriented constructs require foundational knowledge before code synthesis.",
  },
  {
    name: "File Handling",
    mastery: 25.0,
    uncertainty: 65.0,
    status: "Focus Area",
    difficulty: "easy",
    recommendedModality: "Multiple Choice Question",
    explanation: "High epistemic uncertainty indicates prior lack of evidence; easy scaffolding recommended.",
  },
  {
    name: "Exception Handling",
    mastery: 20.0,
    uncertainty: 70.0,
    status: "Focus Area",
    difficulty: "easy",
    recommendedModality: "Multiple Choice Question",
    explanation: "Untested curriculum tail: maximal uncertainty (70%) and low mastery (20%) trigger baseline declarative scaffolding.",
  },
];

// -----------------------------------------------------------------------------
// 2. MATHEMATICAL POLICY FORMULA: Priority = (1.0 - μ) × (1.0 + σ)
// -----------------------------------------------------------------------------
export function computePriorityScore(masteryPercent: number, uncertaintyPercent: number): number {
  const mu = masteryPercent / 100.0;
  const sigma = uncertaintyPercent / 100.0;
  return (1.0 - mu) * (1.0 + sigma);
}

// -----------------------------------------------------------------------------
// 3. PURE HELPER FUNCTIONS FOR DERIVED METRICS
// -----------------------------------------------------------------------------

/**
 * Calculates overall curriculum mastery average across all 10 KCs.
 * Expected: (92 + 88 + 78 + 72 + 65 + 58 + 35 + 30 + 25 + 20) / 10 = 56.3%
 */
export function calculateOverallMastery(kcs: KnowledgeComponentItem[] = CANONICAL_KNOWLEDGE_COMPETENCIES): number {
  if (kcs.length === 0) return 0;
  const total = kcs.reduce((acc, kc) => acc + kc.mastery, 0);
  return Number((total / kcs.length).toFixed(1));
}

/**
 * Calculates mean epistemic uncertainty across all 10 KCs.
 * Expected: (12 + 15 + 22 + 28 + 34 + 41 + 52 + 60 + 65 + 70) / 10 = 39.9%
 */
export function calculateMeanUncertainty(kcs: KnowledgeComponentItem[] = CANONICAL_KNOWLEDGE_COMPETENCIES): number {
  if (kcs.length === 0) return 0;
  const total = kcs.reduce((acc, kc) => acc + kc.uncertainty, 0);
  return Number((total / kcs.length).toFixed(1));
}

/**
 * Calculates count of mastered KCs based on mastery threshold >= 75%.
 * Expected: 3 / 10 (Variables 92%, Syntax 88%, Conditionals 78%)
 */
export function calculateMasteredKCCount(kcs: KnowledgeComponentItem[] = CANONICAL_KNOWLEDGE_COMPETENCIES, threshold = 75.0): number {
  return kcs.filter((kc) => kc.mastery >= threshold).length;
}

/**
 * Returns list of KCs ranked by Behavior-AKT acquisition priority descending.
 */
export function getRankedPolicyMatrix(kcs: KnowledgeComponentItem[] = CANONICAL_KNOWLEDGE_COMPETENCIES) {
  return [...kcs]
    .map((kc) => ({
      ...kc,
      priorityScore: computePriorityScore(kc.mastery, kc.uncertainty),
    }))
    .sort((a, b) => b.priorityScore - a.priorityScore);
}

/**
 * Returns the globally highest-priority KC according to the formula.
 * Expected: Exception Handling (Priority = 1.3600)
 */
export function getGlobalTopPriorityRecommendation(kcs: KnowledgeComponentItem[] = CANONICAL_KNOWLEDGE_COMPETENCIES) {
  const ranked = getRankedPolicyMatrix(kcs);
  return ranked[0];
}

// -----------------------------------------------------------------------------
// 4. ACTIVE DEMONSTRATION PRACTICE TARGET (DISTINCT FROM GLOBAL TOP DEFICIT)
// -----------------------------------------------------------------------------
/**
 * The Practice Arena interactive bundle is calibrated for Loops (Medium).
 * We maintain this explicitly separate from the global maximum-deficit target
 * so students understand why Loops is loaded in the interactive demo while
 * Exception Handling is identified as the theoretical highest priority deficit.
 */
export const ACTIVE_DEMONSTRATION_TARGET = {
  concept: "Loops",
  difficulty: "medium" as const,
  priorityScore: computePriorityScore(35.0, 52.0), // 0.9880
  mastery: 35.0,
  uncertainty: 52.0,
  modality: "5-Activity Concept Assessment Bundle",
  reasoning:
    "Active Demonstration Target: Calibrated interactive bundle focusing on loop control flow, boundary conditions, and procedural iteration.",
};

// -----------------------------------------------------------------------------
// 5. CANONICAL VERIFIED ASSESSMENT HISTORY (6 SESSIONS)
// -----------------------------------------------------------------------------
export const CANONICAL_ASSESSMENT_SESSIONS: DetailedSessionRecord[] = [
  {
    id: "sess_08",
    date: "Mar 8, 2026 14:20",
    concept: "Loops",
    difficulty: "medium",
    bundleScore: 82.5,
    mcqScores: [1.0, 1.0, 0.0],
    shortAnswerScore: 85.0,
    codeScore: 100.0,
    codeTestsPassed: 3,
    codeTestsTotal: 3,
    nextDifficulty: "hard",
    scaffoldingReason: "Score >= 80% baseline threshold -> Promoted to hard.",
    details: {
      mcqs: [
        { question: "What is the output of range(1, 6, 2)?", selected: "B", correct: "B", isCorrect: true },
        { question: "How does the 'continue' statement behave?", selected: "C", correct: "C", isCorrect: true },
        { question: "What is time complexity of iterating list?", selected: "A", correct: "C", isCorrect: false },
      ],
      shortAnswer: {
        question: "Explain difference between for loop and while loop.",
        studentAnswer: "A for loop iterates over an iterable, while a while loop checks a condition.",
        rubric: "for loop iterates over sequences, while loop checks boolean conditions.",
        similarity: 85.0,
      },
      coding: {
        problem: "Implement count_even_numbers(numbers)",
        passed: 3,
        total: 3,
        syntaxValid: true,
      },
    },
  },
  {
    id: "sess_07",
    date: "Mar 7, 2026 11:15",
    concept: "Dictionaries",
    difficulty: "medium",
    bundleScore: 74.0,
    mcqScores: [1.0, 0.0, 1.0],
    shortAnswerScore: 78.0,
    codeScore: 80.0,
    codeTestsPassed: 4,
    codeTestsTotal: 5,
    nextDifficulty: "medium",
    scaffoldingReason: "Score within [50%, 80%] maintenance interval -> Maintained medium.",
    details: {
      mcqs: [
        { question: "Which method retrieves all keys from a dictionary?", selected: "B", correct: "B", isCorrect: true },
        { question: "What happens when accessing a non-existent key with []?", selected: "A", correct: "C", isCorrect: false },
        { question: "Are Python dictionaries ordered?", selected: "A", correct: "A", isCorrect: true },
      ],
      shortAnswer: {
        question: "Explain hash collision handling in Python dicts.",
        studentAnswer: "Python uses open addressing with perturbation to resolve collisions.",
        rubric: "Open addressing hash table with quadratic/perturbation probing.",
        similarity: 78.0,
      },
      coding: {
        problem: "Count frequency of characters in a string using dict.",
        passed: 4,
        total: 5,
        syntaxValid: true,
      },
    },
  },
  {
    id: "sess_06",
    date: "Mar 6, 2026 16:45",
    concept: "Variables",
    difficulty: "hard",
    bundleScore: 92.0,
    mcqScores: [1.0, 1.0, 1.0],
    shortAnswerScore: 90.0,
    codeScore: 100.0,
    codeTestsPassed: 3,
    codeTestsTotal: 3,
    nextDifficulty: "hard",
    scaffoldingReason: "Consistent mastery above 90% -> Mastery status attained.",
    details: {
      mcqs: [
        { question: "What is reference counting in CPython?", selected: "A", correct: "A", isCorrect: true },
        { question: "Explain the 'global' vs 'nonlocal' scope keyword.", selected: "B", correct: "B", isCorrect: true },
        { question: "How are small integers cached in Python?", selected: "D", correct: "D", isCorrect: true },
      ],
      shortAnswer: {
        question: "Explain mutable vs immutable object binding.",
        studentAnswer: "Variables store references to memory objects, immutable objects cannot be modified in-place.",
        rubric: "Variables point to heap objects; immutables allocate new memory upon reassignment.",
        similarity: 90.0,
      },
      coding: {
        problem: "Implement custom deep clone utility for nested variables.",
        passed: 3,
        total: 3,
        syntaxValid: true,
      },
    },
  },
  {
    id: "sess_05",
    date: "Mar 5, 2026 09:30",
    concept: "Arrays",
    difficulty: "medium",
    bundleScore: 68.0,
    mcqScores: [1.0, 0.0, 1.0],
    shortAnswerScore: 72.0,
    codeScore: 66.7,
    codeTestsPassed: 2,
    codeTestsTotal: 3,
    nextDifficulty: "medium",
    scaffoldingReason: "Score within maintenance baseline [50%, 80%] -> Maintained medium.",
    details: {
      mcqs: [
        { question: "What is the time complexity of list.append()?", selected: "C", correct: "C", isCorrect: true },
        { question: "How does list slicing allocate memory?", selected: "B", correct: "A", isCorrect: false },
        { question: "What does list.pop(0) do?", selected: "D", correct: "D", isCorrect: true },
      ],
      shortAnswer: {
        question: "Explain dynamic resizing of list arrays.",
        studentAnswer: "Lists allocate extra slots and reallocate when full.",
        rubric: "Over-allocation geometric growth pattern upon reaching capacity.",
        similarity: 72.0,
      },
      coding: {
        problem: "Rotate an array to the right by k steps.",
        passed: 2,
        total: 3,
        syntaxValid: true,
      },
    },
  },
  {
    id: "sess_04",
    date: "Mar 4, 2026 13:10",
    concept: "Functions",
    difficulty: "easy",
    bundleScore: 88.0,
    mcqScores: [1.0, 1.0, 1.0],
    shortAnswerScore: 82.0,
    codeScore: 100.0,
    codeTestsPassed: 3,
    codeTestsTotal: 3,
    nextDifficulty: "medium",
    scaffoldingReason: "Performance exceeded 80% threshold -> Promoted to medium.",
    details: {
      mcqs: [
        { question: "What keyword defines a function?", selected: "A", correct: "A", isCorrect: true },
        { question: "What is the default return value if omitted?", selected: "C", correct: "C", isCorrect: true },
        { question: "How do default parameter arguments work?", selected: "B", correct: "B", isCorrect: true },
      ],
      shortAnswer: {
        question: "Define positional vs keyword arguments.",
        studentAnswer: "Positional args rely on order, keyword args are matched by parameter name.",
        rubric: "Positional arguments map by position, keywords map by parameter identifier.",
        similarity: 82.0,
      },
      coding: {
        problem: "Define a function that returns the square of a number.",
        passed: 3,
        total: 3,
        syntaxValid: true,
      },
    },
  },
  {
    id: "sess_03",
    date: "Mar 3, 2026 15:40",
    concept: "Conditionals",
    difficulty: "easy",
    bundleScore: 62.0,
    mcqScores: [1.0, 0.0, 0.0],
    shortAnswerScore: 65.0,
    codeScore: 100.0,
    codeTestsPassed: 3,
    codeTestsTotal: 3,
    nextDifficulty: "easy",
    scaffoldingReason: "Score below 70% threshold -> Maintained easy reinforcement.",
    details: {
      mcqs: [
        { question: "Which operator checks strict equality?", selected: "B", correct: "B", isCorrect: true },
        { question: "What is short-circuit evaluation in 'and'?", selected: "C", correct: "A", isCorrect: false },
        { question: "How does elif differ from multiple if statements?", selected: "D", correct: "B", isCorrect: false },
      ],
      shortAnswer: {
        question: "Explain truthy vs falsy evaluation in Python.",
        studentAnswer: "Empty containers and zero evaluate to False, other objects to True.",
        rubric: "Objects evaluating to False include 0, None, empty collections.",
        similarity: 65.0,
      },
      coding: {
        problem: "Determine whether a number is positive, negative or zero.",
        passed: 3,
        total: 3,
        syntaxValid: true,
      },
    },
  },
];

/**
 * Calculates mean bundle score across all verified sessions.
 * Expected: (82.5 + 74.0 + 92.0 + 68.0 + 88.0 + 62.0) / 6 = 77.8%
 */
export function calculateMeanBundleScore(sessions: DetailedSessionRecord[] = CANONICAL_ASSESSMENT_SESSIONS): number {
  if (sessions.length === 0) return 0;
  const total = sessions.reduce((acc, s) => acc + s.bundleScore, 0);
  return Number((total / sessions.length).toFixed(1));
}

/**
 * Calculates total questions attempted across all sessions.
 * Each session has 3 MCQs + 1 Short Answer + 1 Coding = 5 questions.
 * 6 sessions × 5 = 30 questions.
 */
export function calculateQuestionsAttempted(sessions: DetailedSessionRecord[] = CANONICAL_ASSESSMENT_SESSIONS): number {
  return sessions.reduce((acc, s) => acc + (s.details.mcqs.length + 1 + 1), 0);
}

// -----------------------------------------------------------------------------
// 6. STUDENT DEMONSTRATION IDENTITY
// -----------------------------------------------------------------------------
export const DEMO_STUDENT = {
  studentId: "S001",
  fullName: "Alice Smith",
  username: "student_s001",
  email: "alice.smith@university.edu",
  enrolledCurriculum: "Python Core Programming (MCA)",
  registrationDate: "Jan 15, 2026",
  lastActive: "Today at 12:45 PM",
};

