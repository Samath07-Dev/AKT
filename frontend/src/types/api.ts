/**
 * TypeScript definitions matching verified FastAPI schemas and domain models.
 */

export type ConceptName =
  | "Variables"
  | "Conditionals"
  | "Loops"
  | "Functions"
  | "Arrays"
  | "Syntax"
  | "OOP"
  | "Dictionaries"
  | "File Handling"
  | "Exception Handling";

export type DifficultyLevel = "easy" | "medium" | "hard";
export type ModalityType = "MCQ" | "Short Answer" | "Code";

export interface Student {
  student_id: string;
  username: string;
  full_name: string;
  email?: string;
  created_at?: string;
}

export interface ConceptMastery {
  mastery: number;      // mu in [0.0, 1.0]
  uncertainty: number;  // sigma in [0.0, 1.0]
  history?: Array<Record<string, unknown>>;
  attempts?: number;
  last_updated?: string;
}

export interface StudentMasteryResponse {
  student_id: string;
  knowledge_state: Record<ConceptName, ConceptMastery>;
  concept_difficulties?: Record<ConceptName, DifficultyLevel>;
}

export interface Recommendation {
  student_id: string;
  recommended_concept: ConceptName;
  priority_score: number;
  recommended_activity: string;
  activity_code: 0 | 1 | 2;
  concept_mastery: number;
  concept_uncertainty: number;
  recommended_difficulty: DifficultyLevel;
  scaffolding_reasoning: string;
  reasoning: string;
  question_details: Record<string, unknown>;
  all_concept_priorities: Array<{
    concept: ConceptName;
    priority: number;
    mastery: number;
    uncertainty: number;
  }>;
  difficulty_floor_active?: boolean;
  cycle_unattempted?: boolean;
  modality_downgraded?: boolean;
  prerequisite_fallback_applied?: boolean;
}

export interface MCQQuestion {
  id: string;
  difficulty: DifficultyLevel;
  question: string;
  options: string[];
  correct_option: string;
}

export interface ShortAnswerQuestion {
  id: string;
  difficulty: DifficultyLevel;
  question: string;
  reference_answer: string;
}

export interface TestCase {
  call: string;
  expected: unknown;
  description: string;
}

export interface CodingQuestion {
  id: string;
  difficulty: DifficultyLevel;
  problem: string;
  template: string;
  test_cases: TestCase[];
}

export interface ConceptBundle {
  concept: ConceptName;
  difficulty: DifficultyLevel;
  bundle: {
    mcqs: MCQQuestion[];
    short_answer: ShortAnswerQuestion;
    coding: CodingQuestion;
  };
}

export interface BundleAssessmentSubmission {
  student_id: string;
  concept: ConceptName;
  difficulty: DifficultyLevel;
  mcq_responses: string[];
  short_answer_response: string;
  code_response: string;
  passed_test_cases: number;
  total_test_cases: number;
  response_time_sec: number;
}

export interface MCQGradingDetail {
  question_id: string;
  question: string;
  selected_option: string;
  correct_option: string;
  is_correct: boolean;
  evidence_score: number;
}

export interface ShortAnswerGradingDetail {
  question: string;
  student_response: string;
  reference_answer: string;
  evidence_score: number;
  similarity_percentage: number;
  missing_keywords: string[];
  is_acceptable: boolean;
  feedback: string;
}

export interface CodingGradingDetail {
  problem: string;
  code_string: string;
  evidence_score: number;
  pass_fraction: number;
  passed_test_cases: number;
  total_test_cases: number;
  is_compilable: boolean;
  syntax_valid: boolean;
  syntax_error?: string | null;
  runtime_error?: string | null;
  feedback: string;
}

export interface BundleAssessmentResponse {
  student_id: string;
  concept: ConceptName;
  mcq_scores: number[];
  short_answer_score: number;
  code_score: number;
  bundle_average_score: number;
  updated_mastery: number;
  updated_uncertainty: number;
  feedbacks: string[];
  difficulty: DifficultyLevel;
  next_recommended_difficulty: DifficultyLevel;
  scaffolding_reasoning: string;
  grading_details: {
    mcqs: MCQGradingDetail[];
    short_answer: ShortAnswerGradingDetail;
    coding: CodingGradingDetail;
  };
}

export interface HistorySessionRecord {
  submission_id?: string;
  student_id: string;
  concept: ConceptName;
  difficulty: DifficultyLevel;
  bundle_average_score: number;
  mcq_scores: number[];
  short_answer_score: number;
  code_score: number;
  code_status?: string;
  code_execution_status?: string;
  code_tests_passed?: number;
  code_tests_total?: number;
  syntax_preview_passed?: boolean;
  syntax_preview_count?: number;
  next_difficulty: DifficultyLevel;
  scaffolding_reasoning: string;
  timestamp: string;
}

export interface StudentHistoryResponse {
  student_id: string;
  history: HistorySessionRecord[];
}

