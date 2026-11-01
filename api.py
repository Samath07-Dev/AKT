"""
api.py

FastAPI Microservice for Adaptive Knowledge Tracing & Multi-Response Student Behavior Modeling.
Exposes endpoints for interaction log ingestion, 5-question concept assessment bundle evaluation,
real-time knowledge state updating, MC Dropout uncertainty estimation, uncertainty-guided activity recommendation,
and difficulty scaffolding ('easy', 'medium', 'hard').

Integrates overhauled data/reference_answers.json:
- 10 Python KCs (Variables, Conditionals, Loops, Functions, Arrays, Syntax, OOP, Dictionaries, File Handling, Exception Handling)
- 3 Difficulty Levels per KC ('easy', 'medium', 'hard')
- Exactly 3 Easy MCQs, 3 Medium MCQs, 3 Hard MCQs per KC (9 MCQs each)
- Exactly 1 Easy, 1 Medium, 1 Hard Short Answer per KC (SBERT evaluated)
- Exactly 1 Easy, 1 Medium, 1 Hard Coding task per KC (with unit test cases)
- Difficulty Scaffolding Policy: Evidence Score < 0.5 routes down; Evidence Score > 0.8 routes up.
"""

import os
import json
import hashlib
import uuid
import asyncio
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient

from src.analyzers import MCQAnalyzer, CodeAnalyzer, ShortAnswerAnalyzer
from src.engine import KnowledgeStateTracker, AdaptiveActivitySelector
from src.models import BehaviorAKT

app = FastAPI(
    title="Adaptive Knowledge Tracing API",
    description="Multi-Response Student Behaviour Modeling & Uncertainty-Guided Adaptive Learning Engine API with Difficulty Scaffolding",
    version="2.0.0"
)

# MongoDB Configuration & Motor Async Client
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "akt_tutor")

_motor_client: Optional[AsyncIOMotorClient] = None
_motor_loop = None

def get_motor_client() -> AsyncIOMotorClient:
    """Returns motor AsyncIOMotorClient instance connected to MongoDB for the current event loop."""
    global _motor_client, _motor_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _motor_client is None or _motor_loop is None or (_motor_loop is not None and (_motor_loop.is_closed() or _motor_loop != current_loop)):
        _motor_loop = current_loop
        _motor_client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    return _motor_client

def get_motor_db():
    """Returns asynchronous Motor database handle."""
    return get_motor_client()[MONGO_DB_NAME]

def get_mongo_db():
    """Returns synchronous MongoDB database handle for fallback or synchronous utilities."""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=1500)
        client.admin.command('ping')
        return client[MONGO_DB_NAME]
    except Exception:
        return None

def hash_password(password: str) -> str:
    """Computes SHA-256 hash for secure student credential storage."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

_in_memory_users: Dict[str, Dict[str, Any]] = {}
_in_memory_scores: Dict[str, List[Dict[str, Any]]] = {}
_in_memory_student_states: Dict[str, Dict[str, Any]] = {}

DEFAULT_KCS = ["Variables", "Conditionals", "Loops", "Functions", "Arrays", "Syntax", "OOP", "Dictionaries", "File Handling", "Exception Handling"]

def get_initial_mastery_state() -> Dict[str, Dict[str, Any]]:
    """Returns baseline mastery state for all Python KCs."""
    return {
        kc: {
            "mastery": 0.30,
            "uncertainty": 0.50,
            "history": []
        }
        for kc in DEFAULT_KCS
    }

def get_initial_concept_difficulties() -> Dict[str, str]:
    """Returns default medium difficulty for all Python KCs."""
    return {
        kc: "medium"
        for kc in DEFAULT_KCS
    }

_student_trackers: Dict[str, KnowledgeStateTracker] = {}

async def get_student_tracker(student_id: str) -> KnowledgeStateTracker:
    """Retrieves or creates a KnowledgeStateTracker for an individual student, restoring state from MongoDB if available."""
    if student_id not in _student_trackers:
        stu_tracker = KnowledgeStateTracker()
        try:
            db = get_motor_db()
            state_doc = await db["student_states"].find_one({"student_id": student_id})
            if state_doc and "knowledge_state" in state_doc:
                for c_name, c_data in state_doc["knowledge_state"].items():
                    stu_tracker.set_concept_state(
                        c_name,
                        mastery=float(c_data.get("mastery", 0.30)),
                        uncertainty=float(c_data.get("uncertainty", 0.50)),
                        history=c_data.get("history", [])
                    )
        except Exception:
            pass
        _student_trackers[student_id] = stu_tracker
    return _student_trackers[student_id]

async def persist_student_mastery_state(student_id: str, tracker_instance: KnowledgeStateTracker, concept_diff: Optional[Dict[str, str]] = None):
    """Persists individual student mastery state to MongoDB using motor."""
    state_dict = tracker_instance.get_knowledge_state()
    now_iso = datetime.now(timezone.utc).isoformat()
    update_payload = {
        "student_id": student_id,
        "knowledge_state": state_dict,
        "updated_at": now_iso
    }
    if concept_diff:
        update_payload["concept_difficulties"] = concept_diff
    try:
        db = get_motor_db()
        await db["student_states"].update_one(
            {"student_id": student_id},
            {"$set": update_payload},
            upsert=True
        )
        await db["users"].update_one(
            {"student_id": student_id},
            {"$set": {"mastery_state": state_dict, "updated_at": now_iso}}
        )
    except Exception:
        pass
    _in_memory_student_states[student_id] = update_payload

async def generate_student_id_async(db=None) -> str:
    """Generates a clean unique student_id (e.g. S001, S002) using motor."""
    if db is not None:
        try:
            count = await db["users"].count_documents({}) + 1
            cand = f"S{count:03d}"
            if not await db["users"].find_one({"student_id": cand}):
                return cand
        except Exception:
            pass
    count = len(_in_memory_users) + 1
    return f"S{count:03d}"

def generate_student_id(db=None) -> str:
    """Generates a clean unique student_id (e.g. S001, S002)."""
    if db is not None:
        try:
            count = db["users"].count_documents({}) + 1
            cand = f"S{count:03d}"
            if not db["users"].find_one({"student_id": cand}):
                return cand
        except Exception:
            pass
    count = len(_in_memory_users) + 1
    return f"S{count:03d}"

async def record_student_score_internal_async(
    student_id: str,
    concept: str,
    difficulty: str,
    bundle_average_score: float,
    mcq_scores: List[float],
    short_answer_score: float,
    code_score: float,
    next_difficulty: Optional[str] = None,
    scaffolding_reasoning: Optional[str] = None,
    timestamp: Optional[str] = None
):
    """Persists a student's assessment bundle score to MongoDB using motor."""
    record_entry = {
        "student_id": student_id,
        "concept": concept,
        "difficulty": difficulty,
        "bundle_average_score": float(bundle_average_score),
        "mcq_scores": [float(s) for s in mcq_scores],
        "short_answer_score": float(short_answer_score),
        "code_score": float(code_score),
        "next_difficulty": next_difficulty or difficulty,
        "scaffolding_reasoning": scaffolding_reasoning or "",
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat()
    }
    try:
        db = get_motor_db()
        await db["scores"].insert_one(dict(record_entry))
    except Exception:
        pass
    if student_id not in _in_memory_scores:
        _in_memory_scores[student_id] = []
    _in_memory_scores[student_id].insert(0, record_entry)

