/**
 * frontend/src/lib/mock-data/bundle-catalog.ts
 *
 * Unified Question Bundle Catalog for AKT-Project Frontend.
 * Supports Student-Selected Learning and Adaptive Learning across all 10 concepts
 * and 3 difficulty levels (Easy, Medium, Hard).
 *
 * Security & Academic Integrity:
 * - Public question objects contain NO answer keys, NO reference rubrics, and NO expected test outputs.
 * - Evaluation is isolated in a demonstration submission evaluator.
 * - Source data curated from canonical data/reference_answers.json.
 */

export interface PublicMCQOption {
  key: string;
  text: string;
}

export interface PublicMCQQuestion {
  id: string;
  type: "mcq";
  number: number;
  title: string;
  options: PublicMCQOption[];
}

export interface PublicShortAnswerQuestion {
  id: string;
  type: "short_answer";
  number: number;
  title: string;
  maxWords: number;
}

export interface PublicCodingTestCase {
  call: string;
  description: string;
}

export interface PublicCodingQuestion {
  id: string;
  type: "coding";
  number: number;
  title: string;
  starterCode: string;
  testCases: PublicCodingTestCase[];
}

export type PublicQuestion = PublicMCQQuestion | PublicShortAnswerQuestion | PublicCodingQuestion;

export interface PublicConceptBundle {
  concept: string;
  difficulty: "easy" | "medium" | "hard";
  questions: PublicQuestion[];
}

export interface BundleEvaluationResult {
  concept?: string;
  difficulty?: "easy" | "medium" | "hard";
  mcqPassedCount: number;
  mcqAttemptedCount?: number;
  mcqScores?: number[];
  mcqResults: Array<{
    questionIndex: number;
    questionId: string;
    selectedOption: string | null;
    isCorrect: boolean;
    correctOption?: string;
  }>;
  shortAnswerStatus?: "EVALUATED" | "UNAVAILABLE";
  shortAnswerScore?: number | null;
  shortAnswerFeedback?: string;
  codeScore?: number;
  codeStatus?: "PENDING_SECURE_EVALUATION" | "PENDING SECURE EVALUATION" | "SANDBOX_OFFLINE" | "EVALUATED" | string;
  codeExecutionStatus?: "NOT_PERFORMED" | "EXECUTED" | string;
  syntaxPreviewPassed?: boolean;
  syntaxPreviewCount?: number;
  codeFeedback?: string;
  codeRuntimeError?: string | null;
  codeTestResults?: Array<{
    testIndex: number;
    call: string;
    description: string;
    passed: boolean;
    error?: string | null;
    actualRepr?: string | null;
  }>;
  codeTestsPassed: number;
  codeTotalTests: number;
  bundleAveragePercent: number | null;
  isPartialAssessment?: boolean;
  assessmentLabel?: "COMPLETE BUNDLE" | "PARTIAL ASSESSMENT" | "ASSESSMENT UNAVAILABLE";
  scaffoldingReason?: string;
  nextDifficulty?: "easy" | "medium" | "hard";
  saWordCount?: number;
  hasSaResponse?: boolean;
  isCodeModified?: boolean;
}

