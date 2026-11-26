# Technical Architecture & Systems Engineering

**Document:** `project_handover/TECHNICAL_ARCHITECTURE.md`  
**Project:** Adaptive Knowledge Tracing (AKT) & Multimodal Intelligent Tutoring System  
**Audience:** Incoming Senior AI Engineers, Systems Architects, and Google Gemini Pro  

---

## 1. System Topology Overview

The AKT Intelligent Tutor is architected around a decoupled, modern three-tier web topology designed for educational research, cognitive modeling, and high-concurrency student interactions:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CLIENT / WEB BROWSER                            │
│  Interactive UI: Monaco Editor, SVG Knowledge Radars, Velocity Charts  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / HTTPS (Port 3000)
                                    │ Same-Site HTTP-Only Cookies (akt_session)
┌───────────────────────────────────▼────────────────────────────────────┐
│                    NEXT.JS FRONTEND LAYER (App Router)                 │
│  - Runtime: Node.js v25+ / Next.js 16.4.5 / React 19 / Tailwind 4      │
│  - BFF API Routes: /api/auth/*, /api/student/*, /api/practice/*        │
│  - Role: Server-Side Cookie Auth, API Proxy, Request Validation        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Loopback HTTP (127.0.0.1:8000)
                                    │ Headers: X-Internal-Service-Secret,
                                    │          X-Authenticated-Student-Id
┌───────────────────────────────────▼────────────────────────────────────┐
│                     FASTAPI BACKEND ENGINE (api.py)                    │
│  - Runtime: Python 3.13.9 / Uvicorn ASGI Server                        │
│  - Concurrency: Per-Student asyncio.Lock + MongoDB Optimistic Locking  │
│  - Knowledge Tracker: Exponential Moving Average (EMA) State Tracker   │
│  - Adaptive Engine: Priority-Score Selector & Difficulty Scaffolding   │
│  - Evaluators: MCQ Analyzer, SBERT SentenceTransformer, AST Analyzer   │
└──────────────────┬─────────────────────────────────┬───────────────────┘
                   │ Motor (AsyncIO MongoDB Driver)  │ Docker CLI / Unix Socket
┌──────────────────▼───────────────┐ ┌───────────────▼───────────────────┐
│         MONGODB DATABASE         │ │      EPHEMERAL DOCKER RUNNER      │
│  Port: 27017 (akt_tutor)         │ │  Image: python:3.13-slim@sha256.. │
│  - users (Argon2 hashes)         │ │  Limits: 5s timeout, 128MB RAM    │
│  - student_states (Mastery)      │ │  Security: Read-only root, non-   │
│  - scores (Ledger + Evidence)    │ │            root, no network       │
└──────────────────────────────────┘ └───────────────────────────────────┘
```

---

## 2. Frontend Architecture (Next.js 16.4.5)

### Tech Stack & Tooling
- **Framework:** Next.js 16.4.5 with App Router (`frontend/src/app`)
- **UI Library:** React 19.3.1
- **Styling:** Tailwind CSS 4.3.5 with PostCSS 8.5.32
- **Code Editor:** Monaco Editor (`@monaco-editor/react` 4.7.0, `monaco-editor` 0.57.0)
- **Data Visualization:** Recharts 3.10.1 (SVG-based Knowledge Radar & Learning Velocity Charts)
- **Icons:** Lucide React 1.70.0
- **TypeScript:** TypeScript 5.7.3 in strict mode (`tsconfig.json`)

### Application Pages & Routing Directory

All portal pages are grouped under the `(portal)` route group and protected by the portal layout and client shell (`portal-client-shell.tsx`):

| Route | Page File | Purpose & Main Components |
| :--- | :--- | :--- |
| `/login` | `src/app/(auth)/login/page.tsx` | Student sign-in form. Calls `/api/auth/login`, issues HTTP-only `akt_session` JWT cookie upon Argon2 password verification. |
| `/register` | `src/app/(auth)/register/page.tsx` | Student registration. Calls `/api/auth/register`, seeds initial student knowledge state with prior mastery ($0.30$) and uncertainty ($0.50$). |
| `/dashboard` | `src/app/(portal)/dashboard/page.tsx` | Main student hub. Renders `KnowledgeRadarChart`, learning streak metrics, overall curriculum mastery percentage, and recommended activity callout. |
| `/practice` | `src/app/(portal)/practice/page.tsx` | Multimodal assessment arena. Renders `MCQCard` (3 questions), `ShortAnswerBox` (SBERT feedback), `MonacoCodeWorkspace` (AST check & sandbox preview), and `ProgressiveHintPanel`. |
| `/history` | `src/app/(portal)/history/page.tsx` | Historical submissions ledger. Displays `HistoryTable` with timestamp, concept, bundle average score, and coding evaluation status badges (`PENDING_SECURE_EVALUATION`, `EVALUATED`, `ERROR`). |
| `/analytics` | `src/app/(portal)/analytics/page.tsx` | Deep-dive learning analytics. Renders `LearningVelocityChart` showing sequential mastery shifts per concept and uncertainty distribution. |
| `/adaptive-learning` | `src/app/(portal)/adaptive-learning/page.tsx` | Curriculum navigation map. Visualizes concept prerequisite trees, current difficulty level per concept, and priority ranking $(1 - \mu) \times (1 + \sigma)$. |
| `/profile` | `src/app/(portal)/profile/page.tsx` | Account details, student ID display, session metadata, and secure logout action. |

### Backend-For-Frontend (BFF) API Routes

The Next.js layer acts as a secure BFF, preventing direct client exposure of the backend API secret:
- `/api/auth/login`: Verifies student credentials against FastAPI `/login`, signs JWT session cookie.
- `/api/auth/register`: Proxies registration to FastAPI `/register`.
- `/api/auth/me`: Decodes session cookie and returns authenticated student profile.
- `/api/auth/logout`: Clears session cookie and invalidates client session.
- `/api/student/mastery`: Fetches `/api/v1/student/{id}/mastery` with internal secret.
- `/api/student/history`: Fetches `/api/v1/student/{id}/history` with internal secret.
- `/api/practice/bundle/[concept]`: Fetches assessment bundle definition for target concept.
- `/api/practice/evaluate`: Proxies complete bundle submission to FastAPI `/api/v1/evaluate_bundle`.
- `/api/practice/sandbox-status`: Checks Docker sandbox runner availability.

---

## 3. Backend Architecture (FastAPI / api.py)

### Technology & Runtime
- **Framework:** FastAPI with Uvicorn ASGI server
- **Language Version:** Python 3.13.9
- **Validation Engine:** Pydantic 2.14.3
- **Async Driver:** Motor 3.7.0 (AsyncIOMotorClient)
- **Password Hashing:** Argon2 via `argon2-cffi`
- **NLP Semantic Evaluator:** `sentence-transformers/all-MiniLM-L6-v2` via PyTorch 2.6.0

### Concurrency, Locking & State Management
To guarantee mathematical consistency and eliminate race conditions across student sessions:
1. **Per-Student In-Memory Mutex (`asyncio.Lock`):**
   - Managed via `get_student_lock(student_id: str)`.
   - Serializes concurrent requests for the same student within a single FastAPI worker.
2. **Optimistic Version Locking on `student_states`:**
   - Every `student_states` document maintains an integer `version` field.
   - When updating mastery:
     ```python
     res = await db["student_states"].update_one(
         {"student_id": student_id, "version": expected_version},
         {"$set": {"knowledge_state": ..., "version": expected_version + 1}}
     )
     if res.matched_count == 0:
         raise HTTPException(status_code=409, detail="Mastery state version conflict.")
     ```
   - In case of conflict (HTTP 409), staged cache mutations are rolled back, and the latest persisted state is reloaded from MongoDB.
3. **Replay-Safe Idempotent Score Ledger (`scores`):**
   - Unique index on `submission_id`.
   - Duplicate submissions are caught before execution; cached scores and embedded evidence records are served without re-applying knowledge state updates.

---

## 4. Database Architecture (MongoDB)

### Instances & Databases
- **Production Database:** `akt_tutor` on `mongodb://127.0.0.1:27017`
- **Test Database:** `akt_tutor_test` (used exclusively in isolated integration tests with cleanup)

### Collections & Schemas

#### 1. `users` Collection
Stores student authentication credentials and profile information.
```json
{
  "_id": ObjectId("..."),
  "student_id": "S001",
  "username": "student_alice",
  "password_hash": "$argon2id$v=19$m=65536,t=3,p=4$...",
  "full_name": "Alice Smith",
  "email": "alice@example.com",
  "created_at": "2026-11-01T10:00:00.000Z"
}
```
*Key Index:* `{ "username": 1 }` (unique), `{ "student_id": 1 }` (unique).

#### 2. `student_states` Collection
Maintains real-time mastery probabilities ($\mu$) and uncertainties ($\sigma$) per knowledge component.
```json
{
  "_id": ObjectId("..."),
  "student_id": "S001",
  "version": 14,
  "concept_difficulties": {
    "Variables": "medium",
    "Conditionals": "hard",
    "Loops": "easy"
  },
  "knowledge_state": {
    "Variables": {
      "concept_id": 1,
      "mastery": 0.72,
      "uncertainty": 0.28,
      "attempts": 6,
      "history": [
        {
          "submission_id": "sub_S001_8f9a2",
          "evidence_score": 1.0,
          "activity_type": 0,
          "response_time_sec": 12.5,
          "difficulty": "medium",
          "timestamp": "2026-11-17T09:30:00.000Z"
        }
      ]
    }
  },
  "updated_at": "2026-11-17T09:30:01.000Z"
}
```
*Key Index:* `{ "student_id": 1 }` (unique).

#### 3. `scores` Collection (Option A Embedded Architecture)
Maintains the complete transaction ledger for assessment bundles along with granular multimodal evidence items.
```json
{
  "_id": ObjectId("..."),
  "submission_id": "sub_S001_8f9a2b3c4d5e",
  "student_id": "S001",
  "concept": "Variables",
  "difficulty": "medium",
  "bundle_average_score": 0.76,
  "mcq_scores": [1.0, 1.0, 0.0],
  "short_answer_score": 0.85,
  "code_score": 0.0,
  "next_difficulty": "medium",
  "scaffolding_reasoning": "Performance demonstrates moderate mastery.",
  "timestamp": "2026-11-17T09:30:00.000Z",
  "bkt_processed": true,
  "bkt_processed_at": "2026-11-17T09:30:00.250Z",
  "bkt_observations_applied": 3,
  "code_status": "PENDING_SECURE_EVALUATION",
  "code_execution_status": "NOT_PERFORMED",
  "code_tests_passed": 0,
  "code_tests_total": 2,
  "evidence_records": [
    {
      "evidence_id": "ev_sub_S001_8f9a2b3c4d5e_mcq_1",
      "submission_id": "sub_S001_8f9a2b3c4d5e",
      "bundle_id": "bundle_variables_medium",
      "student_id": "S001",
      "item_id": "Variables_MCQ_Medium_1",
      "concept_id": "python:variables",
      "modality": "MCQ",
      "evaluator_version": "mcq_analyzer_v1.0",
      "evaluation_lifecycle": "EVALUATED_SUCCESS",
      "admission_status": "ADMITTED_BINARY",
      "raw_score": 1.0,
      "maximum_possible_score": 1.0,
      "normalized_score": 1.0,
      "correctness": true,
      "modality_details": {
        "mcq": { "selected_option_id": "B", "correct_option_id": "B" },
        "short_answer": null,
        "coding": null
      }
    },
    {
      "evidence_id": "ev_sub_S001_8f9a2b3c4d5e_sa_1",
      "submission_id": "sub_S001_8f9a2b3c4d5e",
      "bundle_id": "bundle_variables_medium",
      "student_id": "S001",
      "item_id": "Variables_SA_Medium_1",
      "concept_id": "python:variables",
      "modality": "SHORT_ANSWER",
      "evaluator_version": "sentence-transformers/all-MiniLM-L6-v2",
      "evaluation_lifecycle": "EVALUATED_SUCCESS",
      "admission_status": "ADMITTED_FORMATIVE_ONLY",
      "raw_score": 0.85,
      "maximum_possible_score": 1.0,
      "normalized_score": 0.85,
      "correctness": null,
      "modality_details": {
        "mcq": null,
        "short_answer": {
          "submitted_text": "[EXCLUDED_PRIVACY_POLICY]",
          "reference_answer_id": "ref_variables_01",
          "semantic_similarity_raw": 0.85,
          "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
        },
        "coding": null
      }
    },
    {
      "evidence_id": "ev_sub_S001_8f9a2b3c4d5e_code_1",
      "submission_id": "sub_S001_8f9a2b3c4d5e",
      "bundle_id": "bundle_variables_medium",
      "student_id": "S001",
      "item_id": "Variables_Code_Medium_1",
      "concept_id": "python:variables",
      "modality": "CODING",
      "evaluator_version": "sandbox_runner_v2.0",
      "evaluation_lifecycle": "PENDING_EVALUATION",
      "admission_status": "PENDING_EVALUATION",
      "raw_score": null,
      "maximum_possible_score": null,
      "normalized_score": null,
      "correctness": null,
      "modality_details": {
        "mcq": null,
        "short_answer": null,
        "coding": {
          "submitted_code": "[EXCLUDED_PRIVACY_POLICY]",
          "tests_run": null,
          "tests_passed": null,
          "tests_failed": null,
          "tests_not_run": 2,
          "total_test_cases": 2,
          "infrastructure_error_message": null
        }
      }
    }
  ]
}
```
*Key Indexes:*
- `{ "submission_id": 1 }` (**unique**, primary idempotency key).
- `{ "student_id": 1, "timestamp": -1 }` (powers history retrieval).

---

## 5. Security Architecture

1. **Host-Process Code Quarantine (Phase 7B-2):**
   - Untrusted student Python code is strictly prevented from executing inside the backend process.
   - AST parser (`ast.parse`) performs static syntax verification only.
2. **Ephemeral Docker Sandbox Runner (`sandbox_runner.py`):**
   - Uses immutable, digest-pinned image: `python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90`.
   - Hard execution limits: Non-root user, `--read-only` root filesystem, `--net=none` (no network), memory capped at $128\text{ MB}$, container timeout capped at $5.0\text{ seconds}$.
   - Fail-closed security: If Docker is unavailable or `SANDBOX_OFFLINE=1`, returns `PENDING_SECURE_EVALUATION` with null score.
3. **Data Privacy Policy Token Masking:**
   - Standardized token `[EXCLUDED_PRIVACY_POLICY]` replaces student Python source code and natural language text answers prior to database persistence.
4. **Service Boundary Authentication & IDOR Protection:**
   - Next.js communicates with FastAPI using a cryptographically secure 32-byte hex key passed in `X-Internal-Service-Secret`.
   - Student authorization checks (`verify_student_authorization`) ensure authenticated students can access only their own records, preventing Insecure Direct Object Reference (IDOR) attacks.

