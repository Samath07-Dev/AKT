# Master File Inventory & Module Directory

**Document:** `project_handover/FILE_INVENTORY.md`  
**Project:** Adaptive Knowledge Tracing (AKT) & Multimodal Intelligent Tutoring System  
**Audience:** Incoming Senior AI Engineers, Systems Architects, and Google Gemini Pro  

---

## 1. File Classification Taxonomy

Every file in the repository falls into one of four operational categories:
- **PRESERVE:** Core domain, model, analyzer, persistence, or schema code. Must not be deleted, renamed, or refactored without explicit stakeholder approval.
- **GENERATED / BUILD:** Output files produced by compilers, bundlers, or test caches (`.next/`, `__pycache__/`, `.pytest_cache/`). Safe to regenerate.
- **SENSITIVE:** Contains environment secrets, session keys, or password hashes (`.env.local`, MongoDB dumps). Never print or commit secret values.
- **RESEARCH ASSET:** Pinned model checkpoints and raw benchmark datasets (`data/processed/akt_baseline.pt`, `data/raw/`).

---

## 2. Core Backend Modules

| File Path | Purpose | Key Classes / Functions | Dependencies | Status |
| :--- | :--- | :--- | :--- | :--- |
| `api.py` | Primary FastAPI application server and REST endpoints. Implements auth, session validation, score ledger, optimistic version locking, and adaptive recommendation. | `app`, `record_student_score_internal_async`, `evaluate_bundle`, `get_student_tracker`, `persist_student_mastery_state` | `fastapi`, `motor`, `pydantic`, `argon2`, `torch`, `sentence_transformers` | **PRESERVE** |
| `conftest.py` | Global Pytest configuration and shared test fixtures (auth headers, service secrets, mock databases). | `auth_headers`, `TEST_SERVICE_SECRET`, `TEST_STUDENT_ID` | `pytest`, `fastapi.testclient` | **PRESERVE** |
| `setup_project.py` | Directory structure initializer and benchmark data downloader. | `setup_directories()`, `download_sample_data()` | `os`, `pathlib`, `urllib` | **PRESERVE** |
| `start_fastapi.sh` | Local service startup script exporting service secrets and invoking Uvicorn. | `uvicorn api:app --reload` | `bash`, `uvicorn` | **PRESERVE** |

---

## 3. Evidence Schemas & Harmonization Adapters

| File Path | Purpose | Key Classes / Functions | Dependencies | Status |
| :--- | :--- | :--- | :--- | :--- |
| `src/schemas/evidence.py` | Canonical Pydantic 2 schema definitions for multimodal evidence records (`UnifiedEvidenceRecord`). | `UnifiedEvidenceRecord`, `ModalityType`, `EvaluationLifecycle`, `AdmissionStatus`, `MCQDetails`, `ShortAnswerDetails`, `CodingDetails` | `pydantic`, `enum`, `datetime` | **PRESERVE** |
| `src/schemas/__init__.py` | Package exports for canonical schemas. | Re-exports `UnifiedEvidenceRecord` and enums. | `src.schemas.evidence` | **PRESERVE** |
| `src/evidence_adapters/mcq_adapter.py` | Transforms legacy MCQ evaluation dictionaries into canonical `UnifiedEvidenceRecord` instances (`ADMITTED_BINARY`). | `adapt_mcq_evaluation()` | `src.schemas.evidence` | **PRESERVE** |
| `src/evidence_adapters/short_answer_adapter.py` | Transforms SBERT semantic similarity outputs into canonical records (`ADMITTED_FORMATIVE_ONLY`). | `adapt_short_answer_evaluation()` | `src.schemas.evidence`, `numpy` | **PRESERVE** |
| `src/evidence_adapters/coding_adapter.py` | Transforms code analyzer and Docker sandbox execution outputs into canonical records (`PENDING_EVALUATION` / `PENDING_RESEARCH_POLICY`). | `adapt_coding_evaluation()` | `src.schemas.evidence` | **PRESERVE** |
| `src/evidence_adapters/bundle_builder.py` | Combines 3 MCQs, 1 Short Answer, and 1 Coding task into 5 canonical records. Enforces privacy masking (`[EXCLUDED_PRIVACY_POLICY]`) and scale normalization. | `build_embedded_bundle_evidence()`, `PRIVACY_EXCLUSION_TOKEN` | `src.schemas.evidence`, `src.evidence_adapters.*` | **PRESERVE** |
| `src/evidence_adapters/__init__.py` | Package exports for adapters and bundle builder. | Re-exports `build_embedded_bundle_evidence`, `PRIVACY_EXCLUSION_TOKEN`, and adapters. | `src.evidence_adapters.*` | **PRESERVE** |