export const PUBLIC_BUNDLE_CATALOG: Record<string, Record<"easy" | "medium" | "hard", PublicConceptBundle>> = {
  "Variables": {
    "easy": {
      "concept": "Variables",
      "difficulty": "easy",
      "questions": [
        {
          "id": "Variables_MCQ_Easy_1",
          "type": "mcq",
          "number": 1,
          "title": "Which of the following is a valid Python variable name?",
          "options": [
            {
              "key": "A",
              "text": "1st_variable"
            },
            {
              "key": "B",
              "text": "my_variable_1"
            },
            {
              "key": "C",
              "text": "for"
            },
            {
              "key": "D",
              "text": "my-variable"
            }
          ]
        },
        {
          "id": "Variables_MCQ_Easy_2",
          "type": "mcq",
          "number": 2,
          "title": "What is the output of x = 5; x += 3; print(x)?",
          "options": [
            {
              "key": "A",
              "text": "53"
            },
            {
              "key": "B",
              "text": "8"
            },
            {
              "key": "C",
              "text": "5"
            },
            {
              "key": "D",
              "text": "Error"
            }
          ]
        },
        {
          "id": "Variables_MCQ_Easy_3",
          "type": "mcq",
          "number": 3,
          "title": "Which data type is returned by type(3.14) in Python?",
          "options": [
            {
              "key": "A",
              "text": "int"
            },
            {
              "key": "B",
              "text": "str"
            },
            {
              "key": "C",
              "text": "float"
            },
            {
              "key": "D",
              "text": "double"
            }
          ]
        },
        {
          "id": "Variables_SA_Easy_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain what a variable is in Python and why it is used.",
          "maxWords": 120
        },
        {
          "id": "Variables_Code_Easy_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function sum_two_numbers(a, b) that takes two numbers and returns their sum.",
          "starterCode": "def sum_two_numbers(a, b):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "sum_two_numbers(2, 3)",
              "description": "Sum of two positive integers"
            },
            {
              "call": "sum_two_numbers(-1, 1)",
              "description": "Sum of negative and positive"
            },
            {
              "call": "sum_two_numbers(0, 0)",
              "description": "Sum of zeros"
            }
          ]
        }
      ]
    },
    "medium": {
      "concept": "Variables",
      "difficulty": "medium",
      "questions": [
        {
          "id": "Variables_MCQ_Medium_1",
          "type": "mcq",
          "number": 1,
          "title": "What will be the values of a and b after executing: a, b = 10, 20; a, b = b, a + b?",
          "options": [
            {
              "key": "A",
              "text": "a = 20, b = 30"
            },
            {
              "key": "B",
              "text": "a = 10, b = 20"
            },
            {
              "key": "C",
              "text": "a = 20, b = 20"
            },
            {
              "key": "D",
              "text": "a = 30, b = 20"
            }
          ]
        },
        {
          "id": "Variables_MCQ_Medium_2",
          "type": "mcq",
          "number": 2,
          "title": "What is the result of bool([]) and bool('False') in Python?",
          "options": [
            {
              "key": "A",
              "text": "False, False"
            },
            {
              "key": "B",
              "text": "False, True"
            },
            {
              "key": "C",
              "text": "True, True"
            },
            {
              "key": "D",
              "text": "True, False"
            }
          ]
        },
        {
          "id": "Variables_MCQ_Medium_3",
          "type": "mcq",
          "number": 3,
          "title": "Given x = [1, 2]; y = x; y.append(3). What is print(x)?",
          "options": [
            {
              "key": "A",
              "text": "[1, 2]"
            },
            {
              "key": "B",
              "text": "[1, 2, 3]"
            },
            {
              "key": "C",
              "text": "[3]"
            },
            {
              "key": "D",
              "text": "AttributeError"
            }
          ]
        },
        {
          "id": "Variables_SA_Medium_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain dynamic typing in Python and what happens in memory when a variable is reassigned to a different data type.",
          "maxWords": 120
        },
        {
          "id": "Variables_Code_Medium_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function convert_temperature(temp, unit) where unit is 'C' (Celsius) or 'F' (Fahrenheit). If 'C', convert to Fahrenheit (temp * 9/5 + 32). If 'F', convert to Celsius ((temp - 32) * 5/9). Round to 2 decimal places.",
          "starterCode": "def convert_temperature(temp, unit):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "convert_temperature(0, 'C')",
              "description": "Freezing point C to F"
            },
            {
              "call": "convert_temperature(100, 'C')",
              "description": "Boiling point C to F"
            },
            {
              "call": "convert_temperature(32, 'F')",
              "description": "Freezing point F to C"
            }
          ]
        }
      ]
    },
    "hard": {
      "concept": "Variables",
      "difficulty": "hard",
      "questions": [
        {
          "id": "Variables_MCQ_Hard_1",
          "type": "mcq",
          "number": 1,
          "title": "What will happen if you reference a variable before assignment inside a function that defines it as a local variable?",
          "options": [
            {
              "key": "A",
              "text": "It accesses the global variable"
            },
            {
              "key": "B",
              "text": "It raises an UnboundLocalError"
            },
            {
              "key": "C",
              "text": "It returns None"
            },
            {
              "key": "D",
              "text": "It initializes the variable to 0"
            }
          ]
        },
        {
          "id": "Variables_MCQ_Hard_2",
          "type": "mcq",
          "number": 2,
          "title": "In Python, which statement about small integer caching (-5 to 256) and the 'is' operator is true?",
          "options": [
            {
              "key": "A",
              "text": "x = 256; y = 256; x is y evaluates to True"
            },
            {
              "key": "B",
              "text": "x = 256; y = 256; x is y evaluates to False"
            },
            {
              "key": "C",
              "text": "'is' checks for value equality, not identity"
            },
            {
              "key": "D",
              "text": "Small integers are reallocated memory upon every assignment"
            }
          ]
        },
        {
          "id": "Variables_MCQ_Hard_3",
          "type": "mcq",
          "number": 3,
          "title": "What does the 'nonlocal' keyword do in a nested Python function?",
          "options": [
            {
              "key": "A",
              "text": "Declares a variable as global across the entire module"
            },
            {
              "key": "B",
              "text": "Binds a variable to the nearest enclosing non-global scope"
            },
            {
              "key": "C",
              "text": "Prevents the variable from being modified"
            },
            {
              "key": "D",
              "text": "Deletes the variable from the local scope"
            }
          ]
        },
        {
          "id": "Variables_SA_Hard_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain Python's LEGB rule for variable scope resolution and how the 'global' and 'nonlocal' keywords alter this resolution.",
          "maxWords": 120
        },
        {
          "id": "Variables_Code_Hard_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function swap_and_aggregate(data_dict) that takes a dictionary mapping string keys to numeric values, swaps keys and values into a new dict (values become keys), and if duplicate values exist, aggregates the original keys into a sorted list.",
          "starterCode": "def swap_and_aggregate(data_dict):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "swap_and_aggregate({'a': 1, 'b': 2})",
              "description": "Unique values swap directly"
            },
            {
              "call": "swap_and_aggregate({'a': 1, 'b': 1, 'c': 2})",
              "description": "Duplicates aggregated into sorted list"
            },
            {
              "call": "swap_and_aggregate({})",
              "description": "Empty dictionary handling"
            }
          ]
        }
      ]
    }
  },
  "Conditionals": {
    "easy": {
      "concept": "Conditionals",
      "difficulty": "easy",
      "questions": [
        {
          "id": "Conditionals_MCQ_Easy_1",
          "type": "mcq",
          "number": 1,
          "title": "What will bool(0) evaluate to in Python?",
          "options": [
            {
              "key": "A",
              "text": "True"
            },
            {
              "key": "B",
              "text": "False"
            },
            {
              "key": "C",
              "text": "None"
            },
            {
              "key": "D",
              "text": "Error"
            }
          ]
        },
        {
          "id": "Conditionals_MCQ_Easy_2",
          "type": "mcq",
          "number": 2,
          "title": "Which keyword is used for additional conditional checks after 'if' in Python?",
          "options": [
            {
              "key": "A",
              "text": "else if"
            },
            {
              "key": "B",
              "text": "elseif"
            },
            {
              "key": "C",
              "text": "elif"
            },
            {
              "key": "D",
              "text": "otherwise"
            }
          ]
        },
        {
          "id": "Conditionals_MCQ_Easy_3",
          "type": "mcq",
          "number": 3,
          "title": "What is the result of True and not False?",
          "options": [
            {
              "key": "A",
              "text": "True"
            },
            {
              "key": "B",
              "text": "False"
            },
            {
              "key": "C",
              "text": "None"
            },
            {
              "key": "D",
              "text": "Error"
            }
          ]
        },
        {
          "id": "Conditionals_SA_Easy_1",
          "type": "short_answer",
          "number": 4,
          "title": "Describe how an if-elif-else conditional statement controls program execution flow.",
          "maxWords": 120
        },
        {
          "id": "Conditionals_Code_Easy_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function is_even(num) that returns True if a number is even, and False otherwise.",
          "starterCode": "def is_even(num):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "is_even(4)",
              "description": "Even number returns True"
            },
            {
              "call": "is_even(7)",
              "description": "Odd number returns False"
            },
            {
              "call": "is_even(0)",
              "description": "Zero is even"
            }
          ]
        }
      ]
    },
    "medium": {
      "concept": "Conditionals",
      "difficulty": "medium",
      "questions": [
        {
          "id": "Conditionals_MCQ_Medium_1",
          "type": "mcq",
          "number": 1,
          "title": "What is the output of the chained comparison: 1 < 3 > 2 == 2 in Python?",
          "options": [
            {
              "key": "A",
              "text": "True"
            },
            {
              "key": "B",
              "text": "False"
            },
            {
              "key": "C",
              "text": "TypeError"
            },
            {
              "key": "D",
              "text": "SyntaxError"
            }
          ]
        },
        {
          "id": "Conditionals_MCQ_Medium_2",
          "type": "mcq",
          "number": 2,
          "title": "What is the return value of: [] or 'default' in Python?",
          "options": [
            {
              "key": "A",
              "text": "[]"
            },
            {
              "key": "B",
              "text": "'default'"
            },
            {
              "key": "C",
              "text": "True"
            },
            {
              "key": "D",
              "text": "False"
            }
          ]
        },
        {
          "id": "Conditionals_MCQ_Medium_3",
          "type": "mcq",
          "number": 3,
          "title": "What does 'x if condition else y' represent in Python?",
          "options": [
            {
              "key": "A",
              "text": "A syntax error"
            },
            {
              "key": "B",
              "text": "A ternary conditional expression"
            },
            {
              "key": "C",
              "text": "A loop construct"
            },
            {
              "key": "D",
              "text": "A lambda function"
            }
          ]
        },
        {
          "id": "Conditionals_SA_Medium_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain short-circuit evaluation in Python logical operators 'and' and 'or', including what value is returned.",
          "maxWords": 120
        },
        {
          "id": "Conditionals_Code_Medium_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function classify_triangle(a, b, c) that returns 'Equilateral', 'Isosceles', 'Scalene', or 'Invalid' if side lengths cannot form a triangle.",
          "starterCode": "def classify_triangle(a, b, c):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "classify_triangle(3, 3, 3)",
              "description": "All three sides equal"
            },
            {
              "call": "classify_triangle(5, 5, 8)",
              "description": "Two sides equal"
            },
            {
              "call": "classify_triangle(1, 2, 10)",
              "description": "Violates triangle inequality"
            }
          ]
        }
      ]
    },
    "hard": {
      "concept": "Conditionals",
      "difficulty": "hard",
      "questions": [
        {
          "id": "Conditionals_MCQ_Hard_1",
          "type": "mcq",
          "number": 1,
          "title": "How does Python evaluate 'f() or g()' when f() returns a non-empty string?",
          "options": [
            {
              "key": "A",
              "text": "Both f() and g() are evaluated in parallel"
            },
            {
              "key": "B",
              "text": "f() is evaluated and g() is never called due to short-circuiting"
            },
            {
              "key": "C",
              "text": "g() is evaluated first, then f()"
            },
            {
              "key": "D",
              "text": "Both f() and g() must evaluate to booleans or a TypeError is raised"
            }
          ]
        },
        {
          "id": "Conditionals_MCQ_Hard_2",
          "type": "mcq",
          "number": 2,
          "title": "In Python 3.10+ match-case statements, what does the wildcard case _ represent?",
          "options": [
            {
              "key": "A",
              "text": "Matches only None values"
            },
            {
              "key": "B",
              "text": "A catch-all pattern equivalent to a default else branch"
            },
            {
              "key": "C",
              "text": "Matches only single-character strings"
            },
            {
              "key": "D",
              "text": "Raises an unhandled pattern exception"
            }
          ]
        },
        {
          "id": "Conditionals_MCQ_Hard_3",
          "type": "mcq",
          "number": 3,
          "title": "What is the result of: not (True or False and False)?",
          "options": [
            {
              "key": "A",
              "text": "True"
            },
            {
              "key": "B",
              "text": "False"
            },
            {
              "key": "C",
              "text": "None"
            },
            {
              "key": "D",
              "text": "Error"
            }
          ]
        },
        {
          "id": "Conditionals_SA_Hard_1",
          "type": "short_answer",
          "number": 4,
          "title": "Compare Python's if-elif-else branching with Python 3.10's structural pattern matching (match-case), explaining when pattern matching provides advantages.",
          "maxWords": 120
        },
        {
          "id": "Conditionals_Code_Hard_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function validate_password(password) that returns True if password is at least 8 chars long, contains at least one uppercase letter, one lowercase letter, one digit, and one special character from '!@#$%^&*'. Otherwise returns False.",
          "starterCode": "def validate_password(password):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "validate_password('Valid123!')",
              "description": "Meets all criteria"
            },
            {
              "call": "validate_password('weakpass')",
              "description": "Missing digits, uppercase, and special chars"
            },
            {
              "call": "validate_password('Short1!')",
              "description": "Fails length requirement (<8)"
            }
          ]
        }
      ]
    }
  },
  "Loops": {
    "easy": {
      "concept": "Loops",
      "difficulty": "easy",
      "questions": [
        {
          "id": "Loops_MCQ_Easy_1",
          "type": "mcq",
          "number": 1,
          "title": "How many times will 'for i in range(3):' execute?",
          "options": [
            {
              "key": "A",
              "text": "2 times"
            },
            {
              "key": "B",
              "text": "3 times"
            },
            {
              "key": "C",
              "text": "4 times"
            },
            {
              "key": "D",
              "text": "Infinite"
            }
          ]
        },
        {
          "id": "Loops_MCQ_Easy_2",
          "type": "mcq",
          "number": 2,
          "title": "Which statement immediately exits the nearest enclosing loop in Python?",
          "options": [
            {
              "key": "A",
              "text": "continue"
            },
            {
              "key": "B",
              "text": "pass"
            },
            {
              "key": "C",
              "text": "break"
            },
            {
              "key": "D",
              "text": "stop"
            }
          ]
        },
        {
          "id": "Loops_MCQ_Easy_3",
          "type": "mcq",
          "number": 3,
          "title": "What sequence does range(1, 5) produce when iterated over?",
          "options": [
            {
              "key": "A",
              "text": "1, 2, 3, 4, 5"
            },
            {
              "key": "B",
              "text": "1, 2, 3, 4"
            },
            {
              "key": "C",
              "text": "0, 1, 2, 3, 4"
            },
            {
              "key": "D",
              "text": "2, 3, 4, 5"
            }
          ]
        },
        {
          "id": "Loops_SA_Easy_1",
          "type": "short_answer",
          "number": 4,
          "title": "What is the main difference between a for loop and a while loop?",
          "maxWords": 120
        },
        {
          "id": "Loops_Code_Easy_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function sum_n(n) that calculates the sum of integers from 1 to n using a loop.",
          "starterCode": "def sum_n(n):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "sum_n(5)",
              "description": "Sum 1 through 5 is 15"
            },
            {
              "call": "sum_n(1)",
              "description": "Sum 1 is 1"
            },
            {
              "call": "sum_n(0)",
              "description": "Sum 0 is 0"
            }
          ]
        }
      ]
    },
    "medium": {
      "concept": "Loops",
      "difficulty": "medium",
      "questions": [
        {
          "id": "Loops_MCQ_Medium_1",
          "type": "mcq",
          "number": 1,
          "title": "When does the 'else' block attached to a Python 'for' loop execute?",
          "options": [
            {
              "key": "A",
              "text": "Only if the loop was terminated by a break statement"
            },
            {
              "key": "B",
              "text": "When the loop completes normally without encountering a break"
            },
            {
              "key": "C",
              "text": "Whenever an exception occurs inside the loop"
            },
            {
              "key": "D",
              "text": "Exactly once before the loop begins"
            }
          ]
        },
        {
          "id": "Loops_MCQ_Medium_2",
          "type": "mcq",
          "number": 2,
          "title": "What is the output of: list(range(10, 0, -3))?",
          "options": [
            {
              "key": "A",
              "text": "[10, 7, 4, 1]"
            },
            {
              "key": "B",
              "text": "[10, 7, 4, 1, -2]"
            },
            {
              "key": "C",
              "text": "[10, 8, 6, 4, 2]"
            },
            {
              "key": "D",
              "text": "[]"
            }
          ]
        },
        {
          "id": "Loops_MCQ_Medium_3",
          "type": "mcq",
          "number": 3,
          "title": "What does the 'continue' keyword do when encountered inside a loop?",
          "options": [
            {
              "key": "A",
              "text": "Terminates the loop completely"
            },
            {
              "key": "B",
              "text": "Skips the rest of the current iteration and jumps to the next iteration"
            },
            {
              "key": "C",
              "text": "Restarts the loop from the initial counter"
            },
            {
              "key": "D",
              "text": "Pauses loop execution indefinitely"
            }
          ]
        },
        {
          "id": "Loops_SA_Medium_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain the behavior and practical use cases of an 'else' block attached to a for or while loop in Python.",
          "maxWords": 120
        },
        {
          "id": "Loops_Code_Medium_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function count_vowels(text) that uses a loop to count the number of vowels (a, e, i, o, u, case-insensitive) in a given string.",
          "starterCode": "def count_vowels(text):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "count_vowels('Hello World')",
              "description": "3 vowels in Hello World"
            },
            {
              "call": "count_vowels('PYTHON')",
              "description": "1 vowel in PYTHON"
            },
            {
              "call": "count_vowels('rhythm')",
              "description": "0 vowels in rhythm"
            }
          ]
        }
      ]
    },
    "hard": {
      "concept": "Loops",
      "difficulty": "hard",
      "questions": [
        {
          "id": "Loops_MCQ_Hard_1",
          "type": "mcq",
          "number": 1,
          "title": "What happens if you mutate a list (e.g. lst.pop(0)) while directly iterating over it with 'for item in lst:'?",
          "options": [
            {
              "key": "A",
              "text": "Python raises a ConcurrentModificationException"
            },
            {
              "key": "B",
              "text": "Elements are skipped because the internal iterator index advances normally"
            },
            {
              "key": "C",
              "text": "The loop automatically creates a frozen snapshot copy"
            },
            {
              "key": "D",
              "text": "The loop executes in reverse order"
            }
          ]
        },
        {
          "id": "Loops_MCQ_Hard_2",
          "type": "mcq",
          "number": 2,
          "title": "Which construct allows iterating over two iterables simultaneously while stopping when the shortest is exhausted?",
          "options": [
            {
              "key": "A",
              "text": "enumerate()"
            },
            {
              "key": "B",
              "text": "zip()"
            },
            {
              "key": "C",
              "text": "itertools.cycle()"
            },
            {
              "key": "D",
              "text": "chain()"
            }
          ]
        },
        {
          "id": "Loops_MCQ_Hard_3",
          "type": "mcq",
          "number": 3,
          "title": "What is the return value of next(iter([]), 'empty')?",
          "options": [
            {
              "key": "A",
              "text": "Raises StopIteration"
            },
            {
              "key": "B",
              "text": "None"
            },
            {
              "key": "C",
              "text": "'empty'"
            },
            {
              "key": "D",
              "text": "[]"
            }
          ]
        },
        {
          "id": "Loops_SA_Hard_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain the iterator protocol in Python (__iter__ and __next__) and how 'for' loops utilize this protocol under the hood.",
          "maxWords": 120
        },
        {
          "id": "Loops_Code_Hard_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function find_primes(n) that uses nested loops to return a list of all prime numbers less than or equal to n.",
          "starterCode": "def find_primes(n):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "find_primes(10)",
              "description": "Primes up to 10"
            },
            {
              "call": "find_primes(20)",
              "description": "Primes up to 20"
            },
            {
              "call": "find_primes(1)",
              "description": "No primes <= 1"
            }
          ]
        }
      ]
    }
  },
  "Functions": {
    "easy": {
      "concept": "Functions",
      "difficulty": "easy",
      "questions": [
        {
          "id": "Functions_MCQ_Easy_1",
          "type": "mcq",
          "number": 1,
          "title": "Which keyword is used to define a function in Python?",
          "options": [
            {
              "key": "A",
              "text": "function"
            },
            {
              "key": "B",
              "text": "def"
            },
            {
              "key": "C",
              "text": "fn"
            },
            {
              "key": "D",
              "text": "define"
            }
          ]
        },
        {
          "id": "Functions_MCQ_Easy_2",
          "type": "mcq",
          "number": 2,
          "title": "What value does a function return by default if no return statement is specified?",
          "options": [
            {
              "key": "A",
              "text": "0"
            },
            {
              "key": "B",
              "text": "False"
            },
            {
              "key": "C",
              "text": "None"
            },
            {
              "key": "D",
              "text": "Undefined"
            }
          ]
        },
        {
          "id": "Functions_MCQ_Easy_3",
          "type": "mcq",
          "number": 3,
          "title": "What are default parameter values in Python functions?",
          "options": [
            {
              "key": "A",
              "text": "Values assigned when no argument is provided"
            },
            {
              "key": "B",
              "text": "Global variables"
            },
            {
              "key": "C",
              "text": "Constant values that cannot change"
            },
            {
              "key": "D",
              "text": "Mandatory arguments"
            }
          ]
        },
        {
          "id": "Functions_SA_Easy_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain the purpose of functions in software development and the concept of parameters versus arguments.",
          "maxWords": 120
        },
        {
          "id": "Functions_Code_Easy_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function greet(name) that returns 'Hello, ' followed by the name.",
          "starterCode": "def greet(name):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "greet('Alice')",
              "description": "Greeting Alice"
            },
            {
              "call": "greet('Bob')",
              "description": "Greeting Bob"
            },
            {
              "call": "greet(123)",
              "description": "Greeting integer converted to string"
            }
          ]
        }
      ]
    },
    "medium": {
      "concept": "Functions",
      "difficulty": "medium",
      "questions": [
        {
          "id": "Functions_MCQ_Medium_1",
          "type": "mcq",
          "number": 1,
          "title": "What does *args collect positional arguments into inside a Python function?",
          "options": [
            {
              "key": "A",
              "text": "A list"
            },
            {
              "key": "B",
              "text": "A tuple"
            },
            {
              "key": "C",
              "text": "A set"
            },
            {
              "key": "D",
              "text": "A dictionary"
            }
          ]
        },
        {
          "id": "Functions_MCQ_Medium_2",
          "type": "mcq",
          "number": 2,
          "title": "What does **kwargs collect keyword arguments into inside a Python function?",
          "options": [
            {
              "key": "A",
              "text": "A list"
            },
            {
              "key": "B",
              "text": "A tuple"
            },
            {
              "key": "C",
              "text": "A dictionary"
            },
            {
              "key": "D",
              "text": "A string"
            }
          ]
        },
        {
          "id": "Functions_MCQ_Medium_3",
          "type": "mcq",
          "number": 3,
          "title": "What is the output of: (lambda x, y: x * y + 2)(3, 4)?",
          "options": [
            {
              "key": "A",
              "text": "14"
            },
            {
              "key": "B",
              "text": "18"
            },
            {
              "key": "C",
              "text": "24"
            },
            {
              "key": "D",
              "text": "Error"
            }
          ]
        },
        {
          "id": "Functions_SA_Medium_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain how *args and **kwargs enable variable-length argument passing in Python.",
          "maxWords": 120
        },
        {
          "id": "Functions_Code_Medium_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function factorial(n) that calculates and returns the factorial of a non-negative integer n.",
          "starterCode": "def factorial(n):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "factorial(5)",
              "description": "5! = 120"
            },
            {
              "call": "factorial(0)",
              "description": "0! = 1"
            },
            {
              "call": "factorial(1)",
              "description": "1! = 1"
            }
          ]
        }
      ]
    },
    "hard": {
      "concept": "Functions",
      "difficulty": "hard",
      "questions": [
        {
          "id": "Functions_MCQ_Hard_1",
          "type": "mcq",
          "number": 1,
          "title": "Why is using a mutable default argument like 'def f(lst=[]):' considered dangerous in Python?",
          "options": [
            {
              "key": "A",
              "text": "It causes an immediate SyntaxError"
            },
            {
              "key": "B",
              "text": "The default list object is created once at function definition time and shared across subsequent calls"
            },
            {
              "key": "C",
              "text": "Python creates a new copy of the list on every call, consuming excessive memory"
            },
            {
              "key": "D",
              "text": "Elements inside the list cannot be modified"
            }
          ]
        },
        {
          "id": "Functions_MCQ_Hard_2",
          "type": "mcq",
          "number": 2,
          "title": "In Python decorators, what is the role of functools.wraps?",
          "options": [
            {
              "key": "A",
              "text": "Executes the function in an isolated process"
            },
            {
              "key": "B",
              "text": "Preserves original function metadata (__name__, __doc__, annotations)"
            },
            {
              "key": "C",
              "text": "Automatically caches return values"
            },
            {
              "key": "D",
              "text": "Converts synchronous functions into coroutines"
            }
          ]
        },
        {
          "id": "Functions_MCQ_Hard_3",
          "type": "mcq",
          "number": 3,
          "title": "What is the closure variable accessed via func.__closure__[0].cell_contents in Python?",
          "options": [
            {
              "key": "A",
              "text": "Global variables referenced by func"
            },
            {
              "key": "B",
              "text": "Free variables bound from an enclosing lexical scope"
            },
            {
              "key": "C",
              "text": "Default argument parameters"
            },
            {
              "key": "D",
              "text": "Built-in functions available to func"
            }
          ]
        },
        {
          "id": "Functions_SA_Hard_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain what a closure is in Python, how variable binding occurs, and why the mutable default argument pattern causes bugs.",
          "maxWords": 120
        },
        {
          "id": "Functions_Code_Hard_1",
          "type": "coding",
          "number": 5,
          "title": "Write a higher-order function compose(f, g) that returns a new function representing the composition f(g(x)).",
          "starterCode": "def compose(f, g):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "compose(lambda x: x + 1, lambda x: x * 2)(3)",
              "description": "f(g(3)) = (3*2)+1 = 7"
            },
            {
              "call": "compose(str, lambda x: x ** 2)(5)",
              "description": "str(5^2) = '25'"
            },
            {
              "call": "compose(abs, lambda x: x - 10)(3)",
              "description": "abs(3 - 10) = 7"
            }
          ]
        }
      ]
    }
  },
  "Arrays": {
    "easy": {
      "concept": "Arrays",
      "difficulty": "easy",
      "questions": [
        {
          "id": "Arrays_MCQ_Easy_1",
          "type": "mcq",
          "number": 1,
          "title": "How do you access the last element of a Python list 'lst'?",
          "options": [
            {
              "key": "A",
              "text": "lst[0]"
            },
            {
              "key": "B",
              "text": "lst[-1]"
            },
            {
              "key": "C",
              "text": "lst[len(lst)]"
            },
            {
              "key": "D",
              "text": "lst.last()"
            }
          ]
        },
        {
          "id": "Arrays_MCQ_Easy_2",
          "type": "mcq",
          "number": 2,
          "title": "Which list method adds an item to the end of the list in Python?",
          "options": [
            {
              "key": "A",
              "text": "append()"
            },
            {
              "key": "B",
              "text": "add()"
            },
            {
              "key": "C",
              "text": "push()"
            },
            {
              "key": "D",
              "text": "insert()"
            }
          ]
        },
        {
          "id": "Arrays_MCQ_Easy_3",
          "type": "mcq",
          "number": 3,
          "title": "What is the result of [1, 2] + [3, 4] in Python?",
          "options": [
            {
              "key": "A",
              "text": "[4, 6]"
            },
            {
              "key": "B",
              "text": "[1, 2, 3, 4]"
            },
            {
              "key": "C",
              "text": "[[1, 2], [3, 4]]"
            },
            {
              "key": "D",
              "text": "Error"
            }
          ]
        },
        {
          "id": "Arrays_SA_Easy_1",
          "type": "short_answer",
          "number": 4,
          "title": "Describe what a list or array is in Python and how indexing works.",
          "maxWords": 120
        },
        {
          "id": "Arrays_Code_Easy_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function find_max(lst) that returns the maximum numerical value in a list.",
          "starterCode": "def find_max(lst):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "find_max([1, 5, 3, 9, 2])",
              "description": "Max value in list"
            },
            {
              "call": "find_max([-10, -5, -20])",
              "description": "Max among negative numbers"
            },
            {
              "call": "find_max([42])",
              "description": "Single element list"
            }
          ]
        }
      ]
    },
    "medium": {
      "concept": "Arrays",
      "difficulty": "medium",
      "questions": [
        {
          "id": "Arrays_MCQ_Medium_1",
          "type": "mcq",
          "number": 1,
          "title": "What is the result of lst = [0, 1, 2, 3, 4, 5]; print(lst[1:5:2])?",
          "options": [
            {
              "key": "A",
              "text": "[1, 3]"
            },
            {
              "key": "B",
              "text": "[1, 3, 5]"
            },
            {
              "key": "C",
              "text": "[0, 2, 4]"
            },
            {
              "key": "D",
              "text": "[1, 2, 3, 4]"
            }
          ]
        },
        {
          "id": "Arrays_MCQ_Medium_2",
          "type": "mcq",
          "number": 2,
          "title": "What is the output of [x**2 for x in range(5) if x % 2 != 0]?",
          "options": [
            {
              "key": "A",
              "text": "[1, 9]"
            },
            {
              "key": "B",
              "text": "[0, 4, 16]"
            },
            {
              "key": "C",
              "text": "[1, 4, 9]"
            },
            {
              "key": "D",
              "text": "[1, 9, 25]"
            }
          ]
        },
        {
          "id": "Arrays_MCQ_Medium_3",
          "type": "mcq",
          "number": 3,
          "title": "What does lst.pop() do when called without arguments?",
          "options": [
            {
              "key": "A",
              "text": "Removes and returns the first element"
            },
            {
              "key": "B",
              "text": "Removes and returns the last element"
            },
            {
              "key": "C",
              "text": "Clears all elements from the list"
            },
            {
              "key": "D",
              "text": "Returns the last element without removing it"
            }
          ]
        },
        {
          "id": "Arrays_SA_Medium_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain Python list slicing syntax [start:stop:step] and how negative step values reverse or step through sequences.",
          "maxWords": 120
        },
        {
          "id": "Arrays_Code_Medium_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function remove_duplicates(lst) that removes duplicate values from a list while preserving their original order of appearance.",
          "starterCode": "def remove_duplicates(lst):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "remove_duplicates([1, 2, 2, 3, 4, 3, 5])",
              "description": "Duplicates removed in order"
            },
            {
              "call": "remove_duplicates(['a', 'b', 'a', 'c'])",
              "description": "String duplicates removed in order"
            },
            {
              "call": "remove_duplicates([])",
              "description": "Empty list returns empty list"
            }
          ]
        }
      ]
    },
    "hard": {
      "concept": "Arrays",
      "difficulty": "hard",
      "questions": [
        {
          "id": "Arrays_MCQ_Hard_1",
          "type": "mcq",
          "number": 1,
          "title": "What is the result of creating a 2D list with row = [0]*2; matrix = [row]*2; matrix[0][0] = 99?",
          "options": [
            {
              "key": "A",
              "text": "[[99, 0], [0, 0]]"
            },
            {
              "key": "B",
              "text": "[[99, 0], [99, 0]]"
            },
            {
              "key": "C",
              "text": "[[99, 99], [0, 0]]"
            },
            {
              "key": "D",
              "text": "[[99, 99], [99, 99]]"
            }
          ]
        },
        {
          "id": "Arrays_MCQ_Hard_2",
          "type": "mcq",
          "number": 2,
          "title": "What is the average time complexity of inserting an element at the beginning of a Python list (lst.insert(0, val)) versus appending (lst.append(val))?",
          "options": [
            {
              "key": "A",
              "text": "O(1) for insert(0), O(N) for append"
            },
            {
              "key": "B",
              "text": "O(N) for insert(0), O(1) amortized for append"
            },
            {
              "key": "C",
              "text": "O(log N) for both"
            },
            {
              "key": "D",
              "text": "O(N) for both"
            }
          ]
        },
        {
          "id": "Arrays_MCQ_Hard_3",
          "type": "mcq",
          "number": 3,
          "title": "What is the difference between copy.copy() and copy.deepcopy() on a nested list?",
          "options": [
            {
              "key": "A",
              "text": "copy() creates a shallow copy where inner lists are still shared; deepcopy() recursively copies all nested objects"
            },
            {
              "key": "B",
              "text": "copy() copies values, deepcopy() copies types"
            },
            {
              "key": "C",
              "text": "deepcopy() is faster than copy()"
            },
            {
              "key": "D",
              "text": "copy() works only on integers"
            }
          ]
        },
        {
          "id": "Arrays_SA_Hard_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain why lists in Python are implemented as dynamic arrays of pointers, and how this impacts memory usage and algorithmic time complexity for append vs insert operations.",
          "maxWords": 120
        },
        {
          "id": "Arrays_Code_Hard_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function rotate_list(lst, k) that rotates a list to the right by k positions in-place or returning a new list. For example, [1, 2, 3, 4, 5] rotated by k=2 becomes [4, 5, 1, 2, 3].",
          "starterCode": "def rotate_list(lst, k):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "rotate_list([1, 2, 3, 4, 5], 2)",
              "description": "Rotate right by 2"
            },
            {
              "call": "rotate_list([1, 2, 3], 4)",
              "description": "Rotate right by k > length (4 % 3 = 1)"
            },
            {
              "call": "rotate_list([1, 2, 3], 0)",
              "description": "Rotate right by 0"
            }
          ]
        }
      ]
    }
  },
  "Syntax": {
    "easy": {
      "concept": "Syntax",
      "difficulty": "easy",
      "questions": [
        {
          "id": "Syntax_MCQ_Easy_1",
          "type": "mcq",
          "number": 1,
          "title": "How are code blocks demarcated in Python?",
          "options": [
            {
              "key": "A",
              "text": "Curly braces {}"
            },
            {
              "key": "B",
              "text": "Indentation"
            },
            {
              "key": "C",
              "text": "Parentheses ()"
            },
            {
              "key": "D",
              "text": "End keywords"
            }
          ]
        },
        {
          "id": "Syntax_MCQ_Easy_2",
          "type": "mcq",
          "number": 2,
          "title": "Which character begins a single-line comment in Python?",
          "options": [
            {
              "key": "A",
              "text": "//"
            },
            {
              "key": "B",
              "text": "/*"
            },
            {
              "key": "C",
              "text": "#"
            },
            {
              "key": "D",
              "text": "--"
            }
          ]
        },
        {
          "id": "Syntax_MCQ_Easy_3",
          "type": "mcq",
          "number": 3,
          "title": "What error is raised when code indentation is inconsistent?",
          "options": [
            {
              "key": "A",
              "text": "SyntaxError"
            },
            {
              "key": "B",
              "text": "IndentationError"
            },
            {
              "key": "C",
              "text": "TypeError"
            },
            {
              "key": "D",
              "text": "ValueError"
            }
          ]
        },
        {
          "id": "Syntax_SA_Easy_1",
          "type": "short_answer",
          "number": 4,
          "title": "Why is indentation essential in Python syntax compared to languages like C or Java?",
          "maxWords": 120
        },
        {
          "id": "Syntax_Code_Easy_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function fix_syntax() that cleans whitespace and returns True.",
          "starterCode": "def fix_syntax():\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "fix_syntax()",
              "description": "Syntax check returns True"
            }
          ]
        }
      ]
    },
    "medium": {
      "concept": "Syntax",
      "difficulty": "medium",
      "questions": [
        {
          "id": "Syntax_MCQ_Medium_2",
          "type": "mcq",
          "number": 1,
          "title": "What is the prefix used for raw string literals where escape characters like \\n are treated as literal characters?",
          "options": [
            {
              "key": "A",
              "text": "f"
            },
            {
              "key": "B",
              "text": "r"
            },
            {
              "key": "C",
              "text": "b"
            },
            {
              "key": "D",
              "text": "u"
            }
          ]
        },
        {
          "id": "Syntax_MCQ_Medium_1",
          "type": "mcq",
          "number": 2,
          "title": "Which statement allows breaking a long line of code across multiple lines without a backslash?",
          "options": [
            {
              "key": "A",
              "text": "Wrapping the expression in parentheses ()"
            },
            {
              "key": "B",
              "text": "Semicolons ;"
            },
            {
              "key": "C",
              "text": "Double quotes \"\""
            },
            {
              "key": "D",
              "text": "Using the continue statement"
            }
          ]
        },
        {
          "id": "Syntax_MCQ_Medium_3",
          "type": "mcq",
          "number": 3,
          "title": "What is the syntax for formatted string literals (f-strings) introduced in Python 3.6?",
          "options": [
            {
              "key": "A",
              "text": "f\"{expression}\""
            },
            {
              "key": "B",
              "text": "format(expression)"
            },
            {
              "key": "C",
              "text": "%s % expression"
            },
            {
              "key": "D",
              "text": "${expression}"
            }
          ]
        },
        {
          "id": "Syntax_SA_Medium_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain the difference between SyntaxError and runtime exceptions (like TypeError or ValueError) in Python.",
          "maxWords": 120
        },
        {
          "id": "Syntax_Code_Medium_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function parse_key_values(kv_str) that parses a string like 'name=Alice;age=30;city=London' into a Python dictionary.",
          "starterCode": "def parse_key_values(kv_str):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "parse_key_values('name=Alice;age=30')",
              "description": "Key value parsing"
            },
            {
              "call": "parse_key_values('x=10')",
              "description": "Single key value pair"
            },
            {
              "call": "parse_key_values('')",
              "description": "Empty string returns empty dict"
            }
          ]
        }
      ]
    },
    "hard": {
      "concept": "Syntax",
      "difficulty": "hard",
      "questions": [
        {
          "id": "Syntax_MCQ_Hard_1",
          "type": "mcq",
          "number": 1,
          "title": "What does the walrus operator ':=' do in Python syntax?",
          "options": [
            {
              "key": "A",
              "text": "Checks for type equivalence"
            },
            {
              "key": "B",
              "text": "Performs assignment expression within larger expressions"
            },
            {
              "key": "C",
              "text": "Declares an immutable constant"
            },
            {
              "key": "D",
              "text": "Performs integer division and assignment"
            }
          ]
        },
        {
          "id": "Syntax_MCQ_Hard_2",
          "type": "mcq",
          "number": 2,
          "title": "In Python function signatures, what does a bare asterisk '*' parameter denote (e.g. def f(a, *, b):)?",
          "options": [
            {
              "key": "A",
              "text": "Accepts arbitrary positional arguments"
            },
            {
              "key": "B",
              "text": "Indicates that all subsequent arguments must be passed as keyword-only arguments"
            },
            {
              "key": "C",
              "text": "Multiplies default values"
            },
            {
              "key": "D",
              "text": "Marks parameters as optional"
            }
          ]
        },
        {
          "id": "Syntax_MCQ_Hard_3",
          "type": "mcq",
          "number": 3,
          "title": "What is the purpose of the '__all__' variable in a Python module's syntax?",
          "options": [
            {
              "key": "A",
              "text": "Lists all installed dependencies"
            },
            {
              "key": "B",
              "text": "Defines the public symbols exported when 'from module import *' is used"
            },
            {
              "key": "C",
              "text": "Prevents the module from being imported"
            },
            {
              "key": "D",
              "text": "Automatically executes tests on import"
            }
          ]
        },
        {
          "id": "Syntax_SA_Hard_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain the syntax and practical benefits of the walrus operator (:=) and positional-only parameter markers (/ and *) in Python signatures.",
          "maxWords": 120
        },
        {
          "id": "Syntax_Code_Hard_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function safe_eval_math(expr) that safely parses and computes simple binary arithmetic expressions 'A + B', 'A - B', 'A * B', or 'A / B' where A and B are floats. Returns float or 'DivisionByZero' or 'InvalidSyntax'.",
          "starterCode": "def safe_eval_math(expr):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "safe_eval_math('10 + 5')",
              "description": "Addition"
            },
            {
              "call": "safe_eval_math('8 / 0')",
              "description": "Zero division handling"
            },
            {
              "call": "safe_eval_math('bad expr')",
              "description": "Syntax error handling"
            }
          ]
        }
      ]
    }
  },
  "OOP": {
    "easy": {
      "concept": "OOP",
      "difficulty": "easy",
      "questions": [
        {
          "id": "OOP_MCQ_Easy_1",
          "type": "mcq",
          "number": 1,
          "title": "Which keyword is used to create a class in Python?",
          "options": [
            {
              "key": "A",
              "text": "object"
            },
            {
              "key": "B",
              "text": "struct"
            },
            {
              "key": "C",
              "text": "class"
            },
            {
              "key": "D",
              "text": "type"
            }
          ]
        },
        {
          "id": "OOP_MCQ_Easy_2",
          "type": "mcq",
          "number": 2,
          "title": "What parameter must be explicitly passed as the first argument to instance methods in Python classes?",
          "options": [
            {
              "key": "A",
              "text": "this"
            },
            {
              "key": "B",
              "text": "self"
            },
            {
              "key": "C",
              "text": "super"
            },
            {
              "key": "D",
              "text": "cls"
            }
          ]
        },
        {
          "id": "OOP_MCQ_Easy_3",
          "type": "mcq",
          "number": 3,
          "title": "What is the special constructor method name in Python classes?",
          "options": [
            {
              "key": "A",
              "text": "__init__"
            },
            {
              "key": "B",
              "text": "__construct__"
            },
            {
              "key": "C",
              "text": "__new__"
            },
            {
              "key": "D",
              "text": "class_init"
            }
          ]
        },
        {
          "id": "OOP_SA_Easy_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain object-oriented programming concepts in Python, specifically classes and objects.",
          "maxWords": 120
        },
        {
          "id": "OOP_Code_Easy_1",
          "type": "coding",
          "number": 5,
          "title": "Write a class Person with an __init__(self, name) method and a get_name(self) method.",
          "starterCode": "class Person:\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "Person('Alice').get_name()",
              "description": "Person get_name returns Alice"
            },
            {
              "call": "Person('Bob').get_name()",
              "description": "Person get_name returns Bob"
            }
          ]
        }
      ]
    },
    "medium": {
      "concept": "OOP",
      "difficulty": "medium",
      "questions": [
        {
          "id": "OOP_MCQ_Medium_1",
          "type": "mcq",
          "number": 1,
          "title": "What is the difference between a class attribute and an instance attribute in Python?",
          "options": [
            {
              "key": "A",
              "text": "Class attributes are shared across all instances; instance attributes are unique to each instance"
            },
            {
              "key": "B",
              "text": "Class attributes can only be integers"
            },
            {
              "key": "C",
              "text": "Instance attributes must be declared outside any method"
            },
            {
              "key": "D",
              "text": "Class attributes are private by default"
            }
          ]
        },
        {
          "id": "OOP_MCQ_Medium_2",
          "type": "mcq",
          "number": 2,
          "title": "Which built-in function checks whether an object is an instance of a specified class or its subclasses?",
          "options": [
            {
              "key": "A",
              "text": "typeof()"
            },
            {
              "key": "B",
              "text": "isinstance()"
            },
            {
              "key": "C",
              "text": "issubclass()"
            },
            {
              "key": "D",
              "text": "hasinstance()"
            }
          ]
        },
        {
          "id": "OOP_MCQ_Medium_3",
          "type": "mcq",
          "number": 3,
          "title": "What decorator turns an instance method into a getter property that can be accessed without parentheses?",
          "options": [
            {
              "key": "A",
              "text": "@getter"
            },
            {
              "key": "B",
              "text": "@property"
            },
            {
              "key": "C",
              "text": "@accessor"
            },
            {
              "key": "D",
              "text": "@attribute"
            }
          ]
        },
        {
          "id": "OOP_SA_Medium_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain inheritance in Python and how the super() function allows subclasses to extend parent class behavior.",
          "maxWords": 120
        },
        {
          "id": "OOP_Code_Medium_1",
          "type": "coding",
          "number": 5,
          "title": "Write a class BankAccount with methods deposit(amount), withdraw(amount), and get_balance(). Initial balance should be 0. Withdraw should return False if insufficient funds, else True.",
          "starterCode": "class BankAccount:\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "acc = BankAccount(); acc.deposit(100); acc.withdraw(30); acc.get_balance()",
              "description": "Deposit and valid withdraw"
            },
            {
              "call": "acc = BankAccount(); acc.withdraw(50)",
              "description": "Withdraw with insufficient funds returns False"
            }
          ]
        }
      ]
    },
    "hard": {
      "concept": "OOP",
      "difficulty": "hard",
      "questions": [
        {
          "id": "OOP_MCQ_Hard_1",
          "type": "mcq",
          "number": 1,
          "title": "How does Python handle private attributes with double leading underscores (e.g., __secret) inside a class?",
          "options": [
            {
              "key": "A",
              "text": "Raises a runtime error if accessed outside"
            },
            {
              "key": "B",
              "text": "Performs name mangling by rewriting the attribute name to _ClassName__secret"
            },
            {
              "key": "C",
              "text": "Encrypts the variable in bytecode"
            },
            {
              "key": "D",
              "text": "Restricts access via OS-level memory locks"
            }
          ]
        },
        {
          "id": "OOP_MCQ_Hard_2",
          "type": "mcq",
          "number": 2,
          "title": "What algorithm does Python use to determine Method Resolution Order (MRO) in multiple inheritance?",
          "options": [
            {
              "key": "A",
              "text": "Depth-First Search (DFS)"
            },
            {
              "key": "B",
              "text": "C3 Linearization Algorithm"
            },
            {
              "key": "C",
              "text": "Breadth-First Search (BFS)"
            },
            {
              "key": "D",
              "text": "Dijkstra's Algorithm"
            }
          ]
        },
        {
          "id": "OOP_MCQ_Hard_3",
          "type": "mcq",
          "number": 3,
          "title": "What is the primary difference between @classmethod and @staticmethod in Python?",
          "options": [
            {
              "key": "A",
              "text": "@classmethod receives the class 'cls' as its first parameter; @staticmethod receives neither 'self' nor 'cls'"
            },
            {
              "key": "B",
              "text": "@staticmethod can only access global variables"
            },
            {
              "key": "C",
              "text": "@classmethod cannot be called on an instance"
            },
            {
              "key": "D",
              "text": "@staticmethod cannot return any value"
            }
          ]
        },
        {
          "id": "OOP_SA_Hard_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain Python's Method Resolution Order (MRO) using C3 Linearization in multiple inheritance, and describe how __new__ differs from __init__.",
          "maxWords": 120
        },
        {
          "id": "OOP_Code_Hard_1",
          "type": "coding",
          "number": 5,
          "title": "Create a base class Vehicle(brand, model) and a subclass ElectricCar(brand, model, battery_kwh) that has a method get_specs() returning a dict {'brand': ..., 'model': ..., 'battery_kwh': ...}.",
          "starterCode": "class Vehicle:\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "ElectricCar('Tesla', 'Model 3', 75).get_specs()",
              "description": "Inheritance specs dictionary"
            }
          ]
        }
      ]
    }
  },
  "Dictionaries": {
    "easy": {
      "concept": "Dictionaries",
      "difficulty": "easy",
      "questions": [
        {
          "id": "Dictionaries_MCQ_Easy_1",
          "type": "mcq",
          "number": 1,
          "title": "Which syntax is used to initialize an empty dictionary in Python?",
          "options": [
            {
              "key": "A",
              "text": "[]"
            },
            {
              "key": "B",
              "text": "{}"
            },
            {
              "key": "C",
              "text": "()"
            },
            {
              "key": "D",
              "text": "set()"
            }
          ]
        },
        {
          "id": "Dictionaries_MCQ_Easy_2",
          "type": "mcq",
          "number": 2,
          "title": "Which method retrieves a value for a key without raising a KeyError if the key does not exist?",
          "options": [
            {
              "key": "A",
              "text": "dict.pop()"
            },
            {
              "key": "B",
              "text": "dict.fetch()"
            },
            {
              "key": "C",
              "text": "dict.get()"
            },
            {
              "key": "D",
              "text": "dict.find()"
            }
          ]
        },
        {
          "id": "Dictionaries_MCQ_Easy_3",
          "type": "mcq",
          "number": 3,
          "title": "Which of the following can be used as a key in a Python dictionary?",
          "options": [
            {
              "key": "A",
              "text": "A list [1, 2]"
            },
            {
              "key": "B",
              "text": "A dictionary {\"a\": 1}"
            },
            {
              "key": "C",
              "text": "A tuple (\"apple\", 42)"
            },
            {
              "key": "D",
              "text": "A set {1, 2}"
            }
          ]
        },
        {
          "id": "Dictionaries_SA_Easy_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain what a dictionary is in Python, how it stores data as key-value pairs, and how to access values.",
          "maxWords": 120
        },
        {
          "id": "Dictionaries_Code_Easy_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function count_char_frequencies(text) that counts the frequency of each character in a given string text and returns a dictionary.",
          "starterCode": "def count_char_frequencies(text):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "count_char_frequencies(\"apple\")",
              "description": "Frequencies of apple"
            },
            {
              "call": "count_char_frequencies(\"banana\")",
              "description": "Frequencies of banana"
            },
            {
              "call": "count_char_frequencies(\"\")",
              "description": "Empty string frequency"
            }
          ]
        }
      ]
    },
    "medium": {
      "concept": "Dictionaries",
      "difficulty": "medium",
      "questions": [
        {
          "id": "Dictionaries_MCQ_Medium_1",
          "type": "mcq",
          "number": 1,
          "title": "What is the result of the dictionary comprehension {x: x * 2 for x in (1, 2, 3)}?",
          "options": [
            {
              "key": "A",
              "text": "{1: 2, 2: 4, 3: 6}"
            },
            {
              "key": "B",
              "text": "[2, 4, 6]"
            },
            {
              "key": "C",
              "text": "{(1, 2), (2, 4), (3, 6)}"
            },
            {
              "key": "D",
              "text": "{2, 4, 6}"
            }
          ]
        },
        {
          "id": "Dictionaries_MCQ_Medium_2",
          "type": "mcq",
          "number": 2,
          "title": "Which dictionary method returns a dynamic view of all key-value pairs as tuples?",
          "options": [
            {
              "key": "A",
              "text": "dict.pairs()"
            },
            {
              "key": "B",
              "text": "dict.items()"
            },
            {
              "key": "C",
              "text": "dict.entries()"
            },
            {
              "key": "D",
              "text": "dict.values()"
            }
          ]
        },
        {
          "id": "Dictionaries_MCQ_Medium_3",
          "type": "mcq",
          "number": 3,
          "title": "What does dict.setdefault(key, default) do if key is already present in the dictionary?",
          "options": [
            {
              "key": "A",
              "text": "Overwrites the existing value with default"
            },
            {
              "key": "B",
              "text": "Returns the existing value and leaves the dictionary unchanged"
            },
            {
              "key": "C",
              "text": "Raises a KeyError exception"
            },
            {
              "key": "D",
              "text": "Removes the key from the dictionary"
            }
          ]
        },
        {
          "id": "Dictionaries_SA_Medium_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain the difference between dict[key] and dict.get(key, default), and describe how dictionary comprehensions work.",
          "maxWords": 120
        },
        {
          "id": "Dictionaries_Code_Medium_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function merge_inventory(inv1, inv2) that merges two inventory dictionaries by summing the counts of matching items.",
          "starterCode": "def merge_inventory(inv1, inv2):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "merge_inventory({\"apples\": 5, \"oranges\": 3}, {\"apples\": 2, \"bananas\": 4})",
              "description": "Merge overlapping inventories"
            },
            {
              "call": "merge_inventory({\"a\": 10}, {})",
              "description": "Merge with empty inventory"
            },
            {
              "call": "merge_inventory({\"x\": 1, \"y\": 2}, {\"x\": 3, \"y\": 4})",
              "description": "Merge all overlapping keys"
            }
          ]
        }
      ]
    },
    "hard": {
      "concept": "Dictionaries",
      "difficulty": "hard",
      "questions": [
        {
          "id": "Dictionaries_MCQ_Hard_1",
          "type": "mcq",
          "number": 1,
          "title": "What is the average-case time complexity of key lookup, insertion, and deletion in a Python dictionary?",
          "options": [
            {
              "key": "A",
              "text": "O(log n)"
            },
            {
              "key": "B",
              "text": "O(1)"
            },
            {
              "key": "C",
              "text": "O(n)"
            },
            {
              "key": "D",
              "text": "O(n log n)"
            }
          ]
        },
        {
          "id": "Dictionaries_MCQ_Hard_2",
          "type": "mcq",
          "number": 2,
          "title": "Since Python 3.7+, what guarantee does the language standard provide regarding dictionary iteration order?",
          "options": [
            {
              "key": "A",
              "text": "Keys are sorted alphabetically"
            },
            {
              "key": "B",
              "text": "Keys maintain insertion order"
            },
            {
              "key": "C",
              "text": "Keys are sorted by hash value"
            },
            {
              "key": "D",
              "text": "Iteration order is randomized"
            }
          ]
        },
        {
          "id": "Dictionaries_MCQ_Hard_3",
          "type": "mcq",
          "number": 3,
          "title": "In Python 3.9+, which operator merges two dictionaries d1 and d2 into a new dictionary?",
          "options": [
            {
              "key": "A",
              "text": "d1 + d2"
            },
            {
              "key": "B",
              "text": "d1 & d2"
            },
            {
              "key": "C",
              "text": "d1 | d2"
            },
            {
              "key": "D",
              "text": "d1 ^ d2"
            }
          ]
        },
        {
          "id": "Dictionaries_SA_Hard_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain the underlying hash table implementation of Python dictionaries, collision resolution, and why keys must be hashable.",
          "maxWords": 120
        },
        {
          "id": "Dictionaries_Code_Hard_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function invert_and_group(data) that inverts a dictionary mapping keys to values so that original values become keys, each pointing to a sorted list of original keys.",
          "starterCode": "def invert_and_group(data):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "invert_and_group({'apple': 'fruit', 'carrot': 'veggie', 'banana': 'fruit'})",
              "description": "Invert dictionary with duplicate values"
            },
            {
              "call": "invert_and_group({\"alice\": \"CS\", \"bob\": \"Math\", \"charlie\": \"CS\"})",
              "description": "Invert student majors"
            },
            {
              "call": "invert_and_group({})",
              "description": "Invert empty dictionary"
            }
          ]
        }
      ]
    }
  },
  "File Handling": {
    "easy": {
      "concept": "File Handling",
      "difficulty": "easy",
      "questions": [
        {
          "id": "File Handling_MCQ_Easy_1",
          "type": "mcq",
          "number": 1,
          "title": "Which built-in Python function is used to open files on disk?",
          "options": [
            {
              "key": "A",
              "text": "file_open()"
            },
            {
              "key": "B",
              "text": "open()"
            },
            {
              "key": "C",
              "text": "read_file()"
            },
            {
              "key": "D",
              "text": "os.file()"
            }
          ]
        },
        {
          "id": "File Handling_MCQ_Easy_2",
          "type": "mcq",
          "number": 2,
          "title": "What is the default file access mode when mode is omitted in open(\"file.txt\")?",
          "options": [
            {
              "key": "A",
              "text": "\"w\" (write text)"
            },
            {
              "key": "B",
              "text": "\"a\" (append text)"
            },
            {
              "key": "C",
              "text": "\"r\" (read text)"
            },
            {
              "key": "D",
              "text": "\"rb\" (read binary)"
            }
          ]
        },
        {
          "id": "File Handling_MCQ_Easy_3",
          "type": "mcq",
          "number": 3,
          "title": "Why is using the \"with\" statement considered best practice when opening files in Python?",
          "options": [
            {
              "key": "A",
              "text": "It prevents anyone else from reading the file"
            },
            {
              "key": "B",
              "text": "It automatically closes the file even if exceptions occur"
            },
            {
              "key": "C",
              "text": "It encrypts the file content on disk"
            },
            {
              "key": "D",
              "text": "It increases read speed by caching the disk"
            }
          ]
        },
        {
          "id": "File Handling_SA_Easy_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain how to open, read from, and write to a text file in Python, and why the \"with\" statement is recommended.",
          "maxWords": 120
        },
        {
          "id": "File Handling_Code_Easy_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function write_and_read_file(filename, content) that writes content to a file in \"w\" mode, and then reads and returns the file content in \"r\" mode using \"with\" statements.",
          "starterCode": "def write_and_read_file(filename, content):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "write_and_read_file(\"test_easy.txt\", \"Hello, World!\")",
              "description": "Write and read single line string"
            },
            {
              "call": "write_and_read_file('test_notes.txt', 'Line 1' + chr(10) + 'Line 2')",
              "description": "Write and read multiline string"
            },
            {
              "call": "write_and_read_file(\"test_empty.txt\", \"\")",
              "description": "Write and read empty string"
            }
          ]
        }
      ]
    },
    "medium": {
      "concept": "File Handling",
      "difficulty": "medium",
      "questions": [
        {
          "id": "File Handling_MCQ_Medium_1",
          "type": "mcq",
          "number": 1,
          "title": "What is the key difference between open mode \"w\" and open mode \"a\"?",
          "options": [
            {
              "key": "A",
              "text": "\"w\" overwrites or truncates existing file contents, whereas \"a\" appends new data to the end"
            },
            {
              "key": "B",
              "text": "\"w\" is for binary files, whereas \"a\" is for text files"
            },
            {
              "key": "C",
              "text": "\"w\" creates files only if they exist, whereas \"a\" always fails"
            },
            {
              "key": "D",
              "text": "\"w\" locks the file exclusively, whereas \"a\" does not"
            }
          ]
        },
        {
          "id": "File Handling_MCQ_Medium_2",
          "type": "mcq",
          "number": 2,
          "title": "What does the file method f.readlines() return?",
          "options": [
            {
              "key": "A",
              "text": "A single string containing the whole file"
            },
            {
              "key": "B",
              "text": "A list of strings, where each element is a line from the file"
            },
            {
              "key": "C",
              "text": "An integer representing line count"
            },
            {
              "key": "D",
              "text": "An iterator over characters"
            }
          ]
        },
        {
          "id": "File Handling_MCQ_Medium_3",
          "type": "mcq",
          "number": 3,
          "title": "What does the method call f.seek(0) do on an open file object f?",
          "options": [
            {
              "key": "A",
              "text": "Truncates the file size to 0 bytes"
            },
            {
              "key": "B",
              "text": "Resets the file read/write position pointer back to the beginning of the file"
            },
            {
              "key": "C",
              "text": "Deletes the file contents"
            },
            {
              "key": "D",
              "text": "Flushes the internal buffer without moving the pointer"
            }
          ]
        },
        {
          "id": "File Handling_SA_Medium_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain the difference between read(), readline(), and line-by-line file iteration in terms of memory efficiency.",
          "maxWords": 120
        },
        {
          "id": "File Handling_Code_Medium_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function process_log_file(filename, log_lines) that writes log_lines to filename line-by-line, then reads the file back and returns a list of stripped lines that start with \"ERROR\".",
          "starterCode": "def process_log_file(filename, log_lines):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "process_log_file(\"log1.txt\", [\"INFO: start\", \"ERROR: missing file\", \"DEBUG: trace\", \"ERROR: timeout\"])",
              "description": "Filter log errors from file"
            },
            {
              "call": "process_log_file(\"log2.txt\", [\"INFO: ok\", \"WARN: slow\"])",
              "description": "No error lines"
            },
            {
              "call": "process_log_file(\"log3.txt\", [\"ERROR: crash\"])",
              "description": "Single error line"
            }
          ]
        }
      ]
    },
    "hard": {
      "concept": "File Handling",
      "difficulty": "hard",
      "questions": [
        {
          "id": "File Handling_MCQ_Hard_1",
          "type": "mcq",
          "number": 1,
          "title": "Why is explicitly passing encoding=\"utf-8\" when opening text files recommended across systems?",
          "options": [
            {
              "key": "A",
              "text": "Python raises a SyntaxError if encoding is omitted"
            },
            {
              "key": "B",
              "text": "It prevents platform-dependent default encoding mismatches between Windows, Linux, and macOS"
            },
            {
              "key": "C",
              "text": "It converts binary data into ASCII strings"
            },
            {
              "key": "D",
              "text": "It compresses files using gzip"
            }
          ]
        },
        {
          "id": "File Handling_MCQ_Hard_2",
          "type": "mcq",
          "number": 2,
          "title": "Which special dunder methods define the context manager protocol used by the \"with\" statement?",
          "options": [
            {
              "key": "A",
              "text": "__init__ and __del__"
            },
            {
              "key": "B",
              "text": "__enter__ and __exit__"
            },
            {
              "key": "C",
              "text": "__open__ and __close__"
            },
            {
              "key": "D",
              "text": "__start__ and __stop__"
            }
          ]
        },
        {
          "id": "File Handling_MCQ_Hard_3",
          "type": "mcq",
          "number": 3,
          "title": "What is the primary operational advantage of buffered I/O over unbuffered raw I/O in Python?",
          "options": [
            {
              "key": "A",
              "text": "Buffered I/O batches small transfers in memory to minimize costly operating system syscalls"
            },
            {
              "key": "B",
              "text": "Buffered I/O bypasses OS file permissions"
            },
            {
              "key": "C",
              "text": "Buffered I/O guarantees persistent storage without write delays"
            },
            {
              "key": "D",
              "text": "Buffered I/O enables multi-threaded concurrent writes to the same descriptor"
            }
          ]
        },
        {
          "id": "File Handling_SA_Hard_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain context management under the hood (__enter__ and __exit__), character encoding pitfalls, and how file buffering impacts disk I/O.",
          "maxWords": 120
        },
        {
          "id": "File Handling_Code_Hard_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function summarize_csv_file(filename, csv_data) that writes csv_data to filename, then reads and parses the CSV content, returning a dictionary summing the integer amounts per category.",
          "starterCode": "def summarize_csv_file(filename, csv_data):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "summarize_csv_file('test_sales.csv', chr(10).join(['name,category,amount', 'Widget,Tools,10', 'Gadget,Electronics,25', 'Bolt,Tools,15']))",
              "description": "Aggregate tool and electronic amounts"
            },
            {
              "call": "summarize_csv_file('test_groceries.csv', chr(10).join(['name,category,amount', 'Apple,Fruit,5', 'Banana,Fruit,8', 'Carrot,Veggie,4']))",
              "description": "Aggregate grocery category amounts"
            },
            {
              "call": "summarize_csv_file('test_empty.csv', 'name,category,amount')",
              "description": "Empty data rows returns empty dictionary"
            }
          ]
        }
      ]
    }
  },
  "Exception Handling": {
    "easy": {
      "concept": "Exception Handling",
      "difficulty": "easy",
      "questions": [
        {
          "id": "Exception Handling_MCQ_Easy_1",
          "type": "mcq",
          "number": 1,
          "title": "Which Python keyword block is used to catch and handle exceptions?",
          "options": [
            {
              "key": "A",
              "text": "try / catch"
            },
            {
              "key": "B",
              "text": "try / except"
            },
            {
              "key": "C",
              "text": "do / except"
            },
            {
              "key": "D",
              "text": "test / error"
            }
          ]
        },
        {
          "id": "Exception Handling_MCQ_Easy_2",
          "type": "mcq",
          "number": 2,
          "title": "Which block in a try-except statement is guaranteed to always execute, whether an exception occurred or not?",
          "options": [
            {
              "key": "A",
              "text": "else"
            },
            {
              "key": "B",
              "text": "finally"
            },
            {
              "key": "C",
              "text": "resume"
            },
            {
              "key": "D",
              "text": "complete"
            }
          ]
        },
        {
          "id": "Exception Handling_MCQ_Easy_3",
          "type": "mcq",
          "number": 3,
          "title": "Which keyword is used to intentionally raise an exception in Python?",
          "options": [
            {
              "key": "A",
              "text": "throw"
            },
            {
              "key": "B",
              "text": "raise"
            },
            {
              "key": "C",
              "text": "trigger"
            },
            {
              "key": "D",
              "text": "yield"
            }
          ]
        },
        {
          "id": "Exception Handling_SA_Easy_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain the purpose of try, except, and finally blocks in Python error handling.",
          "maxWords": 120
        },
        {
          "id": "Exception Handling_Code_Easy_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function safe_divide(a, b) that returns a / b. Catch ZeroDivisionError and return \"Cannot divide by zero\". Catch TypeError and return \"Invalid types\".",
          "starterCode": "def safe_divide(a, b):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "safe_divide(10, 2)",
              "description": "Safe division of two numbers"
            },
            {
              "call": "safe_divide(5, 0)",
              "description": "Division by zero caught"
            },
            {
              "call": "safe_divide(\"10\", 2)",
              "description": "Type error caught"
            }
          ]
        }
      ]
    },
    "medium": {
      "concept": "Exception Handling",
      "difficulty": "medium",
      "questions": [
        {
          "id": "Exception Handling_MCQ_Medium_1",
          "type": "mcq",
          "number": 1,
          "title": "When does the \"else\" block attached to a try-except structure execute?",
          "options": [
            {
              "key": "A",
              "text": "Only when an unhandled exception occurs"
            },
            {
              "key": "B",
              "text": "Only when the try block executes successfully without raising any exceptions"
            },
            {
              "key": "C",
              "text": "Immediately after the except block finishes"
            },
            {
              "key": "D",
              "text": "Only when a TypeError is raised"
            }
          ]
        },
        {
          "id": "Exception Handling_MCQ_Medium_2",
          "type": "mcq",
          "number": 2,
          "title": "What is the correct syntax for catching multiple distinct exception types in a single except clause?",
          "options": [
            {
              "key": "A",
              "text": "except (ValueError, TypeError):"
            },
            {
              "key": "B",
              "text": "except [ValueError, TypeError]:"
            },
            {
              "key": "C",
              "text": "except ValueError, TypeError:"
            },
            {
              "key": "D",
              "text": "except ValueError or TypeError:"
            }
          ]
        },
        {
          "id": "Exception Handling_MCQ_Medium_3",
          "type": "mcq",
          "number": 3,
          "title": "Which base class should custom user-defined application exceptions inherit from in Python?",
          "options": [
            {
              "key": "A",
              "text": "BaseException"
            },
            {
              "key": "B",
              "text": "Exception"
            },
            {
              "key": "C",
              "text": "RuntimeError"
            },
            {
              "key": "D",
              "text": "SystemError"
            }
          ]
        },
        {
          "id": "Exception Handling_SA_Medium_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain the difference between \"else\" and \"finally\" blocks in try-except statements, and why catching specific exceptions is preferred.",
          "maxWords": 120
        },
        {
          "id": "Exception Handling_Code_Medium_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function parse_int_list(str_items) that converts a list of strings to integers, skipping invalid entries using try/except ValueError. Return a dictionary {\"valid\": valid_list, \"errors\": error_count}.",
          "starterCode": "def parse_int_list(str_items):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "parse_int_list([\"10\", \"abc\", \"25\", \"xyz\", \"42\"])",
              "description": "Parse list with invalid strings"
            },
            {
              "call": "parse_int_list([\"1\", \"2\", \"3\"])",
              "description": "Parse list with all valid integers"
            },
            {
              "call": "parse_int_list([\"invalid\", \"test\"])",
              "description": "Parse list with all invalid strings"
            }
          ]
        }
      ]
    },
    "hard": {
      "concept": "Exception Handling",
      "difficulty": "hard",
      "questions": [
        {
          "id": "Exception Handling_MCQ_Hard_1",
          "type": "mcq",
          "number": 1,
          "title": "Why is using a bare \"except:\" or catching BaseException strongly discouraged in application code?",
          "options": [
            {
              "key": "A",
              "text": "It degrades garbage collection performance"
            },
            {
              "key": "B",
              "text": "It intercepts critical system exit signals like KeyboardInterrupt and SystemExit, preventing clean termination"
            },
            {
              "key": "C",
              "text": "It leads to an immediate compiler SyntaxError"
            },
            {
              "key": "D",
              "text": "Python does not allow BaseException in except clauses"
            }
          ]
        },
        {
          "id": "Exception Handling_MCQ_Hard_2",
          "type": "mcq",
          "number": 2,
          "title": "What is the purpose of the \"raise NewException from orig_exc\" syntax introduced in Python 3?",
          "options": [
            {
              "key": "A",
              "text": "Suppresses the traceback completely"
            },
            {
              "key": "B",
              "text": "Sets the __cause__ attribute on the new exception, explicitly chaining the root cause in tracebacks"
            },
            {
              "key": "C",
              "text": "Retries the failed block from the start"
            },
            {
              "key": "D",
              "text": "Converts the exception into a logged warning"
            }
          ]
        },
        {
          "id": "Exception Handling_MCQ_Hard_3",
          "type": "mcq",
          "number": 3,
          "title": "What happens when a \"return\" statement is placed inside both the \"try\" block and the \"finally\" block?",
          "options": [
            {
              "key": "A",
              "text": "The return value from the \"try\" block takes precedence"
            },
            {
              "key": "B",
              "text": "The return value from the \"finally\" block overrides and replaces the return value from the \"try\" block"
            },
            {
              "key": "C",
              "text": "Python raises a ConflictingReturnError"
            },
            {
              "key": "D",
              "text": "Both values are returned as a tuple"
            }
          ]
        },
        {
          "id": "Exception Handling_SA_Hard_1",
          "type": "short_answer",
          "number": 4,
          "title": "Explain Python exception hierarchy, exception chaining with \"raise ... from\", and the danger of catching BaseException.",
          "maxWords": 120
        },
        {
          "id": "Exception Handling_Code_Hard_1",
          "type": "coding",
          "number": 5,
          "title": "Write a function retry_operation(func, max_retries=3, fallback_value=None) that executes func(). If an exception occurs, retry up to max_retries times. Return the successful result or fallback_value if all retries fail.",
          "starterCode": "def retry_operation(func, max_retries=3, fallback_value=None):\n    # Write your solution here\n    pass\n",
          "testCases": [
            {
              "call": "retry_operation(lambda: 42, max_retries=3, fallback_value=-1)",
              "description": "Immediate success"
            },
            {
              "call": "retry_operation(lambda: 1 / 0, max_retries=3, fallback_value=\"failed\")",
              "description": "All retries fail and fallback returned"
            },
            {
              "call": "retry_operation((lambda count=[0]: (count.__setitem__(0, count[0] + 1) or (count[0] if count[0] >= 2 else 1/0))), max_retries=3, fallback_value=0)",
              "description": "Success on second attempt"
            }
          ]
        }
      ]
    }
  }
};


/**
 * Retrieves the public question bundle for any concept and difficulty.
 * Guaranteed to exclude answer keys and expected test outputs.
 */
export function getPublicBundle(
  concept: string,
  difficulty: "easy" | "medium" | "hard" = "medium"
): PublicConceptBundle {
  const conceptBundles = PUBLIC_BUNDLE_CATALOG[concept] || PUBLIC_BUNDLE_CATALOG["Loops"];
  const bundle = conceptBundles[difficulty] || conceptBundles["medium"] || conceptBundles["easy"];
  return bundle;
}
