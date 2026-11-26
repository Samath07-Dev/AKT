# AKT Intelligent Tutor: Master Handover Documentation Index

**Document:** `project_handover/HANDOVER_INDEX.md`  
**Project:** Adaptive Knowledge Tracing (AKT) & Multimodal Intelligent Tutoring System  
**Audience:** Incoming Senior AI Engineers, Systems Architects, and Google Gemini Pro  
**Workspace:** `/Users/abdulsamath/AKT-recovery-test copy`  

---

## 1. Welcome & Document Navigation Guide

Welcome to the **Adaptive Knowledge Tracing (AKT) Intelligent Tutor** codebase. This handover dossier provides the complete architectural, historical, algorithmic, and operational context required to seamlessly continue development using Google Gemini Pro.

To maintain architectural integrity, avoid regressions, and adhere to strict research and security invariants, **incoming engineers and AI assistants must read the handover documents in the exact order outlined below:**

```
                                  START HERE
                                      │
                        ┌─────────────▼─────────────┐
                        │     HANDOVER_INDEX.md     │
                        └─────────────┬─────────────┘
                                      │
                        ┌─────────────▼─────────────┐
                        │ MASTER_PROJECT_CONTEXT.md │  (Pillars, Objectives & Topology)
                        └─────────────┬─────────────┘
                                      │
                        ┌─────────────▼─────────────┐
                        │   DEVELOPMENT_HISTORY.md  │  (Phase Matrix & Resolved Bugs)
                        └─────────────┬─────────────┘
                                      │
                        ┌─────────────▼─────────────┐
                        │ TECHNICAL_ARCHITECTURE.md │  (Next.js, FastAPI, MongoDB & Docker)
                        └─────────────┬─────────────┘
                                      │
                        ┌─────────────▼─────────────┐
                        │   ML_RESEARCH_CONTEXT.md  │  (DKT, AKT, Behavior-AKT & EMA)
                        └─────────────┬─────────────┘
                                      │
                        ┌─────────────▼─────────────┐
                        │     FILE_INVENTORY.md     │  (Classifications & Dependencies)
                        └─────────────┬─────────────┘
                                      │
                        ┌─────────────▼─────────────┐
                        │ CURRENT_STATUS_AND_       │  (Health Audit & Phase 6 Target)
                        │ PENDING_WORK.md           │
                        └─────────────┬─────────────┘
                                      │
                        ┌─────────────▼─────────────┐
                        │    DEVELOPMENT_RULES.md   │  (Safety Guardrails & Style)
                        └─────────────┬─────────────┘
                                      │
                        ┌─────────────▼─────────────┐
                        │ GEMINI_MASTER_HANDOVER_   │  (Prompt to Transfer Project)
                        │ PROMPT.md                 │
                        └───────────────────────────┘
```

---

## 2. Directory Map of Handover Documents

| # | Document File | Core Contents | Key Topics Covered |
| :-: | :--- | :--- | :--- |
| **1** | [`HANDOVER_INDEX.md`](file:///Users/abdulsamath/AKT-recovery-test%20copy/project_handover/HANDOVER_INDEX.md) | **Master Reading Guide** | Reading order, document map, and executive checklist. |
| **2** | [`MASTER_PROJECT_CONTEXT.md`](file:///Users/abdulsamath/AKT-recovery-test%20copy/project_handover/MASTER_PROJECT_CONTEXT.md) | **Project Mission & Overview** | Research motivation, multimodal problem statement, core hypotheses, and high-level system topology. |
| **3** | [`DEVELOPMENT_HISTORY.md`](file:///Users/abdulsamath/AKT-recovery-test%20copy/project_handover/DEVELOPMENT_HISTORY.md) | **Phase History & Bug Log** | Detailed phase matrix (Phases 1 through 8G), major bugs resolved (quarantine, version locking, SBERT bounds), and permanent decisions. |
| **4** | [`TECHNICAL_ARCHITECTURE.md`](file:///Users/abdulsamath/AKT-recovery-test%20copy/project_handover/TECHNICAL_ARCHITECTURE.md) | **Engineering Specifications** | Next.js 16.4.5 frontend, FastAPI backend, MongoDB document schemas (Option A embedded evidence), and ephemeral Docker sandbox security. |
| **5** | [`ML_RESEARCH_CONTEXT.md`](file:///Users/abdulsamath/AKT-recovery-test%20copy/project_handover/ML_RESEARCH_CONTEXT.md) | **AI & Cognitive Science** | DKT, AKT, Behavior-AKT with MC Dropout ($N=20$), real-time EMA knowledge tracker, $(1-\mu)(1+\sigma)$ adaptive selector, and CSEDM/Runestone datasets. |
| **6** | [`FILE_INVENTORY.md`](file:///Users/abdulsamath/AKT-recovery-test%20copy/project_handover/FILE_INVENTORY.md) | **Complete File Catalog** | Granular inventory of all application, model, analyzer, adapter, test, and dataset files with operational classifications. |
| **7** | [`CURRENT_STATUS_AND_PENDING_WORK.md`](file:///Users/abdulsamath/AKT-recovery-test%20copy/project_handover/CURRENT_STATUS_AND_PENDING_WORK.md) | **Current Health & Roadmap** | Verified test status (112 passing tests, TypeScript clean), roadmap tasks, and Phase 6 recommendations. |
| **8** | [`DEVELOPMENT_RULES.md`](file:///Users/abdulsamath/AKT-recovery-test%20copy/project_handover/DEVELOPMENT_RULES.md) | **Assistant Guidelines** | Working style preferences, non-negotiable safety invariants, and standard verification commands. |
| **9** | [`GEMINI_MASTER_HANDOVER_PROMPT.md`](file:///Users/abdulsamath/AKT-recovery-test%20copy/project_handover/GEMINI_MASTER_HANDOVER_PROMPT.md) | **Direct Handover Prompt** | Ready-to-copy master prompt instructing Gemini Pro to adopt the project persona and continue development safely. |

---

## 3. Executive Status & Safety Summary

- **Active Workspace:** `/Users/abdulsamath/AKT-recovery-test copy`
- **Current Phase:** Phase 5 is **COMPLETE & VERIFIED**. Phase 8G is **CLOSED**.
- **Next Phase:** Phase 6 (Asynchronous Coding Evaluation & Sandbox Reconciliation Planning).
- **Test Health:** **112 passing unit/regression tests** (64 evidence tests, 48 backend/engine tests, 0 failures).
- **Frontend Health:** TypeScript typecheck (`npx tsc --noEmit`) passes with 0 errors. Next.js production build verified.
- **Safety Invariant #1:** Student Python code must **NEVER** execute on the host process (`exec()`, `eval()`, host `subprocess` permanently quarantined).
- **Safety Invariant #2:** Live EMA mastery state updates strictly via binary MCQ items (`activity_type=0`). Short Answer and Coding are excluded from EMA updates.
- **Safety Invariant #3:** Option A embedded evidence persistence inside `scores` documents ensures single atomic document writes without dual-write drift.
- **Safety Invariant #4:** Student code and freeform answers are masked with `[EXCLUDED_PRIVACY_POLICY]` in permanent MongoDB ledgers.
- **Safety Invariant #5:** Never mutate active production MongoDB databases or access original backups (`/Users/abdulsamath/AKT-recovery-backups`).