---

## 4. Machine Learning Models & Research Pipelines

| File Path | Purpose | Key Classes / Functions | Dependencies | Status |
| :--- | :--- | :--- | :--- | :--- |
| `src/models/dkt.py` | Deep Knowledge Tracing baseline using LSTM/GRU networks. | `DKTBaseline`, `train_dkt_epoch()`, `evaluate_dkt()` | `torch`, `torch.nn` | **PRESERVE** |
| `src/models/akt.py` | Attention-based Knowledge Tracing baseline with causal self-attention. | `AKTBaseline`, `PositionalEncoding`, `train_akt_epoch()`, `evaluate_akt()` | `torch`, `torch.nn`, `math` | **PRESERVE** |
| `src/models/behavior_akt.py` | Behavior-Aware AKT model fusing concept embeddings, modality embeddings, and behavioral telemetry with Monte Carlo Dropout ($N=20$). | `BehaviorAKT`, `predict_with_uncertainty()`, `train_behavior_akt_epoch()` | `torch`, `torch.nn`, `math` | **PRESERVE** |
| `src/models/__init__.py` | Model package exports. | Re-exports `DKTBaseline`, `AKTBaseline`, `BehaviorAKT`. | `src.models.*` | **PRESERVE** |
| `train.py` | 50% Milestone baseline training script for AKT on CSEDM / Runestone datasets. | `main()`, DataLoader pipelines, train/val splits | `torch`, `pandas`, `src.data.preprocessor` | **PRESERVE** |
| `run_presentation_experiments.py` | Research benchmarking script comparing DKT, AKT, and Behavior-AKT; computes AUC, F1, RMSE, and ablation metrics. | `main()`, `compute_metrics()`, `run_ablation_experiments()` | `torch`, `sklearn.metrics`, `pandas` | **PRESERVE** |
| `src/data/preprocessor.py` | Ingests raw interaction CSVs, standardizes continuous features, builds PyTorch `KTDataset` sequences. | `UnifiedDataPreprocessor`, `KTDataset`, `load_raw_file_in_chunks()` | `torch.utils.data`, `pandas`, `numpy` | **PRESERVE** |

---

## 5. Analyzers & Sandbox Runners

| File Path | Purpose | Key Classes / Functions | Dependencies | Status |
| :--- | :--- | :--- | :--- | :--- |
| `src/analyzers/mcq_analyzer.py` | Evaluates student MCQ selections against answer keys and distractor weights. | `MCQAnalyzer`, `evaluate()` | Python standard library | **PRESERVE** |
| `src/analyzers/short_answer_analyzer.py` | Computes SBERT embedding cosine similarity against reference answer rubrics. | `ShortAnswerAnalyzer`, `evaluate()`, `compute_cosine_similarity()` | `sentence_transformers`, `numpy` | **PRESERVE** |
| `src/analyzers/code_analyzer.py` | Static AST syntax parser. Host-process code execution is permanently disabled. | `CodeAnalyzer`, `check_syntax()`, `evaluate()` | `ast` | **PRESERVE** |
| `src/analyzers/sandbox_runner.py` | Hardened ephemeral Docker runner for untrusted Python code. Fails closed to `PENDING_SECURE_EVALUATION` when offline. | `SandboxRunner`, `evaluate_code_isolated()`, `is_docker_available()` | `subprocess`, `docker CLI`, `ast` | **PRESERVE** |
| `src/analyzers/__init__.py` | Package exports for all evaluators. | Re-exports analyzer classes. | `src.analyzers.*` | **PRESERVE** |

