# Development History & Phase Audit Log

**Document:** `project_handover/DEVELOPMENT_HISTORY.md`  
**Project:** Adaptive Knowledge Tracing (AKT) & Multimodal Intelligent Tutoring System  
**Audience:** Incoming Senior AI Engineers, Researchers, and AI Assistants (Google Gemini Pro)  

---

## 1. Chronological Phase Matrix

The following matrix documents the verified development trajectory of the AKT Intelligent Tutor. Each phase reflects concrete source code artifacts and passing test suites in `/Users/abdulsamath/AKT-recovery-test copy`.

| Phase | Objective | Implemented Work | Verification | Status | Pending Work |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | Disaster Recovery & Workspace Reconstruction | Established recovery runbook (`RECOVERY.md`), isolated virtual environment (`.venv-isolated`), verified backup manifests across research, application, and database snapshots. | Validated SHA256 hashes; restored isolated MongoDB double; verified document counts (users: 63, student_states: 54, scores: 94). | **CLOSED** | None. Baseline recovery fully operational. |
| **Phase 2A** | Technical Design Review & Evidence Spec Correction | Formulated canonical JSON Schema (Draft 2020-12) for multimodal evidence; resolved lifecycle inconsistencies; separated completed test results from research admission policy. | Automated JSON schema validation against 4 multimodal example records. | **CLOSED** | None. Frozen as baseline design. |
| **Phase 2B** | Implementation Planning & Risk Analysis | Audited execution order in `evaluate_bundle`; evaluated identifier semantics (`submission_id`, `bundle_id`, `evidence_id`); evaluated shadow-write risks. | Architectural report identifying dual-write risks and selecting Option A (Embedded Records). | **CLOSED** | None. Option A approved. |
| **Phase 3** | Canonical Pydantic Schema Implementation | Implemented `UnifiedEvidenceRecord` in `src/schemas/evidence.py` covering MCQ, Short Answer, and Coding modalities. | Authored `test_evidence_schema.py`; verified cross-field invariants and enum types. | **CLOSED** | Superseded by Phase 3A refinements. |
| **Phase 3A** | Approved Schema Refinements | Modified `UnifiedEvidenceRecord` to allow SBERT negative cosine values $[-1.0, 1.0]$, made client timestamps nullable, decoupled item and concept attempt counters. | 33 isolated schema tests passing in `test_evidence_schema.py`. | **CLOSED** | None. Schema frozen. |
| **Phase 4** | Evaluator Harmonization Implementation | Built modular adapters in `src/evidence_adapters/` (`mcq_adapter.py`, `short_answer_adapter.py`, `coding_adapter.py`) converting legacy outputs to canonical records. | 22 isolated adapter tests passing across `test_mcq_adapter.py`, `test_short_answer_adapter.py`, and `test_coding_adapter.py`. | **CLOSED** | None. All 3 modalities harmonized. |
| **Phase 5** | Embedded Evidence Persistence (Option A) | Built `bundle_builder.py`; wired atomic embedded evidence persistence into `api.py` (`db["scores"].insert_one`); enforced privacy masking of student code and text. | 9 isolated persistence tests passing in `test_embedded_evidence_persistence.py`; all 64 evidence tests passing. | **CLOSED** | None. Option A fully implemented and verified. |
| **Phase 7B-2** | Host-Process Code Execution Quarantine | Permanently disabled `exec()`, `eval()`, and host `subprocess` in `code_analyzer.py`; built hardened ephemeral Docker sandbox runner (`sandbox_runner.py`). | Verified fail-closed behavior when Docker daemon is offline; AST syntax verification passing. | **CLOSED** | None. Quarantine permanently locked. |
| **Phase 8G** | Portal Regression Audit & Verification | Full verification across all 6 portal pages (`/dashboard`, `/practice`, `/history`, `/analytics`, `/adaptive-learning`, `/profile`); verified Next.js App Router, TypeScript checks, and build artifacts. | `tsc --noEmit` clean exit; Next.js production build verified; analyzer regression tests passing. | **CLOSED** | Automated E2E browser interactions (Playwright) deferred. |

---

## 2. Major Bugs Discovered & Resolved

Throughout system development, several critical architectural and algorithmic defects were identified, analyzed, and permanently resolved:

