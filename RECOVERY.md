# AKT Tutor Disaster Recovery Runbook

> [!WARNING]
> **Operational Safety Notice:**
> - The procedures documented herein represent an architectural recovery guide for rebuilding the AKT Tutor environment.
> - **End-to-end recovery has NOT been executed or claimed as successfully tested in production.**
> - **NEVER** restore database archives directly over an active production instance. Always restore into an isolated recovery instance first.
> - The two database archives (`akt_tutor.archive.gz` and `akt_tutor_test.archive.gz`) are **independent, point-in-time snapshots** captured sequentially; they do NOT form a globally synchronized cross-database distributed transaction.
> - Knowledge tracing in AKT Tutor utilizes an Exponential Moving Average (EMA) mastery tracker; it is NOT a Bayesian posterior state calculation.

---

## 1. Recovery Checkpoint Inventory

Disaster recovery relies on three cryptographically verified checkpoints stored outside the repository at:
`/Users/abdulsamath/AKT-recovery-backups/`

```
AKT-recovery-backups/
├── phase38-research/          # Research datasets & pretrained models (2.44 GB, 13 files)
│   ├── MANIFEST.txt           # SHA-256 verification manifest
│   ├── data/raw/              # Raw CSEDM & Runestone CSV datasets
│   ├── data/processed/        # akt_baseline.pt weights & akt_metadata.json
│   ├── src/models/            # Architecture definitions (DKT, AKT, Behavior-AKT)
│   └── run_presentation_experiments.py
├── phase40-application/       # Application source code & tests (0.97 MB, 94 files)
│   ├── SHA256SUMS.txt         # SHA-256 verification manifest
│   ├── api.py                 # FastAPI backend server
│   ├── conftest.py            # Pytest test harness
│   ├── requirements.txt       # Abstract Python dependency bounds
│   ├── data/                  # Question bank & curriculum reference answers
│   ├── frontend/              # Complete Next.js frontend (components, pages, package-lock.json)
│   ├── legacy/                # Preserved legacy monolith baseline
│   ├── scripts/               # Historical reconciliation scripts
│   └── src/                   # Analyzers, preprocessor, and EMA knowledge state engine
└── phase42-database/          # Standalone MongoDB archives (28.2 KB, Mode 0700/0600)
    ├── SHA256SUMS.txt         # SHA-256 verification manifest
    ├── akt_tutor.archive.gz   # Production database dump (users, student_states, scores)
    └── akt_tutor_test.archive.gz # Test database dump (users, student_states, scores, test marker)
```

---

## 2. Step-by-Step Restoration Procedure

### Step 1: Restore Application Source Code *(Proposed Procedure)*
Extract or copy all 94 application files from `phase40-application/` into the target workspace root:

```bash
TARGET_DIR="/path/to/restored-AKT-project"
mkdir -p "$TARGET_DIR"
cp -R /Users/abdulsamath/AKT-recovery-backups/phase40-application/* "$TARGET_DIR"/
cd "$TARGET_DIR"

# Verify source file integrity against preserved manifest
shasum -a 256 -c SHA256SUMS.txt
```

### Step 2: Restore Research Assets *(Proposed Procedure)*
Copy raw datasets and pretrained PyTorch weights from `phase38-research/` into the project data directory:

```bash
mkdir -p "$TARGET_DIR/data/raw" "$TARGET_DIR/data/processed"
cp -R /Users/abdulsamath/AKT-recovery-backups/phase38-research/data/raw/* "$TARGET_DIR/data/raw/"
cp -R /Users/abdulsamath/AKT-recovery-backups/phase38-research/data/processed/* "$TARGET_DIR/data/processed/"
```

### Step 3: Set Up Python 3.13 Runtime & Dependencies *(Tested Configuration)*
The project runs on Python `3.13.9`. To ensure reproducible builds and eliminate dependency drift, install from `requirements.lock`:

```bash
# Create and activate an isolated virtual environment
python3.13 -m venv .venv
source .venv/bin/activate

# Upgrade pip build tools
pip install --upgrade pip setuptools wheel

# Install exact pinned dependencies from lockfile
pip install -r requirements.lock
```

### Step 4: Set Up Node.js & Frontend Toolchain *(Tested Configuration)*
Frontend dependencies require Node.js `v25.2.1+` and npm `11.6.2+`. Build reproducibly using the committed `package-lock.json`:

```bash
cd "$TARGET_DIR/frontend"

# Clean reproducible install based on exact package-lock hashes
npm ci

# Optional: compile production Next.js build
npm run build
cd "$TARGET_DIR"
```

### Step 5: Environment Variable Configuration *(Tested Security Architecture)*
AKT Tutor enforces a shared internal service secret between Next.js and FastAPI. Sensitive keys must be generated with high entropy.

1. **Create Frontend Environment (`frontend/.env.local`):**
   ```bash
   cd "$TARGET_DIR/frontend"
   cp .env.example .env.local
   chmod 600 .env.local
   ```

2. **Generate Cryptographic Secrets:**
   ```bash
   # Generate 32-character hex secrets
   NEW_SERVICE_SECRET=$(openssl rand -hex 32)
   NEW_JWT_SECRET=$(openssl rand -hex 32)
   ```

3. **Populate `frontend/.env.local`:**
   ```env
   # Loopback URL for Next.js BFF server calls
   FASTAPI_BACKEND_URL=http://127.0.0.1:8000
   NEXT_PUBLIC_API_URL=http://127.0.0.1:8000

   # Internal Service Authentication Secret (Must match FastAPI)
   INTERNAL_SERVICE_SECRET=<PASTE_NEW_SERVICE_SECRET_HERE>

   # Server-Only JWT Session Secret for student cookies
   JWT_SECRET=<PASTE_NEW_JWT_SECRET_HERE>
   ```