---

## 6. Adaptive Recommendation Engine

| File Path | Purpose | Key Classes / Functions | Dependencies | Status |
| :--- | :--- | :--- | :--- | :--- |
| `src/engine/knowledge_state.py` | Real-time Exponential Moving Average (EMA) mastery tracker per concept ($\mu$ and $\sigma$). | `KnowledgeStateTracker`, `update_state()`, `get_concept_mastery()`, `reset_state()` | `numpy` | **PRESERVE** |
| `src/engine/adaptive_selector.py` | Uncertainty-guided adaptive activity selector and difficulty scaffolding engine. Priority: $(1 - \mu) \times (1 + \sigma)$. | `AdaptiveActivitySelector`, `select_activity()`, `scaffold_difficulty()` | Python standard library | **PRESERVE** |
| `src/engine/__init__.py` | Engine package exports. | Re-exports `KnowledgeStateTracker`, `AdaptiveActivitySelector`. | `src.engine.*` | **PRESERVE** |

---

## 7. Frontend Application (Next.js 16.4.5)

| File Path | Purpose | Key Components / Exports | Dependencies | Status |
| :--- | :--- | :--- | :--- | :--- |
| `frontend/src/app/layout.tsx` | Root Next.js layout providing global fonts and theme wrappers. | `RootLayout` | `react`, `globals.css` | **PRESERVE** |
| `frontend/src/app/(auth)/login/page.tsx` | Student sign-in page. | `LoginPage` | `lucide-react`, React hooks | **PRESERVE** |
| `frontend/src/app/(auth)/register/page.tsx` | Student registration page. | `RegisterPage` | `lucide-react`, React hooks | **PRESERVE** |
| `frontend/src/app/(portal)/layout.tsx` | Portal layout wrapping sidebar, top navbar, and auth check. | `PortalLayout` | `sidebar.tsx`, `top-navbar.tsx` | **PRESERVE** |
| `frontend/src/app/(portal)/portal-client-shell.tsx` | Client shell managing session state and responsive layout. | `PortalClientShell` | React Context, hooks | **PRESERVE** |
| `frontend/src/app/(portal)/dashboard/page.tsx` | Main student dashboard. | `DashboardPage`, `KnowledgeRadarChart` | `recharts`, UI components | **PRESERVE** |
| `frontend/src/app/(portal)/practice/page.tsx` | Multimodal assessment arena. | `PracticePage`, `MonacoCodeWorkspace`, `MCQCard`, `ShortAnswerBox` | `@monaco-editor/react`, UI components | **PRESERVE** |
| `frontend/src/app/(portal)/history/page.tsx` | Historical submissions ledger. | `HistoryPage`, `HistoryTable` | `lucide-react`, UI components | **PRESERVE** |
| `frontend/src/app/(portal)/analytics/page.tsx` | Deep-dive mastery and velocity analytics. | `AnalyticsPage`, `LearningVelocityChart` | `recharts`, UI components | **PRESERVE** |
| `frontend/src/app/(portal)/adaptive-learning/page.tsx` | Curriculum prerequisite and priority map. | `AdaptiveLearningPage` | UI components | **PRESERVE** |
| `frontend/src/app/(portal)/profile/page.tsx` | Student account profile and settings. | `ProfilePage` | UI components | **PRESERVE** |
| `frontend/src/lib/auth/session.ts` | JWT session encoding, decoding, and cookie extraction. | `getSession()`, `createSession()`, `destroySession()` | `jose` / standard crypto | **PRESERVE** |
| `frontend/src/lib/server/bundle-evaluator.ts` | Server-side bundle evaluation dispatcher. | `evaluateBundleServer()` | `fetch`, Next.js server | **PRESERVE** |
| `frontend/src/lib/server/sandbox-status.ts` | Docker sandbox health checker. | `getSandboxStatus()` | `fetch` | **PRESERVE** |
| `frontend/src/lib/api/backend-client.ts` | Shared client for loopback FastAPI calls with secret header. | `fetchFromBackend()` | `fetch` | **PRESERVE** |