### 1. Host Code Execution Exploit Risk (Phase 7B-2)
- **Problem:** Early iterations executed student Python submissions directly inside the FastAPI backend process using `exec()` or host subprocesses, introducing severe security vulnerabilities (remote code execution, file system tampering, resource starvation).
- **Resolution:** Host code execution was permanently banned and quarantined. `code_analyzer.py` was restricted to AST parsing (`ast.parse`) for syntax analysis. Ephemeral, non-root Docker containers with strict timeouts and memory limits were introduced in `sandbox_runner.py`. When Docker is offline, the runner fails closed to `PENDING_SECURE_EVALUATION` with score `None`.

### 2. SBERT Negative Cosine Rejection (Phase 3A)
- **Problem:** `UnifiedEvidenceRecord.raw_score` had a global validation rule `ge=0.0`. Valid semantic cosine similarities from `sentence-transformers/all-MiniLM-L6-v2` can fall between $-1.0$ and $+1.0$. Opposing or unrelated student responses generated negative cosine values that caused Pydantic validation crashes.
- **Resolution:** Removed the global `ge=0.0` constraint from `raw_score` and implemented modality-aware cross-field validation: Short Answer raw scores permit $[-1.0, 1.0]$ while `normalized_score` is clamped to $[0.0, 1.0]$. MCQ and Coding retain non-negative constraints.

### 3. Short Answer Scale Inconsistency (Phase 5)
- **Problem:** Legacy frontend and test payloads submitted `short_answer_score` as a percentage (e.g. `83.8` for $83.8\%$), whereas the SBERT adapter expected fractional cosine values in $[-1.0, 1.0]$, causing `ValueError: SBERT cosine similarity must be within [-1.0, 1.0], got 83.8`.
- **Resolution:** Added automated scale normalization in `bundle_builder.py`: if `short_answer_score > 1.0`, it is divided by $100.0$ to standardize to unit interval $[0.0, 1.0]$ before passing to the adapter.

### 4. BKT Optimistic Concurrency Race Condition (Phase 6 / Version Locking)
- **Problem:** Rapid sequential or parallel assessment submissions resulted in lost updates on student mastery state in `db["student_states"]`.
- **Resolution:** Implemented per-student in-memory `asyncio.Lock()` in FastAPI and optimistic concurrency version locking using a `version` integer field in MongoDB. Updates use `db["student_states"].update_one({"student_id": ..., "version": expected_ver}, {"$set": ..., "$inc": {"version": 1}})`, rejecting conflicts with HTTP 409 and forcing state reload.

### 5. Dual-Write Divergence in Evidence Persistence (Phase 2B / Phase 5)
- **Problem:** Proposals to store evidence records in a separate `evidence_ledger` collection created dual-write failure windows where score documents were written but evidence records were lost upon process crash, requiring complex background reconciliation workers.
- **Resolution:** Selected and implemented **Option A**: embedding the 5 `UnifiedEvidenceRecord` objects directly inside the existing `scores` document. Persisted in a single atomic MongoDB WiredTiger document write with zero dual-write window.

### 6. Submission Replay & Idempotency
- **Problem:** Network retries from the frontend or student double-clicks risked inserting duplicate score rows and repeatedly applying BKT/EMA observations to mastery.
- **Resolution:** Enforced unique index on `submission_id` in `db["scores"]`. Before inserting, the backend checks for existing `submission_id` with `bkt_processed: True`. If found, it immediately returns the cached response. In concurrent race conditions, `DuplicateKeyError` is caught and the existing document is served.

---

## 3. Decisions That Must Not Be Reversed

The following design decisions are research- and safety-critical and **must NOT be reversed** without explicit stakeholder approval:

1. **Quarantine of Host Code Execution:** Never reintroduce `exec()`, `eval()`, or host subprocess execution for student code.
2. **Cognitive Model EMA Exclusivity:** Never feed raw Coding scores or Short Answer semantic similarity into the live EMA mastery tracker. Only binary MCQ items (`activity_type=0`) update live mastery.
3. **Option A Embedded Evidence:** Never separate evidence records into a secondary collection requiring dual-write transactions.
4. **Permanent Privacy Masking:** Never write raw student Python code or essay text to the permanent MongoDB database ledger.
5. **Phase 8G Status:** Phase 8G is marked CLOSED. All six portal pages are verified. Do not restart Phase 8 audits.

