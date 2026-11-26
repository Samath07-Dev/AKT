/**
 * frontend/test_preview_structure.mjs
 *
 * Automated regression test suite for meaningful-code structural detection.
 * Validates that OOP classes (BankAccount), dictionary parsers (parse_key_values),
 * and functional implementations pass simulated preview detection, while stubs,
 * empty inputs, and comments-only code are correctly flagged as INCOMPLETE.
 */

import { hasMeaningfulCode } from "./src/lib/code-structure.ts";

const BANK_ACCOUNT_CODE = `
class BankAccount:
    def __init__(self):
        self.balance = 0

    def deposit(self, amount):
        if amount > 0:
            self.balance += amount

    def withdraw(self, amount):
        if 0 < amount <= self.balance:
            self.balance -= amount
            return True
        return False

    def get_balance(self):
        return self.balance
`;

const PARSE_KEY_VALUES_CODE = `
def parse_key_values(kv_str):
    if not kv_str.strip():
        return {}

    result = {}
    for pair in kv_str.split(';'):
        if '=' in pair:
            k, v = pair.split('=', 1)
            result[k.strip()] = v.strip()

    return result
`;

const TEST_CASES = [
  { name: "1. Complete BankAccount (OOP class with methods & state)", code: BANK_ACCOUNT_CODE, expected: true },
  { name: "2. Complete parse_key_values (procedural function with loop/dict)", code: PARSE_KEY_VALUES_CODE, expected: true },
  { name: "3. Simple valid function (add)", code: "def add(a, b):\n    return a + b", expected: true },
  { name: "4. Simple valid class (Person)", code: "class Person:\n    def __init__(self, name):\n        self.name = name\n    def get_name(self):\n        return self.name", expected: true },
  { name: "5. Empty string input", code: "", expected: false },
  { name: "6. Whitespace-only input", code: "   \n\t  \n  ", expected: false },
  { name: "7. Comments-only input", code: "# Write solution here\n# TODO: implement", expected: false },
  { name: "8. Docstring-only input", code: '"""\nThis is a docstring describing the problem.\n"""', expected: false },
  { name: "9. Pass-only statement", code: "pass", expected: false },
  { name: "10. Pass-only statement with trailing semicolon", code: "pass;", expected: false },
  { name: "11. Class BankAccount with pass stub", code: "class BankAccount:\n    # Write your solution here\n    pass\n", expected: false },
  { name: "12. Function parse_key_values with pass stub", code: "def parse_key_values(kv_str):\n    # Write your solution here\n    pass\n", expected: false },
  { name: "13. Function with raise NotImplementedError", code: "def foo():\n    raise NotImplementedError\n", expected: false },
  { name: "14. Class with __init__ containing only pass", code: "class BankAccount:\n    def __init__(self):\n        pass\n", expected: false },
  { name: "15. Bare return without value", code: "def foo():\n    return\n", expected: false },
  { name: "16. Bare return None", code: "def foo():\n    return None\n", expected: false },
];

console.log("============================================================");
console.log("       Meaningful-Code Structural Detection Tests           ");
console.log("============================================================");

let failedCount = 0;

for (const tc of TEST_CASES) {
  const result = hasMeaningfulCode(tc.code);
  const passed = result === tc.expected;
  if (!passed) {
    console.error(`❌ FAIL: ${tc.name}`);
    console.error(`   Expected: ${tc.expected}, Actual: ${result}`);
    failedCount++;
  } else {
    console.log(`✓ PASS: ${tc.name} -> ${result ? "MEANINGFUL (Simulated Pass)" : "INCOMPLETE (Stub/Empty)"}`);
  }
}

console.log("============================================================");
if (failedCount > 0) {
  console.error(`❌ ${failedCount} test(s) failed.`);
  process.exit(1);
} else {
  console.log(`✓ ALL ${TEST_CASES.length} structural detection tests passed successfully!`);
}