---

## 8. Automated Test Suite Files

| File Path | Purpose | Test Count | Status |
| :--- | :--- | :--- | :--- |
| `test_evidence_schema.py` | Tests Pydantic `UnifiedEvidenceRecord` schema invariants, negative raw scores, nullable timestamps, and validation rules. | 33 tests | **PRESERVE** (33 passing) |
| `test_mcq_adapter.py` | Tests MCQ adapter correctness, distractor weighting, and serialization. | 5 tests | **PRESERVE** (5 passing) |
| `test_short_answer_adapter.py` | Tests SBERT adapter semantic similarity range preservation and bounding. | 9 tests | **PRESERVE** (9 passing) |
| `test_coding_adapter.py` | Tests coding adapter AST error, sandbox execution, and infrastructure failure handling. | 8 tests | **PRESERVE** (8 passing) |
| `test_embedded_evidence_persistence.py` | Tests Option A embedded persistence in `scores`, atomic writes, replay idempotency, race recovery, and privacy masking. | 9 tests | **PRESERVE** (9 passing) |
| `test_bkt_version_locking.py` | Tests optimistic concurrency version locking on `student_states` and duplicate key race recovery. | 13 tests | **PRESERVE** (13 passing) |
| `test_history_coding_status.py` | Tests coding status normalization (`PENDING_SECURE_EVALUATION`) across `/history`. | 3 tests | **PRESERVE** (3 passing) |
| `test_analyzers.py` | Tests AST syntax checking, quarantine of host execution, and analyzer unit behavior. | 7 tests | **PRESERVE** (7 passing) |
| `test_engine.py` | Tests adaptive activity selector routing and knowledge state tracker math. | 2 tests | **PRESERVE** (2 passing) |
| `test_models.py` | Tests PyTorch model forward passes for DKT, AKT, and Behavior-AKT. | 1 test | **PRESERVE** (1 passing) |
| `test_api_kc_cycling.py` | Tests curriculum cycling and IDOR security protections. | 6 tests | **PRESERVE** (6 passing, 2 DB-skipped) |
| `test_sandbox_runner.py` | Hardened Docker sandbox tests (asserts container execution or clean fail-closed). | 10 tests | **PRESERVE** (fails closed when Docker offline) |
| `test_student_dashboard_flow.py` | Integration test suite for full student dashboard flow. | 21 tests | **PRESERVE** (requires live MongoDB daemon) |

---

## 9. Data Assets & Preserved Checkpoints

| File Path | Description | Classification |
| :--- | :--- | :--- |
| `data/processed/akt_baseline.pt` | Pinned PyTorch model weights for 50% Milestone baseline AKT model ($447\text{ KB}$). | **RESEARCH ASSET** |
| `data/processed/akt_metadata.json` | Concept vocabulary, hyperparameter configuration, and feature scaling metadata ($3.3\text{ KB}$). | **RESEARCH ASSET** |
| `data/raw/csedm_sample.csv` | CSEDM Data Challenge interaction log sample ($9.9\text{ KB}$). | **RESEARCH ASSET** |
| `data/raw/runestone_sample.csv` | Runestone Interactive e-book interaction log sample ($13.0\text{ KB}$). | **RESEARCH ASSET** |
| `data/reference_answers.json` | Canonical rubric reference answers for natural language conceptual questions ($85.2\text{ KB}$). | **PRESERVE** |
| `data/hints.json` | Three-tier progressive scaffolding hint catalog across curriculum concepts ($53.0\text{ KB}$). | **PRESERVE** |
| `data/new_concepts.json` | Concept taxonomy, difficulty assignments, and prerequisite graphs ($32.2\text{ KB}$). | **PRESERVE** |
| `RECOVERY.md` | Authoritative Disaster Recovery Runbook and architectural verification guide. | **PRESERVE** |