def record_student_score_internal(
    student_id: str,
    concept: str,
    difficulty: str,
    bundle_average_score: float,
    mcq_scores: List[float],
    short_answer_score: float,
    code_score: float,
    next_difficulty: Optional[str] = None,
    scaffolding_reasoning: Optional[str] = None,
    timestamp: Optional[str] = None
):
    """Persists a student's assessment bundle score to MongoDB and in-memory cache synchronously."""
    record_entry = {
        "student_id": student_id,
        "concept": concept,
        "difficulty": difficulty,
        "bundle_average_score": float(bundle_average_score),
        "mcq_scores": [float(s) for s in mcq_scores],
        "short_answer_score": float(short_answer_score),
        "code_score": float(code_score),
        "next_difficulty": next_difficulty or difficulty,
        "scaffolding_reasoning": scaffolding_reasoning or "",
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat()
    }
    db = get_mongo_db()
    if db is not None:
        try:
            db["scores"].insert_one(dict(record_entry))
        except Exception:
            pass
    if student_id not in _in_memory_scores:
        _in_memory_scores[student_id] = []
    _in_memory_scores[student_id].insert(0, record_entry)


# Load reference answers database (7 Python KCs, 3 difficulty levels each)
REF_ANSWERS_PATH = os.path.join("data", "reference_answers.json")

