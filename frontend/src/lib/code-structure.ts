/**
 * frontend/src/lib/code-structure.ts
 *
 * Structural code analyzer for student Python programming tasks.
 * Performs safe, client/server structural inspection without executing student code.
 *
 * Security Policy:
 * - Real Python execution is quarantined (SANDBOX_OFFLINE=1).
 * - Code is never executed via exec, eval, or host subprocesses.
 * - Meaningful implementation detection checks for substantive statements,
 *   supporting OOP classes, constructors, methods, and procedural functions
 *   without relying on naive string equality diffs against starter templates.
 */

/**
 * Checks whether the submitted Python code contains a substantive, meaningful implementation.
 * Returns true if the code contains operational statements (assignments, conditionals,
 * loops, returns with expressions, class methods, etc.).
 * Returns false if the code is empty, whitespace-only, comment/docstring-only, or a pass/stub.
 */
export function hasMeaningfulCode(rawCode: string | null | undefined): boolean {
  if (!rawCode || typeof rawCode !== "string") return false;
  const trimmed = rawCode.trim();
  if (!trimmed) return false;

  // 1. Strip triple-quoted docstrings ("""...""" and '''...''')
  const cleaned = trimmed
    .replace(/"""[\s\S]*?"""/g, "")
    .replace(/'''[\s\S]*?'''/g, "");

  // 2. Split lines and strip inline comments (# ...)
  const lines = cleaned
    .split("\n")
    .map((l) => {
      const hashIdx = l.indexOf("#");
      return hashIdx >= 0 ? l.slice(0, hashIdx).trim() : l.trim();
    })
    .filter(Boolean);

  if (lines.length === 0) return false;

  // 3. Filter out non-operational stub statements
  const isStubLine = (l: string) => {
    const s = l.replace(/;+$/, "").trim();
    return (
      s === "pass" ||
      s === "..." ||
      s === "raise NotImplementedError" ||
      s === "raise NotImplementedError()"
    );
  };

  const nonStubLines = lines.filter((l) => !isStubLine(l));
  if (nonStubLines.length === 0) return false;

  // 4. Identify structural signatures (class ...: or def ...:)
  const isDefOrClass = (l: string) =>
    /^class\s+[A-Za-z_][A-Za-z0-9_]*(\s*\(.*\))?\s*:/.test(l) ||
    /^def\s+[A-Za-z_][A-Za-z0-9_]*\s*\(.*\)\s*(->.*)?\s*:/.test(l);

  // If every non-stub line is merely a bare "class ...:" or "def ...:" declaration, it is an empty stub
  const operationalLines = nonStubLines.filter((l) => !isDefOrClass(l));
  if (operationalLines.length === 0) return false;

  // 5. Must have at least one substantive operational statement:
  // - Return statement with an expression (not bare return or return None)
  // - Variable or attribute assignment / augmented assignment (self.balance = 0, k, v = ...)
  // - Control flow keywords (if, elif, else:, for, while, with, try:, except, finally:)
  // - Method/function invocation (acc.deposit(100), kv_str.split(';'))
  // - Structured data operations / indexing / comprehensions
  const isMeaningfulOp = (l: string) => {
    if (/^return(\s+.*)?$/.test(l)) {
      const retVal = l.replace(/^return/, "").trim();
      return retVal.length > 0 && retVal !== "None";
    }
    if (/^[a-zA-Z_][a-zA-Z0-9_\.]*\s*(\+=|-=|\*=|\/=|%=|=)\s*.+/.test(l)) return true;
    if (/^(if|elif|else:|for|while|with|try:|except|finally:)\b/.test(l)) return true;
    if (/[a-zA-Z_][a-zA-Z0-9_]*\(.*\)/.test(l)) return true;
    if (/\[.*\]|\{.*\}|\(.*\)/.test(l)) return true;
    return false;
  };

  const meaningfulOps = operationalLines.filter(isMeaningfulOp);
  return meaningfulOps.length > 0;
}