> [!WARNING]
> Generating a new `JWT_SECRET` invalidates all prior student browser cookies. Students must log in again, but user accounts and password hashes in MongoDB remain unaffected.

---

## 3. Database Restoration to Isolated Instance

> [!CAUTION]
> **DO NOT restore directly into an active production MongoDB instance.**
> Restoring with `--drop` will destroy existing database state. Always restore to a temporary isolated port or sandbox instance first to verify counts.

### Step 6: Start Isolated MongoDB Recovery Daemon *(Tested Isolation)*
```bash
# Create an isolated sandbox database directory
mkdir -p /tmp/akt_recovery_mongo
chmod 700 /tmp/akt_recovery_mongo

# Launch MongoDB on temporary isolated port 27018
mongod --port 27018 --dbpath /tmp/akt_recovery_mongo --bind_ip 127.0.0.1
```

### Step 7: Restore Database Archives *(Tested Restore Command)*
Restore the independent archives from `phase42-database/`:

```bash
BACKUP_DIR="/Users/abdulsamath/AKT-recovery-backups/phase42-database"

# 1. Restore Production Database (akt_tutor)
mongorestore --host 127.0.0.1 --port 27018 \
  --archive="$BACKUP_DIR/akt_tutor.archive.gz" --gzip

# 2. Restore Test Database (akt_tutor_test)
mongorestore --host 127.0.0.1 --port 27018 \
  --archive="$BACKUP_DIR/akt_tutor_test.archive.gz" --gzip
```

### Step 8: Verify Restored Document Counts *(Required Audit Assertion)*
Execute read-only verification queries against port `27018`:

```bash
# Verify Production (akt_tutor)
mongosh --quiet "mongodb://127.0.0.1:27018/akt_tutor" --eval "
  console.log('users:', db.users.countDocuments());
  console.log('student_states:', db.student_states.countDocuments());
  console.log('scores:', db.scores.countDocuments());
"
```
*Expected production counts:*
- `users`: **63**
- `student_states`: **54**
- `scores`: **94**

```bash
# Verify Test Database (akt_tutor_test)
mongosh --quiet "mongodb://127.0.0.1:27018/akt_tutor_test" --eval "
  console.log('users:', db.users.countDocuments());
  console.log('student_states:', db.student_states.countDocuments());
  console.log('scores:', db.scores.countDocuments());
  console.log('_test_initialization:', db._test_initialization.countDocuments());
"
```
*Expected test counts:*
- `users`: **19**
- `student_states`: **57**
- `scores`: **60**
- `_test_initialization`: **1**

---

## 4. Service Startup & Functional Verification

### Step 9: Launch FastAPI Backend *(Tested Configuration)*
Export matching environment variables and launch uvicorn:

```bash
cd "$TARGET_DIR"
source .venv/bin/activate

export INTERNAL_SERVICE_SECRET="<MATCHING_SERVICE_SECRET>"
export MONGO_URI="mongodb://127.0.0.1:27017/"
export MONGO_DB_NAME="akt_tutor"

python3 -m uvicorn api:app --host 127.0.0.1 --port 8000
```

### Step 10: Launch Next.js Frontend *(Tested Configuration)*
```bash
cd "$TARGET_DIR/frontend"
npm run dev
# Or for production: npm run start (listening on http://127.0.0.1:3000)
```

### Step 11: End-to-End Verification Checklist *(Proposed Procedure)*
1. **Authentication:** Navigate to `http://127.0.0.1:3000/login`. Log in using an existing student account. Confirm Argon2 password validation succeeds and session cookie is issued.
2. **Student Dashboard:** Confirm dashboard renders actual persisted mastery states (e.g. S009 historical concepts) rather than default priors or demo history.
3. **Assessment History:** Open `/history`. Confirm sessions render matching persisted records in `scores` collection.
4. **Analytics:** Open `/analytics`. Confirm knowledge radar and learning velocity charts render from live database metrics.
5. **Adaptive Practice:** Open `/practice`. Confirm recommendation engine dynamically generates questions without code execution errors.

---

## 5. Offline Hugging Face Model Cache Requirement

In `api.py`, `ShortAnswerAnalyzer` instantiates semantic similarity using Hugging Face:
```python
short_answer_analyzer = ShortAnswerAnalyzer(model_name="sentence-transformers/all-MiniLM-L6-v2")
```

- **Network Requirement:** On first startup, `sentence-transformers` attempts to fetch weights from Hugging Face Hub (`huggingface.co`).
- **Air-Gapped / Offline Recovery:** If recovering in an environment without internet access, pre-populate the Hugging Face cache directory:
  ```bash
  # Standard cache path on macOS / Linux
  ~/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/
  ```
  Or point `HF_HOME` to a restored model cache before launching FastAPI.

---

## 6. Backup Security & File Permissions

Backup archives in `phase42-database/` contain student user records and Argon2 password hashes. Operators must enforce POSIX permission restrictions:

```bash
# Restrict backup directories to owner-only read/write/execute
chmod 700 /Users/abdulsamath/AKT-recovery-backups/phase42-database

# Restrict archive files to owner-only read/write
chmod 600 /Users/abdulsamath/AKT-recovery-backups/phase42-database/*.archive.gz
chmod 600 /Users/abdulsamath/AKT-recovery-backups/phase42-database/SHA256SUMS.txt
chmod 600 "$TARGET_DIR/frontend/.env.local"
```