def load_reference_answers():
    if os.path.exists(REF_ANSWERS_PATH):
        with open(REF_ANSWERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

REFERENCE_ANSWERS = load_reference_answers()

# Initialize Core Services & Analyzers
tracker = KnowledgeStateTracker()
selector = AdaptiveActivitySelector()

mcq_analyzer = MCQAnalyzer()
code_analyzer = CodeAnalyzer()
short_answer_analyzer = ShortAnswerAnalyzer(model_name="sentence-transformers/all-MiniLM-L6-v2")

# Tracking attempted MCQs per student, concept, and difficulty level
student_attempted_mcqs: Dict[str, Dict[str, Dict[str, List[str]]]] = {}

# Tracking active difficulty per student and concept
student_concept_difficulty: Dict[str, Dict[str, str]] = {}

def get_next_mcq_for_student(student_id: str, concept: str, difficulty: str = "medium") -> Dict[str, Any]:
    """Cycles through unattempted MCQs for a given student, concept, and difficulty level."""
    diff = str(difficulty).lower().strip() if difficulty else "medium"
    kc_data = REFERENCE_ANSWERS.get(concept, REFERENCE_ANSWERS.get("Variables", {}))
    mcqs_container = kc_data.get("mcqs", {})

    if isinstance(mcqs_container, dict):
        mcqs = mcqs_container.get(diff, mcqs_container.get("medium", []))
    elif isinstance(mcqs_container, list):
        mcqs = mcqs_container
    else:
        mcqs = []

    if not mcqs:
        return {
            "id": f"{concept}_MCQ_{diff}_default",
            "difficulty": diff,
            "question": f"Sample {diff.title()} MCQ for {concept}",
            "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],
            "correct_option": "A"
        }

    if student_id not in student_attempted_mcqs:
        student_attempted_mcqs[student_id] = {}
    if concept not in student_attempted_mcqs[student_id]:
        student_attempted_mcqs[student_id][concept] = {}
    if diff not in student_attempted_mcqs[student_id][concept]:
        student_attempted_mcqs[student_id][concept][diff] = []

    attempted_list = student_attempted_mcqs[student_id][concept][diff]
    unattempted = [m for m in mcqs if m["id"] not in attempted_list]

    if not unattempted:
        student_attempted_mcqs[student_id][concept][diff] = []
        unattempted = mcqs

    next_mcq = unattempted[0]
    return next_mcq

def mark_mcq_attempted(student_id: str, concept: str, mcq_id: str, difficulty: str = "medium"):
    diff = str(difficulty).lower().strip() if difficulty else "medium"
    if student_id not in student_attempted_mcqs:
        student_attempted_mcqs[student_id] = {}
    if concept not in student_attempted_mcqs[student_id]:
        student_attempted_mcqs[student_id][concept] = {}
    if diff not in student_attempted_mcqs[student_id][concept]:
        student_attempted_mcqs[student_id][concept][diff] = []
    if mcq_id not in student_attempted_mcqs[student_id][concept][diff]:
        student_attempted_mcqs[student_id][concept][diff].append(mcq_id)

def get_short_answer_for_concept(concept: str, difficulty: str = "medium") -> Dict[str, Any]:
    diff = str(difficulty).lower().strip() if difficulty else "medium"
    kc_data = REFERENCE_ANSWERS.get(concept, REFERENCE_ANSWERS.get("Variables", {}))
    sa_container = kc_data.get("short_answer", {})
    if isinstance(sa_container, dict):
        if diff in sa_container:
            return sa_container[diff]
        elif "medium" in sa_container:
            return sa_container["medium"]
        elif "question" in sa_container:
            return sa_container
        elif sa_container:
            return list(sa_container.values())[0]
    return {
        "id": f"{concept}_SA_{diff}_default",
        "difficulty": diff,
        "question": f"Explain the core concept of {concept}.",
        "reference_answer": "Reference rubric text."
    }

def get_coding_task_for_concept(concept: str, difficulty: str = "medium") -> Dict[str, Any]:
    diff = str(difficulty).lower().strip() if difficulty else "medium"
    kc_data = REFERENCE_ANSWERS.get(concept, REFERENCE_ANSWERS.get("Variables", {}))
    code_container = kc_data.get("coding", {})
    if isinstance(code_container, dict):
        if diff in code_container:
            return code_container[diff]
        elif "medium" in code_container:
            return code_container["medium"]
        elif "problem" in code_container:
            return code_container
        elif code_container:
            return list(code_container.values())[0]
    return {
        "id": f"{concept}_Code_{diff}_default",
        "difficulty": diff,
        "problem": f"Write Python code demonstrating {concept}.",
        "template": "def solution():\n    pass\n",
        "test_cases": []
    }

def find_mcq_by_id(concept: str, mcq_id: str) -> Optional[Tuple[Dict[str, Any], str]]:
    kc_data = REFERENCE_ANSWERS.get(concept, REFERENCE_ANSWERS.get("Variables", {}))
    mcqs_container = kc_data.get("mcqs", {})
    if isinstance(mcqs_container, dict):
        for diff, mcqs in mcqs_container.items():
            for m in mcqs:
                if m.get("id") == mcq_id:
                    return m, diff
    elif isinstance(mcqs_container, list):
        for m in mcqs_container:
            if m.get("id") == mcq_id:
                return m, m.get("difficulty", "medium")
    return None

# Pydantic Schemas
class InteractionRequest(BaseModel):
    student_id: str = Field(..., example="S001")
    concept: str = Field(..., example="Loops")
    activity_type: str = Field(..., example="MCQ", description="MCQ, Code, or Short Answer")
    student_response: str = Field(..., example="B")
    question_id: Optional[str] = Field(None, example="Loops_MCQ_Medium_1")
    difficulty: Optional[str] = Field("medium", example="medium", description="Question difficulty: easy, medium, or hard")
    reference_answer: Optional[str] = Field(None, example=None)
    response_time_sec: float = Field(15.0, example=15.0)
    passed_test_cases: Optional[int] = Field(0, example=8)
    total_test_cases: Optional[int] = Field(0, example=10)

# Grading Details Schemas
class MCQGradingDetail(BaseModel):
    question_id: str
    question: str
    selected_option: str
    correct_option: str
    is_correct: bool
    evidence_score: float

class ShortAnswerGradingDetail(BaseModel):
    question: str
    student_response: str
    reference_answer: str
    evidence_score: float
    similarity_percentage: float
    missing_keywords: List[str]
    is_acceptable: bool
    feedback: str

class CodingGradingDetail(BaseModel):
    problem: str
    code_string: str
    evidence_score: float
    pass_fraction: float
    passed_test_cases: int
    total_test_cases: int
    is_compilable: bool
    syntax_valid: bool
    syntax_error: Optional[str] = None
    runtime_error: Optional[str] = None
    feedback: str

class BundleGradingDetails(BaseModel):
    mcqs: List[MCQGradingDetail]
    short_answer: ShortAnswerGradingDetail
    coding: CodingGradingDetail

class InteractionResponse(BaseModel):
    student_id: str
    concept: str
    activity_type: str
    evidence_score: float
    is_success: bool
    updated_mastery: float
    updated_uncertainty: float
    feedback: str
    difficulty: Optional[str] = "medium"
    next_recommended_difficulty: Optional[str] = None
    scaffolding_reasoning: Optional[str] = None
    grading_details: Optional[Dict[str, Any]] = None

class BundleAssessmentRequest(BaseModel):
    student_id: str = Field(..., example="S001")
    concept: str = Field(..., example="Variables")
    difficulty: Optional[str] = Field("medium", example="medium", description="Assessment difficulty level: easy, medium, or hard")
    mcq_responses: List[str] = Field(..., example=["B", "B", "C"], description="List of 3 selected MCQ options [MCQ 1, MCQ 2, MCQ 3]")
    short_answer_response: str = Field(..., example="A variable stores data values in computer memory.")
    code_response: str = Field(..., example="def sum_two_numbers(a, b):\n    return a + b\n")
    passed_test_cases: int = Field(8, example=8)
    total_test_cases: int = Field(10, example=10)
    response_time_sec: float = Field(45.0, example=45.0)

class BundleAssessmentResponse(BaseModel):
    student_id: str
    concept: str
    mcq_scores: List[float]
    short_answer_score: float
    code_score: float
    bundle_average_score: float
    updated_mastery: float
    updated_uncertainty: float
    feedbacks: List[str]
    difficulty: Optional[str] = "medium"
    next_recommended_difficulty: Optional[str] = None
    scaffolding_reasoning: Optional[str] = None
    grading_details: Optional[BundleGradingDetails] = None

class RecommendationRequest(BaseModel):
    student_id: str = Field(..., example="S001")
    target_concept_override: Optional[str] = Field(None, example="Variables")
    current_difficulty: Optional[str] = Field(None, example="medium")
    last_evidence_score: Optional[float] = Field(None, example=0.85)

class RecommendationResponse(BaseModel):
    student_id: str
    recommended_concept: str
    priority_score: float
    recommended_activity: str
    activity_code: int
    concept_mastery: float
    concept_uncertainty: float
    recommended_difficulty: str
    scaffolding_reasoning: str
    reasoning: str
    question_details: Dict[str, Any]
    all_concept_priorities: List[Dict[str, Any]]
    difficulty_floor_active: Optional[bool] = False
    cycle_unattempted: Optional[bool] = False
    modality_downgraded: Optional[bool] = False
    prerequisite_fallback_applied: Optional[bool] = False

# Authentication & Student History Schemas
class RegisterRequest(BaseModel):
    username: str = Field(..., example="alice")
    password: str = Field(..., example="secret123")
    full_name: Optional[str] = Field(None, example="Alice Smith")
    email: Optional[str] = Field(None, example="alice@example.com")

class RegisterResponse(BaseModel):
    status: str
    message: str
    student_id: str
    username: str
    full_name: Optional[str] = None
    mastery_state: Optional[Dict[str, Any]] = None

class LoginRequest(BaseModel):
    username: str = Field(..., example="alice")
    password: str = Field(..., example="secret123")

class LoginResponse(BaseModel):
    status: str
    message: str
    student_id: str
    username: str
    full_name: Optional[str] = None
    mastery_state: Optional[Dict[str, Any]] = None

class StudentHistoryResponse(BaseModel):
    student_id: str
    history: List[Dict[str, Any]]

class StudentMasteryResponse(BaseModel):
    student_id: str
    knowledge_state: Dict[str, Any]
    concept_difficulties: Optional[Dict[str, str]] = None

# Endpoints
@app.get("/")
async def read_root():
    """Healthcheck endpoint."""
    mongo_status = "connected (motor)"
    try:
        db = get_motor_db()
        await db.command("ping")
    except Exception:
        mongo_status = "offline / fallback"
    return {
        "system": "Adaptive Knowledge Tracing API",
        "status": "online",
        "version": "2.0.0",
        "mongodb": mongo_status,
        "model": "Behavior-AKT + MC Dropout Uncertainty + Difficulty Scaffolding + SBERT Short Answer Analyzer",
        "total_kcs": len(REFERENCE_ANSWERS),
        "kcs": list(REFERENCE_ANSWERS.keys()),
        "difficulties": ["easy", "medium", "hard"]
    }

# Student Registration & Login Endpoints (MongoDB backed with motor)
@app.post("/register", response_model=RegisterResponse)
@app.post("/api/v1/register", response_model=RegisterResponse)
async def register_student(req: RegisterRequest):
    """
    Registers a new student, hashes password with SHA-256, links credentials to a unique student_id,
    and initializes/tracks individual student mastery states in MongoDB using motor.
    """
    u_name = req.username.strip().lower()
    if len(u_name) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters long.")
    if len(req.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters long.")

    db = get_motor_db()
    try:
        existing = await db["users"].find_one({"username": u_name})
        if existing:
            raise HTTPException(status_code=400, detail=f"Username '{req.username}' is already registered.")
    except HTTPException:
        raise
    except Exception:
        pass

    if u_name in _in_memory_users:
        raise HTTPException(status_code=400, detail=f"Username '{req.username}' is already registered.")

    student_id = await generate_student_id_async(db)
    init_mastery = get_initial_mastery_state()
    init_diffs = get_initial_concept_difficulties()
    now_iso = datetime.now(timezone.utc).isoformat()

    user_doc = {
        "username": u_name,
        "display_username": req.username.strip(),
        "password_hash": hash_password(req.password),
        "student_id": student_id,
        "full_name": req.full_name or req.username.strip(),
        "email": req.email or "",
        "created_at": now_iso,
        "mastery_state": init_mastery,
        "concept_difficulties": init_diffs
    }

    state_doc = {
        "student_id": student_id,
        "username": u_name,
        "knowledge_state": init_mastery,
        "concept_difficulties": init_diffs,
        "updated_at": now_iso
    }

    try:
        await db["users"].insert_one(dict(user_doc))
        await db["student_states"].update_one(
            {"student_id": student_id},
            {"$set": state_doc},
            upsert=True
        )
    except Exception:
        pass

    _in_memory_users[u_name] = user_doc
    _in_memory_student_states[student_id] = state_doc

    stu_tr = KnowledgeStateTracker()
    _student_trackers[student_id] = stu_tr

    return RegisterResponse(
        status="success",
        message="Student registered successfully",
        student_id=student_id,
        username=req.username.strip(),
        full_name=user_doc["full_name"],
        mastery_state=init_mastery
    )

@app.post("/login", response_model=LoginResponse)
@app.post("/api/v1/login", response_model=LoginResponse)
async def login_student(req: LoginRequest):
    """
    Authenticates student credentials against MongoDB using motor and retrieves student mastery states.
    """
    u_name = req.username.strip().lower()
    pw_hash = hash_password(req.password)

    db = get_motor_db()
    user = None
    try:
        user = await db["users"].find_one({"username": u_name})
    except Exception:
        pass

    if not user:
        user = _in_memory_users.get(u_name)

    if not user or user.get("password_hash") != pw_hash:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    student_id = user["student_id"]
    mastery_state = user.get("mastery_state")
    try:
        state_doc = await db["student_states"].find_one({"student_id": student_id})
        if state_doc and "knowledge_state" in state_doc:
            mastery_state = state_doc["knowledge_state"]
    except Exception:
        pass

    if not mastery_state:
        mastery_state = get_initial_mastery_state()

    return LoginResponse(
        status="success",
        message="Login successful",
        student_id=student_id,
        username=user.get("display_username", req.username.strip()),
        full_name=user.get("full_name", req.username.strip()),
        mastery_state=mastery_state
    )

@app.get("/api/v1/student/{student_id}/history", response_model=StudentHistoryResponse)
@app.get("/student/{student_id}/history", response_model=StudentHistoryResponse)
async def get_student_score_history(student_id: str):
    """Fetches historical assessment scores and practice submissions for a student from MongoDB using motor."""
    db = get_motor_db()
    records = []
    try:
        cursor = db["scores"].find({"student_id": student_id}, {"_id": 0}).sort([("timestamp", -1), ("_id", -1)])
        records = await cursor.to_list(length=100)
    except Exception:
        pass

    if not records and student_id in _in_memory_scores:
        records = _in_memory_scores[student_id]

    return StudentHistoryResponse(student_id=student_id, history=records)

@app.post("/api/v1/student/{student_id}/record_score")
@app.post("/student/{student_id}/record_score")
async def record_student_score_endpoint(student_id: str, record: Dict[str, Any]):
    """Records a completed assessment bundle score for a student into MongoDB using motor."""
    await record_student_score_internal_async(
        student_id=student_id,
        concept=record.get("concept", "Variables"),
        difficulty=record.get("difficulty", "medium"),
        bundle_average_score=float(record.get("bundle_average_score", 0.0)),
        mcq_scores=record.get("mcq_scores", []),
        short_answer_score=float(record.get("short_answer_score", 0.0)),
        code_score=float(record.get("code_score", 0.0)),
        next_difficulty=record.get("next_difficulty"),
        scaffolding_reasoning=record.get("scaffolding_reasoning"),
        timestamp=record.get("timestamp")
    )
    return {"status": "success", "message": "Score recorded successfully"}

@app.get("/api/v1/student/{student_id}/mastery", response_model=StudentMasteryResponse)
@app.get("/api/v1/knowledge_state/{student_id}", response_model=StudentMasteryResponse)
async def get_student_knowledge_state(student_id: str):
    """Fetches full knowledge state breakdown and individual mastery state for a student from MongoDB using motor."""
    db = get_motor_db()
    k_state = None
    diffs = student_concept_difficulty.get(student_id, {})
    try:
        doc = await db["student_states"].find_one({"student_id": student_id}, {"_id": 0})
        if doc:
            k_state = doc.get("knowledge_state")
            if "concept_difficulties" in doc:
                diffs = doc["concept_difficulties"]
    except Exception:
        pass

    if not k_state:
        stu_tr = await get_student_tracker(student_id)
        k_state = stu_tr.get_knowledge_state()

    return StudentMasteryResponse(
        student_id=student_id,
        knowledge_state=k_state,
        concept_difficulties=diffs
    )

@app.post("/api/v1/student/{student_id}/mastery")
async def update_student_mastery_endpoint(student_id: str, payload: Dict[str, Any]):
    """Updates individual student mastery state in MongoDB using motor."""
    k_state = payload.get("knowledge_state", {})
    diffs = payload.get("concept_difficulties", {})
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        db = get_motor_db()
        await db["student_states"].update_one(
            {"student_id": student_id},
            {"$set": {"knowledge_state": k_state, "concept_difficulties": diffs, "updated_at": now_iso}},
            upsert=True
        )
        await db["users"].update_one(
            {"student_id": student_id},
            {"$set": {"mastery_state": k_state, "updated_at": now_iso}}
        )
    except Exception:
        pass
    return {"status": "success", "message": "Mastery state updated"}


@app.get("/api/v1/concept_bundle/{concept}")
def get_concept_bundle(concept: str, difficulty: Optional[str] = Query(None)):
    """
    Retrieves the complete assessment bundle for a KC.
    If difficulty ('easy', 'medium', 'hard') is specified, returns the targeted 5-question bundle.
    Otherwise returns the complete nested dictionary across all difficulties.
    """
    kc_data = REFERENCE_ANSWERS.get(concept)
    if not kc_data:
        raise HTTPException(status_code=404, detail=f"Concept '{concept}' not found. Available KCs: {list(REFERENCE_ANSWERS.keys())}")
    
    if difficulty:
        diff = difficulty.lower().strip()
        mcqs = kc_data.get("mcqs", {}).get(diff, []) if isinstance(kc_data.get("mcqs"), dict) else kc_data.get("mcqs", [])
        sa = kc_data.get("short_answer", {}).get(diff, {}) if isinstance(kc_data.get("short_answer"), dict) else kc_data.get("short_answer", {})
        code = kc_data.get("coding", {}).get(diff, {}) if isinstance(kc_data.get("coding"), dict) else kc_data.get("coding", {})
        return {
            "concept": concept,
            "difficulty": diff,
            "bundle": {
                "mcqs": mcqs,
                "short_answer": sa,
                "coding": code
            }
        }

    return {
        "concept": concept,
        "bundle": kc_data
    }

@app.post("/api/v1/update_interaction", response_model=InteractionResponse)
async def update_interaction(req: InteractionRequest):
    """
    Processes single student response submission via modality analyzers (MCQ, Code, Short Answer),
    calculates continuous evidence score [0.0, 1.0], updates student knowledge state,
    and implements difficulty scaffolding (< 0.5 -> easier, > 0.8 -> harder).
    """
    act_type = req.activity_type.strip().lower()
    student_diff = student_concept_difficulty.get(req.student_id, {}).get(req.concept, "medium")
    cur_diff = req.difficulty.lower().strip() if req.difficulty else student_diff

    if act_type in ["mcq", "multiple_choice", "0"]:
        act_code = 0
        target_mcq = None
        if req.question_id:
            found = find_mcq_by_id(req.concept, req.question_id)
            if found:
                target_mcq, cur_diff = found
        
        if not target_mcq:
            target_mcq = get_next_mcq_for_student(req.student_id, req.concept, difficulty=cur_diff)

        correct_opt = target_mcq.get("correct_option", "A")
        if req.reference_answer:
            correct_opt = req.reference_answer.strip()

        analysis = mcq_analyzer.evaluate(
            student_option=req.student_response,
            correct_option=correct_opt
        )
        score = analysis["evidence_score"]
        is_success = analysis["is_correct"]
        feedback = analysis["feedback"]
        mark_mcq_attempted(req.student_id, req.concept, target_mcq["id"], difficulty=cur_diff)
        single_grading = {
            "activity_type": "MCQ",
            "question_id": target_mcq.get("id"),
            "question": target_mcq.get("question"),
            "selected_option": req.student_response,
            "correct_option": correct_opt,
            "is_correct": is_success,
            "evidence_score": float(score)
        }

    elif act_type in ["code", "programming", "1"]:
        act_code = 1
        code_data = get_coding_task_for_concept(req.concept, difficulty=cur_diff)
        analysis = code_analyzer.evaluate(
            code_string=req.student_response,
            passed_test_cases=req.passed_test_cases or 0,
            total_test_cases=req.total_test_cases or 0,
            test_cases=code_data.get("test_cases", [])
        )
        score = analysis["evidence_score"]
        is_success = analysis["is_compilable"] and (score >= 0.70)
        feedback = f"Code compilable: {analysis['is_compilable']}. Test Pass Fraction: {score * 100:.1f}%"
        single_grading = {
            "activity_type": "Code",
            "pass_fraction": float(analysis.get("pass_fraction", score)),
            "passed_test_cases": int(analysis.get("passed_test_cases", req.passed_test_cases or 0)),
            "total_test_cases": int(analysis.get("total_test_cases", req.total_test_cases or 0)),
            "is_compilable": bool(analysis.get("is_compilable", True)),
            "syntax_valid": bool(analysis.get("syntax_valid", True)),
            "syntax_error": analysis.get("syntax_error"),
            "runtime_error": analysis.get("runtime_error"),
            "evidence_score": float(score)
        }

    elif act_type in ["short answer", "short_answer", "text", "2"]:
        act_code = 2
        sa_data = get_short_answer_for_concept(req.concept, difficulty=cur_diff)
        ref_text = req.reference_answer or sa_data.get(
            "reference_answer",
            "A variable is a named container in computer memory used to store data values."
        )

        analysis = short_answer_analyzer.evaluate(
            student_response=req.student_response,
            reference_answer=ref_text
        )
        score = analysis["evidence_score"]
        is_success = analysis.get("is_acceptable", score >= 0.5)
        sim_pct = float(analysis.get("similarity_percentage", round(score * 100, 1)))
        feedback = f"SBERT Cosine Similarity: {sim_pct:.1f}%. {analysis['feedback']}"
        single_grading = {
            "activity_type": "Short Answer",
            "similarity_percentage": sim_pct,
            "missing_keywords": analysis.get("missing_keywords", []),
            "reference_answer": ref_text,
            "evidence_score": float(score),
            "feedback": analysis.get("feedback")
        }

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported activity_type '{req.activity_type}'. Use MCQ, Code, or Short Answer.")

    # Difficulty Scaffolding Policy:
    # If last evidence score < 0.5 -> route to easier question
    # If last evidence score > 0.8 -> route to harder question
    next_diff, diff_reason = selector.scaffold_difficulty(
        last_evidence_score=score,
        current_difficulty=cur_diff
    )

    if req.student_id not in student_concept_difficulty:
        student_concept_difficulty[req.student_id] = {}
    student_concept_difficulty[req.student_id][req.concept] = next_diff

    # Update individual student knowledge state
    stu_tr = await get_student_tracker(req.student_id)
    stu_tr.update_state(
        concept_name_or_id=req.concept,
        evidence_score=score,
        activity_type=act_code,
        response_time_sec=req.response_time_sec,
        difficulty=cur_diff
    )

    updated_state = tracker.update_state(
        concept_name_or_id=req.concept,
        evidence_score=score,
        activity_type=act_code,
        response_time_sec=req.response_time_sec,
        difficulty=cur_diff
    )

    await persist_student_mastery_state(req.student_id, stu_tr, student_concept_difficulty.get(req.student_id))

    return InteractionResponse(
        student_id=req.student_id,
        concept=req.concept,
        activity_type=req.activity_type,
        evidence_score=float(score),
        is_success=bool(is_success),
        updated_mastery=float(updated_state["mastery"]),
        updated_uncertainty=float(updated_state["uncertainty"]),
        feedback=str(feedback),
        difficulty=cur_diff,
        next_recommended_difficulty=next_diff,
        scaffolding_reasoning=diff_reason,
        grading_details=single_grading
    )

@app.post("/api/v1/evaluate_bundle", response_model=BundleAssessmentResponse)
async def evaluate_bundle(req: BundleAssessmentRequest):
    """
    Evaluates a complete 5-question concept assessment bundle at a specified difficulty level:
    - 3 MCQs
    - 1 Conceptual Short Answer (SBERT)
    - 1 Coding Sandbox challenge (with test case validation)
    Updates tracker state and computes scaffolded difficulty for the next assessment round.
    Returns granular grading_details for each question in the bundle.
    """
    diff = req.difficulty.lower().strip() if req.difficulty else "medium"
    kc_data = REFERENCE_ANSWERS.get(req.concept, REFERENCE_ANSWERS.get("Variables", {}))
    
    mcqs_container = kc_data.get("mcqs", {})
    if isinstance(mcqs_container, dict):
        mcqs = mcqs_container.get(diff, mcqs_container.get("medium", []))
    else:
        mcqs = mcqs_container

    sa_data = get_short_answer_for_concept(req.concept, difficulty=diff)
    code_data = get_coding_task_for_concept(req.concept, difficulty=diff)

    mcq_scores = []
    feedbacks = []
    mcq_grading_details = []

    stu_tr = await get_student_tracker(req.student_id)

    # 1. Evaluate 3 MCQs
    for i in range(3):
        student_opt = req.mcq_responses[i] if i < len(req.mcq_responses) else ""
        mcq_obj = mcqs[i] if i < len(mcqs) else {}
        correct_opt = mcq_obj.get("correct_option", "A")
        
        analysis = mcq_analyzer.evaluate(student_option=student_opt, correct_option=correct_opt)
        score = analysis["evidence_score"]
        mcq_scores.append(float(score))
        status_str = "Correct" if analysis["is_correct"] else f"Incorrect (Correct: {correct_opt})"
        feedbacks.append(f"MCQ {i+1} ({diff.title()}): {status_str} (Score: {score:.2f})")
        
        mcq_grading_details.append(MCQGradingDetail(
            question_id=mcq_obj.get("id", f"{req.concept}_MCQ_{i+1}"),
            question=mcq_obj.get("question", f"MCQ {i+1}"),
            selected_option=student_opt,
            correct_option=correct_opt,
            is_correct=bool(analysis["is_correct"]),
            evidence_score=float(score)
        ))

        # Update state trackers per MCQ
        stu_tr.update_state(
            req.concept,
            evidence_score=score,
            activity_type=0,
            response_time_sec=req.response_time_sec / 5.0,
            difficulty=diff
        )
        tracker.update_state(
            req.concept,
            evidence_score=score,
            activity_type=0,
            response_time_sec=req.response_time_sec / 5.0,
            difficulty=diff
        )

    # 2. Evaluate Short Answer (SBERT)
    ref_sa_text = sa_data.get("reference_answer", "Variables store data values in computer memory.")
    sa_analysis = short_answer_analyzer.evaluate(student_response=req.short_answer_response, reference_answer=ref_sa_text)
    sa_score = float(sa_analysis["evidence_score"])
    sim_pct = float(sa_analysis.get("similarity_percentage", round(sa_score * 100, 1)))
    missing_kws = sa_analysis.get("missing_keywords", [])
    feedbacks.append(f"Short Answer ({diff.title()}) SBERT Cosine Similarity: {sim_pct:.1f}%")
    
    sa_grading_detail = ShortAnswerGradingDetail(
        question=sa_data.get("question", "Explain the concept."),
        student_response=req.short_answer_response,
        reference_answer=ref_sa_text,
        evidence_score=sa_score,
        similarity_percentage=sim_pct,
        missing_keywords=missing_kws,
        is_acceptable=bool(sa_analysis.get("is_acceptable", sa_score >= 0.5)),
        feedback=sa_analysis.get("feedback", "")
    )

    stu_tr.update_state(
        req.concept,
        evidence_score=sa_score,
        activity_type=2,
        response_time_sec=req.response_time_sec / 5.0,
        difficulty=diff
    )
    tracker.update_state(
        req.concept,
        evidence_score=sa_score,
        activity_type=2,
        response_time_sec=req.response_time_sec / 5.0,
        difficulty=diff
    )

    # 3. Evaluate Coding Challenge
    code_analysis = code_analyzer.evaluate(
        code_string=req.code_response,
        passed_test_cases=req.passed_test_cases,
        total_test_cases=req.total_test_cases,
        test_cases=code_data.get("test_cases", [])
    )
    code_score = float(code_analysis["evidence_score"])
    pass_frac = float(code_analysis.get("pass_fraction", code_score))
    code_passed = int(code_analysis.get("passed_test_cases", req.passed_test_cases))
    code_total = int(code_analysis.get("total_test_cases", req.total_test_cases))
    feedbacks.append(f"Coding ({diff.title()}) Pass Fraction: {pass_frac * 100:.1f}% ({code_passed}/{code_total} tests)")

    code_grading_detail = CodingGradingDetail(
        problem=code_data.get("problem", "Write Python code."),
        code_string=req.code_response,
        evidence_score=code_score,
        pass_fraction=pass_frac,
        passed_test_cases=code_passed,
        total_test_cases=code_total,
        is_compilable=bool(code_analysis.get("is_compilable", True)),
        syntax_valid=bool(code_analysis.get("syntax_valid", True)),
        syntax_error=code_analysis.get("syntax_error"),
        runtime_error=code_analysis.get("runtime_error"),
        feedback=f"Passed {code_passed}/{code_total} tests ({pass_frac * 100:.1f}%)"
    )

    stu_tr.update_state(
        req.concept,
        evidence_score=code_score,
        activity_type=1,
        response_time_sec=req.response_time_sec / 5.0,
        difficulty=diff
    )
    updated_state = tracker.update_state(
        req.concept,
        evidence_score=code_score,
        activity_type=1,
        response_time_sec=req.response_time_sec / 5.0,
        difficulty=diff
    )

    # 4. Compute overall bundle average
    bundle_avg = float(np.mean(mcq_scores + [sa_score, code_score]))

    # Difficulty Scaffolding based on bundle average performance:
    next_diff, diff_reason = selector.scaffold_difficulty(
        last_evidence_score=bundle_avg,
        current_difficulty=diff
    )
    if req.student_id not in student_concept_difficulty:
        student_concept_difficulty[req.student_id] = {}
    student_concept_difficulty[req.student_id][req.concept] = next_diff

    # Persist student mastery state and bundle score record in MongoDB using motor
    await persist_student_mastery_state(req.student_id, stu_tr, student_concept_difficulty.get(req.student_id))
    await record_student_score_internal_async(
        student_id=req.student_id,
        concept=req.concept,
        difficulty=diff,
        bundle_average_score=bundle_avg,
        mcq_scores=mcq_scores,
        short_answer_score=sa_score,
        code_score=code_score,
        next_difficulty=next_diff,
        scaffolding_reasoning=diff_reason
    )

    return BundleAssessmentResponse(
        student_id=req.student_id,
        concept=req.concept,
        mcq_scores=mcq_scores,
        short_answer_score=sa_score,
        code_score=code_score,
        bundle_average_score=bundle_avg,
        updated_mastery=float(updated_state["mastery"]),
        updated_uncertainty=float(updated_state["uncertainty"]),
        feedbacks=feedbacks,
        difficulty=diff,
        next_recommended_difficulty=next_diff,
        scaffolding_reasoning=diff_reason,
        grading_details=BundleGradingDetails(
            mcqs=mcq_grading_details,
            short_answer=sa_grading_detail,
            coding=code_grading_detail
        )
    )

@app.post("/api/v1/recommend", response_model=RecommendationResponse)
async def get_recommendation(req: RecommendationRequest):
    """
    Computes priority scores (1.0 - mastery) * (1.0 + uncertainty), routes optimal activity modality,
    implements difficulty scaffolding (< 0.5 -> easier, > 0.8 -> harder), and returns question details.
    """
    stu_tr = await get_student_tracker(req.student_id)
    state_dict = stu_tr.get_knowledge_state()
    cur_diff = req.current_difficulty
    if not cur_diff:
        cur_diff = student_concept_difficulty.get(req.student_id, {}).get(
            req.target_concept_override or "Variables",
            "medium"
        )

    try:
        rec = selector.recommend_next_activity(
            knowledge_state_dict=state_dict,
            target_concept_override=req.target_concept_override,
            current_difficulty=cur_diff,
            last_evidence_score=req.last_evidence_score
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation engine error: {str(e)}")

    concept = rec["recommended_concept"]
    act_code = rec["activity_code"]
    rec_diff = rec["recommended_difficulty"]

    if act_code == 0:
        q_details = get_next_mcq_for_student(req.student_id, concept, difficulty=rec_diff)
    elif act_code == 2:
        q_details = get_short_answer_for_concept(concept, difficulty=rec_diff)
    else:
        q_details = get_coding_task_for_concept(concept, difficulty=rec_diff)

    return RecommendationResponse(
        student_id=req.student_id,
        recommended_concept=rec["recommended_concept"],
        priority_score=rec["priority_score"],
        recommended_activity=rec["recommended_activity"],
        activity_code=rec["activity_code"],
        concept_mastery=rec["concept_mastery"],
        concept_uncertainty=rec["concept_uncertainty"],
        recommended_difficulty=rec_diff,
        scaffolding_reasoning=rec["scaffolding_reasoning"],
        reasoning=rec["reasoning"],
        question_details=q_details,
        all_concept_priorities=rec["all_concept_priorities"],
        difficulty_floor_active=rec.get("difficulty_floor_active", False),
        cycle_unattempted=rec.get("cycle_unattempted", False),
        modality_downgraded=rec.get("modality_downgraded", False),
        prerequisite_fallback_applied=rec.get("prerequisite_fallback_applied", False)
    )
    cur_diff = req.current_difficulty
    if not cur_diff:
        cur_diff = student_concept_difficulty.get(req.student_id, {}).get(
            req.target_concept_override or "Variables",
            "medium"
        )

    try:
        rec = selector.recommend_next_activity(
            knowledge_state_dict=state_dict,
            target_concept_override=req.target_concept_override,
            current_difficulty=cur_diff,
            last_evidence_score=req.last_evidence_score
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation engine error: {str(e)}")

    concept = rec["recommended_concept"]
    act_code = rec["activity_code"]
    rec_diff = rec["recommended_difficulty"]

    if act_code == 0:
        q_details = get_next_mcq_for_student(req.student_id, concept, difficulty=rec_diff)
    elif act_code == 2:
        q_details = get_short_answer_for_concept(concept, difficulty=rec_diff)
    else:
        q_details = get_coding_task_for_concept(concept, difficulty=rec_diff)

    return RecommendationResponse(
        student_id=req.student_id,
        recommended_concept=rec["recommended_concept"],
        priority_score=rec["priority_score"],
        recommended_activity=rec["recommended_activity"],
        activity_code=rec["activity_code"],
        concept_mastery=rec["concept_mastery"],
        concept_uncertainty=rec["concept_uncertainty"],
        recommended_difficulty=rec_diff,
        scaffolding_reasoning=rec["scaffolding_reasoning"],
        reasoning=rec["reasoning"],
        question_details=q_details,
        all_concept_priorities=rec["all_concept_priorities"],
        difficulty_floor_active=rec.get("difficulty_floor_active", False),
        cycle_unattempted=rec.get("cycle_unattempted", False),
        modality_downgraded=rec.get("modality_downgraded", False),
        prerequisite_fallback_applied=rec.get("prerequisite_fallback_applied", False)
    )


