# AI Assistant Development Rules & Working Preferences

**Document:** `project_handover/DEVELOPMENT_RULES.md`  
**Project:** Adaptive Knowledge Tracing (AKT) & Multimodal Intelligent Tutoring System  
**Audience:** Incoming AI Coding Assistants (Google Gemini Pro), Engineers, and Collaborators  

---

## 1. Core Working Principles & User Communication Style

When collaborating on this project, incoming AI assistants (specifically Google Gemini Pro) must strictly adhere to the following communication and execution preferences:

1. **Simple, Beginner-Friendly Language:** Explain technical concepts, architectural decisions, and error diagnostics in clear, accessible English without unnecessary jargon.
2. **One Step at a Time:** Provide instructions sequentially. Never dump large, multi-step execution plans without stopping to let the user execute and verify each milestone.
3. **Exact File Paths & Copy-Paste Ready Commands:**
   - Always cite exact absolute or workspace-relative file paths (e.g. `/Users/abdulsamath/AKT-recovery-test copy/api.py`).
   - Format terminal commands in standalone, copy-paste-ready code blocks.
4. **State Purpose Before Command:** Explain *what* a command will do and *why* it is necessary before prompting the user to run it.
5. **Wait for Actual Terminal Output:** When a command requires terminal execution, wait for the user to provide the actual output before proceeding to subsequent steps.
6. **Inspect Existing Code First:** Always inspect actual source code files using read tools before proposing edits. Never speculate or assume file contents match prior training data.
7. **Never Rewrite Working Code Unnecessarily:** Make minimal, surgical edits. Do not rewrite, refactor, reformat, or restyle working production code unless explicitly tasked with doing so.
8. **No Deletions or Renames Without Explicit Approval:** Never delete, move, or rename files or database collections without prior user consent.
9. **Discuss Before Implementing:** Present a concise technical proposal and obtain user approval before writing code for new features or major modifications.
10. **Report Actual Results Only:** Never fabricate, simulate, or assume test results. Always report the exact, verified console output.

---

## 2. Technical Invariants & Guardrails

The following technical boundaries are immutable and must be preserved throughout all future development:

### A. Security Guardrails
- **Host Code Execution Quarantine:** Student Python submissions must **NEVER** be evaluated using `exec()`, `eval()`, or host `subprocess` inside the FastAPI backend. Code execution must occur exclusively inside the hardened ephemeral Docker container runner (`src/analyzers/sandbox_runner.py`).
- **Fail-Closed Sandbox:** If Docker is offline or unavailable, the system must fail closed: return `PENDING_SECURE_EVALUATION` with score `None`. Never bypass container security by falling back to host execution.
- **Data Privacy & Retention Masking:** Raw student Python code and freeform answers must never be persisted in MongoDB. Always replace them with `[EXCLUDED_PRIVACY_POLICY]` in permanent ledgers.

### B. Cognitive Model Guardrails
- **EMA Mastery Tracker Isolation:** Only binary MCQ items (`activity_type=0`, `ADMITTED_BINARY`) may update the live student knowledge state in `api.py`. Short Answer and Coding items must remain excluded from EMA updates until formal research admission policies are approved.
- **Formula Preservation:** Never modify the composite bundle score formula:
  $$\text{Bundle Average} = (0.6 \times \text{MCQ Fraction}) + (0.4 \times \text{Short Answer Score})$$
- **Adaptive Priority Formula:** Do not change the concept recommendation formula:
  $$\text{Priority} = (1.0 - \text{Mastery}) \times (1.0 + \text{Uncertainty})$$

### C. Data Persistence Guardrails
- **Option A Embedded Evidence:** Assessment item evidence records must be stored embedded directly inside the `scores` document in a single atomic write. Never introduce dual-write secondary collections.
- **Idempotency Protection:** The unique index on `submission_id` in `db["scores"]` must be respected. Always check for existing `bkt_processed: True` before insertion, and catch `DuplicateKeyError` in concurrent race conditions.
- **Optimistic Version Locking:** State updates to `db["student_states"]` must check the `version` field to prevent lost updates.

---

## 3. Standard Verification Commands

Before concluding any development phase or submitting changes, run these verification commands in the isolated environment:

```bash
# 1. Activate isolated Python environment
source .venv-isolated/bin/activate

# 2. Run Evidence Harmonization & Persistence Test Suite (64 tests)
python -m pytest test_evidence_schema.py test_mcq_adapter.py test_short_answer_adapter.py test_coding_adapter.py test_embedded_evidence_persistence.py -v

# 3. Run Backend Concurrency & Regression Test Suite (48 tests)
python -m pytest test_bkt_version_locking.py test_history_coding_status.py test_analyzers.py test_engine.py test_models.py test_api_kc_cycling.py -v

# 4. Run Frontend TypeScript Typecheck
cd frontend && npx tsc --noEmit && cd ..
```
All tests must exit with code 0 before any phase is declared complete.

