# Master Project Context: Adaptive Knowledge Tracing & Intelligent Tutor

**Document:** `project_handover/MASTER_PROJECT_CONTEXT.md`  
**Project:** Adaptive Knowledge Tracing (AKT) & Multimodal Intelligent Tutoring System  
**Audience:** Incoming Senior AI Engineers, Researchers, and AI Assistants (Google Gemini Pro)  
**Date of Audit & Handover:** November 2026  
**Workspace:** `/Users/abdulsamath/AKT-recovery-test copy`  

---

## 1. Project Overview & Mission

The **Adaptive Knowledge Tracing (AKT) Intelligent Tutor** is an advanced cognitive tutoring platform and educational research testbed. It models and traces a student's evolving knowledge state across programming concepts in real time, leveraging that knowledge state to adaptively scaffold and recommend personalized learning activities.

Unlike traditional computer-assisted instruction systems that rely solely on binary (correct/incorrect) responses from Multiple Choice Questions (MCQs), the AKT Intelligent Tutor implements **multimodal evidence collection** across:
1. **Multiple Choice Questions (MCQ):** Testing factual recall and conceptual discrimination.
2. **Short Answer Questions (Natural Language):** Assessing conceptual understanding via Sentence-BERT (`sentence-transformers/all-MiniLM-L6-v2`) semantic similarity against rubric reference answers.
3. **Python Programming Challenges:** Assessing procedural mastery and syntactic/runtime code correctness via AST inspection and hardened ephemeral Docker sandboxing.
4. **Behavioral Telemetry:** Capturing response latency, attempt counts, hints requested, and code revision iterations.

---

## 2. Research Problem Statement & Motivation

### The Research Problem
Traditional Knowledge Tracing (KT) algorithms—such as Bayesian Knowledge Tracing (BKT) and early Deep Knowledge Tracing (DKT)—were designed for uniform, binary-response problem solving (e.g., K-12 math worksheets). When applied to computer science education:
- **Binary Assumption Breakdown:** Code submissions and short conceptual explanations cannot be reduced to simple 0/1 binary outcomes without losing critical formative data.
- **Modality Neglect:** A student might grasp a concept conceptually (passing MCQs and short answers) but struggle syntactically or procedurally in code implementation.
- **Uncertainty Blindness:** Most neural KT models output deterministic point-estimate mastery probabilities without quantifying **epistemic uncertainty** (model confidence due to sparse student data) or **aleatoric uncertainty** (inherent randomness in student performance/guessing).
- **Security & Reliability Gaps:** Evaluating untrusted student Python code poses severe server security risks (code execution exploits, infinite loops, resource exhaustion), demanding fail-closed containerized execution.

### The Research Solution
This project addresses these fundamental challenges through a four-pillar architecture:
1. **Behavior-Aware Attention-based Knowledge Tracing (Behavior-AKT):** A deep self-attention network that contextualizes student interactions by fusing concept embeddings, activity modality identifiers, and continuous behavioral features.
2. **Epistemic & Aleatoric Uncertainty Estimation:** Applying Monte Carlo (MC) Dropout ($N=20$) during model inference to derive confidence bounds ($\sigma$) alongside mastery probabilities ($\mu$).
3. **Uncertainty-Guided Adaptive Policy Engine:** Formulating activity selection and concept routing using priority scores defined by $(1.0 - \mu) \times (1.0 + \sigma)$, driving students toward high-priority, high-uncertainty concepts while scaffolding difficulty dynamically.
4. **Unified Canonical Evidence Architecture:** Harmonizing multimodal evaluation outputs into a standardized schema (`UnifiedEvidenceRecord`) persisted atomically in MongoDB with strict privacy masking.

---

## 3. Core System Architecture

The project is structured as a modern full-stack web application with research-grade machine learning pipelines:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js 16.4.5)                       │
│  - React 19, Tailwind CSS 4, Monaco Code Editor, Recharts              │
│  - App Router: /dashboard, /practice, /history, /analytics, /adaptive  │
│  - Backend-For-Frontend (BFF) Pattern with Session Cookie Auth         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / JSON
                                    │ (Protected by Internal Service Secret)
┌───────────────────────────────────▼────────────────────────────────────┐
│                         BACKEND (FastAPI / api.py)                     │
│  - Async REST API with Motor (AsyncIOMotorClient)                      │
│  - Optimistic Concurrency Version Locking on student states            │
│  - Replay-safe Idempotent Score Ledger                                 │
│  - Real-Time Knowledge State Tracker (Exponential Moving Average)      │
│  - Ephemeral Docker Sandbox Code Runner (Quarantined Host Execution)   │
└──────────────────┬─────────────────────────────────┬───────────────────┘
                   │                                 │
┌──────────────────▼───────────────┐ ┌───────────────▼───────────────────┐
│       DATABASE (MongoDB)         │ │     RESEARCH ML MODELS (PyTorch)  │
│  - Database: akt_tutor           │ │  - DKT Baseline (LSTM)            │
│  - Collections:                  │ │  - AKT Baseline (Self-Attention)  │
│    * users (Argon2 hashes)       │ │  - Behavior-AKT (MC Dropout N=20) │
│    * student_states (Mastery)    │ │  - SBERT all-MiniLM-L6-v2         │
│    * scores (Ledger + Evidence)  │ │  - AST Code Analyzer              │
└──────────────────────────────────┘ └───────────────────────────────────┘
```

---

## 4. Non-Negotiable Safety & Architectural Boundaries

Incoming engineers and AI assistants must adhere to the following strict boundaries established across Phases 1 through 8G:

1. **Host-Process Code Quarantine (Phase 7B-2):**
   Student-submitted Python code must **NEVER** be executed inside the FastAPI host process using `exec()`, `eval()`, or host `subprocess` calls. Untrusted code is analyzed purely via Python AST parsing (`ast.parse`) for syntax, or routed to the ephemeral Docker sandbox runner (`sandbox_runner.py`). If Docker is offline, the system must fail closed to `PENDING_SECURE_EVALUATION`.
2. **Cognitive Model EMA Isolation:**
   Mastery updates in the live application use the Exponential Moving Average (EMA) Knowledge State Tracker. Only binary MCQ items (`activity_type=0`, `ADMITTED_BINARY`) update live knowledge state. Short Answer (`ADMITTED_FORMATIVE_ONLY`) and Coding (`PENDING_EVALUATION` / `PENDING_RESEARCH_POLICY`) are excluded from EMA updates until formal admission research policies are finalized.
3. **Option A Embedded Evidence Persistence (Phase 5):**
   Assessment item evidence records are persisted **embedded directly inside the `scores` document** in a single atomic write. Never introduce dual-write collections or background reconciliation daemons that compromise transaction atomicity.
4. **Data Privacy & Retention Masking:**
   Raw student source code and freeform answers must **NOT** be stored in the permanent database evidence ledger. They must be replaced with the standardized token `[EXCLUDED_PRIVACY_POLICY]` prior to persistence.
5. **Read-Only Database & Environment Protection:**
   Never restore database archives directly over active databases. Automated unit and regression tests must use isolated in-memory doubles (`InMemoryMotorDB`) rather than mutating live MongoDB instances.
6. **Phase 8G Closed Status:**
   Phase 8G (Full Portal Regression Audit across all 6 portal pages) is complete and **CLOSED**. Do not reopen completed phases without explicit evidence of an active regression.

