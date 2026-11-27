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
import re
import copy
import json
import hashlib
import uuid
import math
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import secrets
import logging
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError, InvalidHash
from fastapi import FastAPI, HTTPException, Query, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, ConnectionFailure, ServerSelectionTimeoutError
from motor.motor_asyncio import AsyncIOMotorClient
try:
    import certifi
except ImportError:
    certifi = None

from src.analyzers import MCQAnalyzer, CodeAnalyzer, ShortAnswerAnalyzer
from src.analyzers.sandbox_runner import (
    SecureDockerPythonEvaluator,
    default_sandbox_evaluator,
    MAX_CODE_LENGTH
)
from src.engine import KnowledgeStateTracker, AdaptiveActivitySelector
from src.models import BehaviorAKT
from src.evidence_adapters import build_embedded_bundle_evidence

# 1. Transient in-memory queue for holding code prior to privacy masking
evaluation_queue: asyncio.Queue = asyncio.Queue()


async def coding_evaluation_worker():
    """
    Background worker that consumes transient coding tasks from evaluation_queue,
    invokes SecureDockerPythonEvaluator strictly in ephemeral containers,
    and atomically reconciles evaluation results into db["scores"].
    """
    evaluator = SecureDockerPythonEvaluator()
    logger.info("Coding evaluation background worker started.")
    try:
        while True:
            item = await evaluation_queue.get()
            try:
                submission_id = item.get("submission_id")
                code_string = item.get("code_string", "")
                test_cases = item.get("test_cases", [])

                # 1. Run evaluation inside ephemeral Docker container (fails closed if offline)
                eval_result = evaluator.evaluate(
                    code_string=code_string,
                    test_cases=test_cases
                )

                # 2. Determine canonical lifecycle, admission status, and score metrics
                now_iso = datetime.now(timezone.utc).isoformat()
                is_infra_fail = (
                    eval_result.code_status == "EVALUATION_FAILED_INFRASTRUCTURE"
                    or eval_result.code_execution_status == "INFRASTRUCTURE_UNAVAILABLE"
                    or "infrastructure" in (eval_result.feedback or "").lower()
                )

                if is_infra_fail:
                    lifecycle = "EVALUATION_FAILED_INFRASTRUCTURE"
                    admission = "REJECTED_INFRASTRUCTURE_FAILURE"
                    raw_score = None
                    max_score = None
                    norm_score = None
                    correctness = None
                    tests_run = 0
                    tests_passed = None
                    tests_failed = None
                    tests_not_run = eval_result.code_tests_total
                elif not eval_result.syntax_valid and eval_result.syntax_error:
                    lifecycle = "EVALUATION_ERROR_STUDENT_CODE"
                    admission = "PENDING_RESEARCH_POLICY"
                    raw_score = 0.0
                    max_score = float(eval_result.code_tests_total)
                    norm_score = 0.0
                    correctness = False
                    tests_run = 0
                    tests_passed = 0
                    tests_failed = 0
                    tests_not_run = eval_result.code_tests_total
                elif eval_result.runtime_error and "timed out" in str(eval_result.runtime_error).lower():
                    lifecycle = "EVALUATION_TIMEOUT_STUDENT_CODE"
                    admission = "PENDING_RESEARCH_POLICY"
                    raw_score = 0.0
                    max_score = float(eval_result.code_tests_total)
                    norm_score = 0.0
                    correctness = False
                    tests_run = eval_result.code_tests_passed
                    tests_passed = eval_result.code_tests_passed
                    tests_failed = 0
                    tests_not_run = eval_result.code_tests_total - eval_result.code_tests_passed
                else:
                    lifecycle = "EVALUATED_SUCCESS"
                    admission = "PENDING_RESEARCH_POLICY"
                    raw_score = float(eval_result.code_tests_passed)
                    max_score = float(eval_result.code_tests_total)
                    norm_score = (
                        float(eval_result.code_tests_passed / eval_result.code_tests_total)
                        if eval_result.code_tests_total > 0
                        else 0.0
                    )
                    correctness = bool(
                        eval_result.code_tests_passed == eval_result.code_tests_total
                        and eval_result.code_tests_total > 0
                    )
                    tests_run = eval_result.code_tests_total
                    tests_passed = eval_result.code_tests_passed
                    tests_failed = eval_result.code_tests_total - eval_result.code_tests_passed
                    tests_not_run = 0

                # 3. Construct atomic reconciliation update with arrayFilters
                update_doc = {
                    "$set": {
                        "code_status": eval_result.code_status,
                        "code_execution_status": eval_result.code_execution_status,
                        "code_score": float(norm_score or 0.0),
                        "code_tests_passed": eval_result.code_tests_passed,
                        "code_tests_total": eval_result.code_tests_total,
                        "code_reconciled_at": now_iso,
                        "evidence_records.$[elem].evaluation_lifecycle": lifecycle,
                        "evidence_records.$[elem].admission_status": admission,
                        "evidence_records.$[elem].raw_score": raw_score,
                        "evidence_records.$[elem].maximum_possible_score": max_score,
                        "evidence_records.$[elem].normalized_score": norm_score,
                        "evidence_records.$[elem].correctness": correctness,
                        "evidence_records.$[elem].evaluation_completion_timestamp": now_iso,
                        "evidence_records.$[elem].modality_details.coding.tests_run": tests_run,
                        "evidence_records.$[elem].modality_details.coding.tests_passed": tests_passed,
                        "evidence_records.$[elem].modality_details.coding.tests_failed": tests_failed,
                        "evidence_records.$[elem].modality_details.coding.tests_not_run": tests_not_run,
                        "evidence_records.$[elem].modality_details.coding.total_test_cases": eval_result.code_tests_total,
                        "evidence_records.$[elem].modality_details.coding.infrastructure_error_message": (
                            eval_result.feedback if is_infra_fail else None
                        ),
                    }
                }

                # 4. Atomic MongoDB update with idempotency guard
                db = get_motor_db()
                for _ in range(5):
                    res = await db["scores"].update_one(
                        {"submission_id": submission_id, "code_status": "PENDING_SECURE_EVALUATION"},
                        update_doc,
                        array_filters=[{"elem.modality": "CODING"}]
                    )
                    if res.matched_count > 0:
                        logger.info("Successfully reconciled coding evaluation for %s", submission_id)
                        break
                    # Wait briefly if primary insert is in-flight
                    await asyncio.sleep(0.05)
            except Exception as e:
                logger.error("Error evaluating item for submission_id=%s: %s", item.get("submission_id"), e, exc_info=True)
            finally:
                evaluation_queue.task_done()
    except asyncio.CancelledError:
        logger.info("Coding evaluation background worker shut down gracefully.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application startup and background worker lifecycle."""
    worker_task = asyncio.create_task(coding_evaluation_worker())
    yield
    # Graceful shutdown: cancel background worker
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Adaptive Knowledge Tracing API",
    description="Multi-Response Student Behaviour Modeling & Uncertainty-Guided Adaptive Learning Engine API with Difficulty Scaffolding",
    version="2.0.0",
    lifespan=lifespan
)

# CORS Configuration for Vercel, localhost, and custom frontend domains
ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "")
_custom_origins = [orig.strip() for orig in ALLOWED_ORIGINS_RAW.split(",") if orig.strip()]
_default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
_allowed_origins = list(set(_default_origins + _custom_origins))
_allowed_origin_regex = os.getenv("ALLOWED_ORIGIN_REGEX", r"^https:\/\/.*\.vercel\.app$")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=_allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        timeout_ms = int(os.getenv("MONGO_TIMEOUT_MS", "10000"))
        
        client_kwargs: Dict[str, Any] = {
            "serverSelectionTimeoutMS": timeout_ms,
            "connectTimeoutMS": timeout_ms,
        }
        
        # Configure TLS/SSL and root certificates for MongoDB Atlas / SRV URIs
        is_atlas_or_tls = (
            MONGO_URI.startswith("mongodb+srv://")
            or "ssl=true" in MONGO_URI.lower()
            or "tls=true" in MONGO_URI.lower()
        )
        if is_atlas_or_tls and certifi is not None:
            client_kwargs["tlsCAFile"] = certifi.where()
            
        _motor_client = AsyncIOMotorClient(MONGO_URI, **client_kwargs)
    return _motor_client

def get_motor_db():
    """Returns asynchronous Motor database handle."""
    return get_motor_client()[MONGO_DB_NAME]

def get_mongo_db():
    """Returns synchronous MongoDB database handle for fallback or synchronous utilities."""
    try:
        timeout_ms = int(os.getenv("MONGO_TIMEOUT_MS", "10000"))
        client_kwargs: Dict[str, Any] = {
            "serverSelectionTimeoutMS": timeout_ms,
            "connectTimeoutMS": timeout_ms,
        }
        is_atlas_or_tls = (
            MONGO_URI.startswith("mongodb+srv://")
            or "ssl=true" in MONGO_URI.lower()
            or "tls=true" in MONGO_URI.lower()
        )
        if is_atlas_or_tls and certifi is not None:
            client_kwargs["tlsCAFile"] = certifi.where()
        client = MongoClient(MONGO_URI, **client_kwargs)
        client.admin.command('ping')
        return client[MONGO_DB_NAME]
    except Exception:
        return None

logger = logging.getLogger("akt_api")

# Argon2id Password Hasher (time_cost=3, memory_cost=64MB, parallelism=4)
_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    type=Type.ID
)

def hash_password(password: str) -> str:
    """Computes Argon2id hash for secure student credential storage."""
    return _password_hasher.hash(password)

_in_memory_users: Dict[str, Dict[str, Any]] = {}
_in_memory_scores: Dict[str, List[Dict[str, Any]]] = {}
_in_memory_student_states: Dict[str, Dict[str, Any]] = {}

DEFAULT_KCS = [
    "Variables", "Conditionals", "Loops", "Functions", "Arrays", "Syntax", "OOP",
    "Dictionaries", "File Handling", "Exception Handling"
]

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
_student_async_locks: Dict[str, asyncio.Lock] = {}

def get_student_lock(student_id: str) -> asyncio.Lock:
    """Returns an asyncio.Lock for serializing in-process updates for an individual student."""
    if student_id not in _student_async_locks:
        _student_async_locks[student_id] = asyncio.Lock()
    return _student_async_locks[student_id]

def is_valid_mcq_observation(score: Any) -> bool:
    """
    Strictly validates individual binary MCQ observations (0.0 or 1.0).
    Rejects non-binary values, boolean types, NaNs, infinities, and invalid types.
    """
    if isinstance(score, bool):
        return False
    if not isinstance(score, (int, float)):
        return False
    try:
        val = float(score)
        if math.isnan(val) or math.isinf(val):
            return False
        return val in (0.0, 1.0)
    except (TypeError, ValueError):
        return False

async def get_student_tracker(student_id: str, reload_from_db: bool = False) -> KnowledgeStateTracker:
    """
    Retrieves or creates a KnowledgeStateTracker for an individual student, restoring state from MongoDB if available,
    or falling back to in-memory state tracking when MongoDB is unreachable.
    """
    if reload_from_db or student_id not in _student_trackers:
        stu_tracker = KnowledgeStateTracker()
        state_doc = None
        db = get_motor_db()
        try:
            state_doc = await db["student_states"].find_one({"student_id": student_id})
        except Exception as exc:
            logger.warning("MongoDB unavailable loading state for student %s: %s; falling back to in-memory state", student_id, exc)
            state_doc = _in_memory_student_states.get(student_id)

        if state_doc and "knowledge_state" in state_doc:
            for c_name, c_data in state_doc["knowledge_state"].items():
                stu_tracker.set_concept_state(
                    c_name,
                    mastery=float(c_data.get("mastery", 0.30)),
                    uncertainty=float(c_data.get("uncertainty", 0.50)),
                    history=c_data.get("history", []),
                    attempts=int(c_data.get("attempts", len(c_data.get("history", [])))),
                    last_submission_id=c_data.get("last_submission_id"),
                    processed_submissions=c_data.get("processed_submissions", []),
                    consecutive_easy_failures=c_data.get("consecutive_easy_failures", 0)
                )
        _student_trackers[student_id] = stu_tracker
    return _student_trackers[student_id]

async def persist_student_mastery_state(
    student_id: str,
    tracker_instance: KnowledgeStateTracker,
    concept_diff: Optional[Dict[str, str]] = None,
    expected_version: Optional[int] = None
) -> int:
    """
    Persists individual student mastery state to MongoDB using motor with optimistic version checking.
    Does not silently swallow database persistence failures.
    Returns the new state version.
    """
    state_dict = tracker_instance.get_knowledge_state()
    now_iso = datetime.now(timezone.utc).isoformat()
    update_payload = {
        "student_id": student_id,
        "knowledge_state": state_dict,
        "updated_at": now_iso
    }
    if concept_diff:
        update_payload["concept_difficulties"] = concept_diff

    db = get_motor_db()
    try:
        existing_doc = await db["student_states"].find_one({"student_id": student_id})
        if existing_doc is None:
            if expected_version not in (None, 0):
                logger.warning(
                    "Optimistic lock conflict on student_states for %s: expected version %s, but document does not exist",
                    student_id, expected_version
                )
                raise HTTPException(
                    status_code=409,
                    detail=f"Optimistic lock conflict persisting state for student {student_id}."
                )
            initial_doc = {**update_payload, "version": 1}
            try:
                await db["student_states"].insert_one(initial_doc)
            except DuplicateKeyError:
                logger.warning(
                    "Concurrent initial insert conflict (DuplicateKeyError) on student_states for %s",
                    student_id
                )
                raise HTTPException(
                    status_code=409,
                    detail=f"Optimistic lock conflict persisting initial state for student {student_id}."
                )
            new_version = 1
        else:
            raw_ver = existing_doc.get("version")
            has_int_version = isinstance(raw_ver, int) and not isinstance(raw_ver, bool)
            if has_int_version:
                target_expected = expected_version if expected_version is not None else raw_ver
                res = await db["student_states"].update_one(
                    {"student_id": student_id, "version": target_expected},
                    {"$set": update_payload, "$inc": {"version": 1}}
                )
                if res.matched_count == 0:
                    logger.warning(
                        "Optimistic lock conflict on student_states for %s: expected version %s, current DB version %s",
                        student_id, target_expected, raw_ver
                    )
                    raise HTTPException(
                        status_code=409,
                        detail=f"Optimistic lock conflict persisting state for student {student_id}."
                    )
                new_version = target_expected + 1
            else:
                if expected_version not in (None, 0):
                    logger.warning(
                        "Optimistic lock conflict on student_states for %s: expected version %s, current DB version %r",
                        student_id, expected_version, raw_ver
                    )
                    raise HTTPException(
                        status_code=409,
                        detail=f"Optimistic lock conflict persisting state for student {student_id}."
                    )
                unversioned_payload = {**update_payload, "version": 1}
                res = await db["student_states"].update_one(
                    {
                        "student_id": student_id,
                        "$or": [{"version": {"$exists": False}}, {"version": None}]
                    },
                    {"$set": unversioned_payload}
                )
                if res.matched_count == 0:
                    logger.warning(
                        "Optimistic lock conflict on unversioned student_states for %s",
                        student_id
                    )
                    raise HTTPException(
                        status_code=409,
                        detail=f"Optimistic lock conflict persisting state for student {student_id}."
                    )
                new_version = 1

        # Synchronize users collection (student_states remains canonical authority)
        try:
            await db["users"].update_one(
                {"student_id": student_id},
                {"$set": {"mastery_state": state_dict, "updated_at": now_iso}}
            )
        except Exception as user_exc:
            logger.warning("Secondary update to users.mastery_state failed for %s: %s", student_id, user_exc)

    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("MongoDB unavailable persisting student mastery state for %s: %s; preserved in-memory", student_id, exc)
        new_version = (expected_version or 0) + 1

    _in_memory_student_states[student_id] = {**update_payload, "version": new_version}
    return new_version

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

def normalize_code_status(value: Any) -> Optional[str]:
    """Normalizes coding evaluation status strings to uppercase snake_case without altering DB records."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return re.sub(r"[\s-]+", "_", text.upper())


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
    timestamp: Optional[str] = None,
    submission_id: Optional[str] = None,
    code_status: Optional[str] = None,
    code_execution_status: Optional[str] = None,
    code_tests_passed: Optional[int] = None,
    code_tests_total: Optional[int] = None,
    syntax_preview_passed: Optional[bool] = None,
    syntax_preview_count: Optional[int] = None,
    evidence_records: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Persists a student's assessment bundle score into MongoDB using motor.
    Implements an idempotent score ledger and deterministically reconciles pending
    MCQ observations with the KnowledgeStateTracker using continuous EMA updates (alpha=0.20, activity_type=0).
    """
    async with get_student_lock(student_id):
        db = get_motor_db()
        now_iso = timestamp or datetime.now(timezone.utc).isoformat()

        # 1. Validate / generate submission_id
        if submission_id is not None:
            if not isinstance(submission_id, str) or not submission_id.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Invalid submission_id: must be a non-empty string."
                )
            sub_id = submission_id.strip()
        else:
            sub_id = f"sub_legacy_{uuid.uuid4().hex}"

        # 2. Check for duplicate or existing submission_id
        existing_score = None
        try:
            existing_score = await db["scores"].find_one({"submission_id": sub_id})
        except Exception as exc:
            logger.warning("MongoDB unavailable checking submission_id %s: %s; checking in-memory", sub_id, exc)
            existing_score = next((s for s in _in_memory_scores.get(student_id, []) if s.get("submission_id") == sub_id), None)

        if existing_score:
            if existing_score.get("bkt_processed") is True:
                # Idempotent replay: already fully processed
                replayed_tracker = await get_student_tracker(student_id, reload_from_db=True)
                concept_res = replayed_tracker.state.get(concept, {})
                return {
                    "status": "success",
                    "message": "Score already recorded and processed (idempotent replay).",
                    "submission_id": sub_id,
                    "bkt_processed": True,
                    "replayed": True,
                    "concept": concept,
                    "mastery": concept_res.get("mastery", 0.30),
                    "uncertainty": concept_res.get("uncertainty", 0.50),
                    "attempts": concept_res.get("attempts", 0)
                }
            score_entry = existing_score
        else:
            # Fresh submission: create score ledger entry with bkt_processed: False
            if evidence_records is not None:
                embedded_evidence = [
                    r.model_dump() if hasattr(r, "model_dump") else dict(r)
                    for r in evidence_records
                ]
            else:
                try:
                    embedded_evidence = build_embedded_bundle_evidence(
                        student_id=student_id,
                        submission_id=sub_id,
                        concept=concept,
                        difficulty=difficulty,
                        mcq_scores=mcq_scores,
                        short_answer_score=short_answer_score,
                        code_score=code_score,
                        code_status=code_status,
                        code_execution_status=code_execution_status,
                        code_tests_passed=code_tests_passed,
                        code_tests_total=code_tests_total,
                        server_receipt_timestamp=now_iso,
                        client_submission_timestamp=timestamp,
                    )
                except (ValueError, TypeError) as val_err:
                    raise HTTPException(status_code=400, detail=f"Invalid score payload: {val_err}") from val_err

            score_entry = {
                "submission_id": sub_id,
                "student_id": student_id,
                "concept": concept,
                "difficulty": difficulty,
                "bundle_average_score": float(bundle_average_score),
                "mcq_scores": [float(s) for s in mcq_scores if isinstance(s, (int, float))],
                "short_answer_score": float(short_answer_score),
                "code_score": float(code_score),
                "next_difficulty": next_difficulty or difficulty,
                "scaffolding_reasoning": scaffolding_reasoning or "",
                "timestamp": now_iso,
                "bkt_processed": False,
                "bkt_processed_at": None,
                "bkt_observations_applied": 0,
                "evidence_records": embedded_evidence
            }
            norm_code_status = normalize_code_status(code_status)
            norm_exec_status = normalize_code_status(code_execution_status)
            if norm_code_status is not None:
                score_entry["code_status"] = norm_code_status
            if norm_exec_status is not None:
                score_entry["code_execution_status"] = norm_exec_status
            if code_tests_passed is not None:
                score_entry["code_tests_passed"] = int(code_tests_passed)
            if code_tests_total is not None:
                score_entry["code_tests_total"] = int(code_tests_total)
            if syntax_preview_passed is not None:
                score_entry["syntax_preview_passed"] = bool(syntax_preview_passed)
            if syntax_preview_count is not None:
                score_entry["syntax_preview_count"] = int(syntax_preview_count)
            inserted_fresh = False
            try:
                await db["scores"].insert_one(dict(score_entry))
                inserted_fresh = True
            except DuplicateKeyError:
                raced_score = await db["scores"].find_one({"submission_id": sub_id})
                if raced_score and raced_score.get("bkt_processed") is True:
                    replayed_tracker = await get_student_tracker(student_id, reload_from_db=True)
                    concept_res = replayed_tracker.state.get(concept, {})
                    return {
                        "status": "success",
                        "message": "Score already recorded and processed (idempotent replay).",
                        "submission_id": sub_id,
                        "bkt_processed": True,
                        "replayed": True,
                        "concept": concept,
                        "mastery": concept_res.get("mastery", 0.30),
                        "uncertainty": concept_res.get("uncertainty", 0.50),
                        "attempts": concept_res.get("attempts", 0)
                    }
                score_entry = raced_score or score_entry
            except Exception as exc:
                logger.warning("MongoDB unavailable writing score ledger for %s: %s; cached in-memory", sub_id, exc)
                inserted_fresh = True

            if inserted_fresh:
                if student_id not in _in_memory_scores:
                    _in_memory_scores[student_id] = []
                _in_memory_scores[student_id].insert(0, score_entry)

        # 3. Reconcile pending submissions for this student in deterministic chronological order
        pending_scores = []
        try:
            pending_cursor = db["scores"].find({
                "student_id": student_id,
                "bkt_processed": False,
                "submission_id": {"$exists": True}
            }).sort("timestamp", 1)
            pending_scores = await pending_cursor.to_list(length=100)
        except Exception as exc:
            logger.warning("MongoDB unavailable reading pending scores for %s: %s; using in-memory pending scores", student_id, exc)
            pending_scores = [s for s in _in_memory_scores.get(student_id, []) if not s.get("bkt_processed")]

        # 4. Load fresh tracker state from database and stage updates in a copy
        persisted_tracker = await get_student_tracker(student_id, reload_from_db=True)
        staged_tracker = copy.deepcopy(persisted_tracker)
        state_doc = None
        try:
            state_doc = await db["student_states"].find_one({"student_id": student_id})
        except Exception:
            state_doc = _in_memory_student_states.get(student_id)
        raw_state_ver = state_doc.get("version") if state_doc else None
        current_version = (
            raw_state_ver
            if isinstance(raw_state_ver, int) and not isinstance(raw_state_ver, bool)
            else 0
        )

        # 5. Process pending scores sequentially on the staged tracker
        for pending in pending_scores:
            p_sub_id = pending["submission_id"]
            p_concept = pending.get("concept", concept)
            p_diff = pending.get("difficulty", "medium")
            p_mcqs = pending.get("mcq_scores", [])

            # Concept-level state token check: has this submission already updated state?
            concept_state = staged_tracker.state.get(p_concept, {})
            processed_subs = concept_state.get("processed_submissions", [])
            history = concept_state.get("history", [])

            already_applied = (
                p_sub_id in processed_subs or
                any(h.get("submission_id") == p_sub_id for h in history)
            )

            applied_count = 0
            if not already_applied:
                evidence_records = pending.get("evidence_records")
                if evidence_records and isinstance(evidence_records, list):
                    for rec in evidence_records:
                        norm_score = rec.get("normalized_score")
                        modality = rec.get("modality", "MCQ")
                        lifecycle = rec.get("evaluation_lifecycle")
                        if norm_score is not None and lifecycle in ("EVALUATED_SUCCESS", "EVALUATED"):
                            staged_tracker.update_state(
                                concept_name_or_id=p_concept,
                                evidence_score=float(norm_score),
                                modality=modality,
                                difficulty=p_diff
                            )
                            c_curr = staged_tracker.state[p_concept]
                            if c_curr.get("history"):
                                c_curr["history"][-1]["submission_id"] = p_sub_id
                            applied_count += 1
                else:
                    for score_val in p_mcqs:
                        if is_valid_mcq_observation(score_val):
                            staged_tracker.update_state(
                                concept_name_or_id=p_concept,
                                evidence_score=float(score_val),
                                modality="MCQ",
                                difficulty=p_diff
                            )
                            c_curr = staged_tracker.state[p_concept]
                            if c_curr.get("history"):
                                c_curr["history"][-1]["submission_id"] = p_sub_id
                            applied_count += 1

                # Update concept-level state tokens
                c_curr = staged_tracker.state[p_concept]
                c_curr["last_submission_id"] = p_sub_id
                if "processed_submissions" not in c_curr:
                    c_curr["processed_submissions"] = []
                if p_sub_id not in c_curr["processed_submissions"]:
                    c_curr["processed_submissions"].append(p_sub_id)

                # Persist updated tracker to MongoDB with optimistic versioning
                try:
                    current_version = await persist_student_mastery_state(
                        student_id=student_id,
                        tracker_instance=staged_tracker,
                        expected_version=current_version
                    )
                except Exception:
                    _student_trackers.pop(student_id, None)
                    try:
                        await get_student_tracker(student_id, reload_from_db=True)
                    except Exception:
                        pass
                    raise

                # Commit staged tracker to in-memory cache only after persistence succeeds
                _student_trackers[student_id] = copy.deepcopy(staged_tracker)

            # Mark score record as bkt_processed: True in MongoDB ledger
            if isinstance(pending, dict) and "_id" in pending:
                try:
                    await db["scores"].update_one(
                        {"_id": pending["_id"]},
                        {"$set": {
                            "bkt_processed": True,
                            "bkt_processed_at": datetime.now(timezone.utc).isoformat(),
                            "bkt_observations_applied": applied_count
                        }}
                    )
                except Exception:
                    pass
            pending["bkt_processed"] = True

        _student_trackers[student_id] = staged_tracker
        concept_res = staged_tracker.state.get(concept, {})
        return {
            "status": "success",
            "message": "Score recorded successfully",
            "submission_id": sub_id,
            "bkt_processed": True,
            "concept": concept,
            "mastery": concept_res.get("mastery", 0.30),
            "uncertainty": concept_res.get("uncertainty", 0.50),
            "attempts": concept_res.get("attempts", 0)
        }

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
def _resolve_sbert_model_path() -> str:
    env_path = os.getenv("SBERT_MODEL_PATH", "").strip()
    if env_path and (os.path.isdir(env_path) or os.path.exists(env_path)):
        return env_path
    if os.path.isdir("models/sbert_programming_minilm"):
        return "models/sbert_programming_minilm"
    return env_path or "sentence-transformers/all-MiniLM-L6-v2"

short_answer_analyzer = ShortAnswerAnalyzer(model_name=_resolve_sbert_model_path())

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
    evidence_records: Optional[List[Dict[str, Any]]] = None

class AnalyzeShortAnswerRequest(BaseModel):
    concept: str = Field(..., example="Variables", description="Knowledge component or concept name")
    difficulty: Optional[str] = Field("medium", example="medium", description="Difficulty level: easy, medium, or hard")
    student_response: str = Field(..., max_length=5000, example="A variable is a named storage location in memory.", description="Student's short answer response")

class AnalyzeShortAnswerResponse(BaseModel):
    evidence_score: float
    similarity_percentage: float
    is_acceptable: bool
    missing_keywords: List[str]
    feedback: str
    model_used: str
    fallback_active: bool

class EvaluateCodeRequest(BaseModel):
    concept: str = Field(..., example="Variables", description="Knowledge component or concept name")
    difficulty: Optional[str] = Field("medium", example="medium", description="Difficulty level: easy, medium, or hard")
    code_string: str = Field(..., max_length=MAX_CODE_LENGTH, description="Student submitted Python source code")

class EvaluateCodeTestResult(BaseModel):
    testIndex: int
    call: str
    description: str
    passed: bool
    error: Optional[str] = None
    actualRepr: Optional[str] = None

class EvaluateCodeResponse(BaseModel):
    code_status: str
    code_execution_status: str
    code_score: float
    code_tests_passed: int
    code_tests_total: int
    syntax_valid: bool
    syntax_error: Optional[str] = None
    runtime_error: Optional[str] = None
    test_results: List[EvaluateCodeTestResult] = Field(default_factory=list)
    feedback: str

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

# ==============================================================================
# Internal Service Authentication & Identity Verification Dependencies
# ==============================================================================

def get_internal_service_secret() -> str:
    """
    Retrieves and validates the configured internal service secret.
    Enforces fail-closed behavior: secret must be configured and at least 32 characters.
    Missing or insufficiently strong server configuration raises HTTP 500, never allowing access.
    """
    secret = os.getenv("INTERNAL_SERVICE_SECRET")
    if not secret or len(secret.strip()) < 32:
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: INTERNAL_SERVICE_SECRET is not configured or insufficiently strong (minimum 32 characters required)."
        )
    return secret.strip()

async def verify_service_secret(
    x_internal_service_secret: Optional[str] = Header(None, alias="X-Internal-Service-Secret"),
    expected_secret: str = Depends(get_internal_service_secret)
) -> None:
    """
    Reusable FastAPI dependency validating X-Internal-Service-Secret header using constant-time comparison.
    Rejects missing or invalid service secrets with HTTP 403 Forbidden.
    """
    if not x_internal_service_secret or not secrets.compare_digest(x_internal_service_secret, expected_secret):
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Invalid or missing internal service secret."
        )

async def get_authenticated_student_id(
    _service_verified: None = Depends(verify_service_secret),
    x_authenticated_student_id: Optional[str] = Header(None, alias="X-Authenticated-Student-Id")
) -> str:
    """
    Reusable FastAPI dependency extracting and validating X-Authenticated-Student-Id header.
    Pre-conditioned on verify_service_secret to guarantee the service secret is validated
    before trusting the identity header.
    Rejects missing or blank student identity with HTTP 401 Unauthorized.
    """
    if not x_authenticated_student_id or not x_authenticated_student_id.strip():
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Missing authenticated student identity header."
        )
    return x_authenticated_student_id.strip()

def verify_student_authorization(target_student_id: str, authenticated_student_id: str) -> None:
    """
    Helper function verifying that the target resource student_id strictly matches
    the independently authenticated student identity from the header.
    Rejects mismatches with HTTP 403 Forbidden without revealing student IDs in the error message.
    """
    if target_student_id != authenticated_student_id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Student identity mismatch."
        )

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
async def register_student(
    req: RegisterRequest,
    _auth: None = Depends(verify_service_secret)
):
    """
    Registers a new student, hashes password with Argon2id, links credentials to a unique student_id,
    and initializes/tracks individual student mastery states in MongoDB using motor.
    """
    u_name = req.username.strip().lower()
    if len(u_name) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters long.")
    if len(req.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters long.")

    db = get_motor_db()
    existing = None
    db_available = True
    try:
        existing = await db["users"].find_one({"username": u_name})
    except (ConnectionFailure, ServerSelectionTimeoutError) as conn_err:
        logger.warning("MongoDB connection failure during user lookup: %s", conn_err)
        db_available = False
    except Exception as exc:
        logger.warning("Database error during user registration lookup: %s", exc)
        db_available = False

    if existing:
        raise HTTPException(status_code=400, detail=f"Username '{req.username}' is already registered.")

    if not db_available and u_name in _in_memory_users:
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
        "version": 1,
        "updated_at": now_iso
    }

    persisted_to_db = False
    try:
        await db["users"].insert_one(dict(user_doc))
        await db["student_states"].update_one(
            {"student_id": student_id},
            {"$set": state_doc},
            upsert=True
        )
        persisted_to_db = True
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail=f"Username '{req.username}' is already registered.")
    except Exception as exc:
        logger.warning("Failed to persist user to MongoDB: %s; saving in-memory", exc)

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
async def login_student(
    req: LoginRequest,
    _auth: None = Depends(verify_service_secret)
):
    """
    Authenticates student credentials against MongoDB using motor and retrieves student mastery states.
    Supports Argon2id with transparent migration for legacy SHA-256 credentials.
    """
    u_name = req.username.strip().lower()

    db = get_motor_db()
    user = None
    db_error = False
    try:
        user = await db["users"].find_one({"username": u_name})
    except (ConnectionFailure, ServerSelectionTimeoutError) as conn_err:
        logger.warning("MongoDB connection failure during login lookup: %s", conn_err)
        db_error = True
    except Exception as exc:
        logger.warning("Database error during login user query: %s", exc)
        db_error = True

    if not user:
        user = _in_memory_users.get(u_name)

    if not user:
        if db_error and not _in_memory_users:
            raise HTTPException(
                status_code=503,
                detail="Database service currently unavailable. Please verify MongoDB connection."
            )
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    stored_hash = user.get("password_hash")
    if not stored_hash or not isinstance(stored_hash, str):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    authenticated = False
    needs_rehash = False

    if stored_hash.startswith("$argon2"):
        try:
            _password_hasher.verify(stored_hash, req.password)
            authenticated = True
            needs_rehash = _password_hasher.check_needs_rehash(stored_hash)
        except (VerificationError, InvalidHash):
            authenticated = False
        except Exception:
            authenticated = False
    elif len(stored_hash) == 64 and all(c in "0123456789abcdefABCDEF" for c in stored_hash):
        legacy_hash = hashlib.sha256(req.password.encode("utf-8")).hexdigest()
        if secrets.compare_digest(stored_hash.lower(), legacy_hash):
            authenticated = True
            needs_rehash = True
        else:
            authenticated = False
    else:
        authenticated = False

    if not authenticated:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    if needs_rehash:
        try:
            new_hash = hash_password(req.password)
            if u_name in _in_memory_users:
                _in_memory_users[u_name]["password_hash"] = new_hash
            if isinstance(user, dict):
                user["password_hash"] = new_hash
            await db["users"].update_one(
                {"username": u_name},
                {"$set": {"password_hash": new_hash}}
            )
        except Exception:
            logger.warning("Failed to persist updated password hash during migration.")

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
async def get_student_score_history(
    student_id: str,
    auth_student_id: str = Depends(get_authenticated_student_id)
):
    """Fetches historical assessment scores and practice submissions for a student from MongoDB using motor."""
    verify_student_authorization(target_student_id=student_id, authenticated_student_id=auth_student_id)
    db = get_motor_db()
    records = []
    try:
        cursor = db["scores"].find({"student_id": student_id}, {"_id": 0}).sort([("timestamp", -1), ("_id", -1)])
        records = await cursor.to_list(length=100)
    except Exception:
        pass

    if not records and student_id in _in_memory_scores:
        records = _in_memory_scores[student_id]

    # Normalize status values and legacy camelCase coding keys on read without rewriting historical MongoDB records
    normalized_records = []
    for r in records:
        item = dict(r)
        raw_status = item.get("code_status") if item.get("code_status") is not None else item.get("codeStatus")
        raw_exec_status = (
            item.get("code_execution_status")
            if item.get("code_execution_status") is not None
            else item.get("codeExecutionStatus")
        )
        norm_status = normalize_code_status(raw_status)
        norm_exec_status = normalize_code_status(raw_exec_status)
        if norm_status is not None:
            item["code_status"] = norm_status
        if norm_exec_status is not None:
            item["code_execution_status"] = norm_exec_status
        if "code_tests_passed" not in item and item.get("codeTestsPassed") is not None:
            item["code_tests_passed"] = int(item["codeTestsPassed"])
        if "code_tests_total" not in item and item.get("codeTestsTotal") is not None:
            item["code_tests_total"] = int(item["codeTestsTotal"])
        normalized_records.append(item)

    return StudentHistoryResponse(student_id=student_id, history=normalized_records)

@app.post("/api/v1/student/{student_id}/record_score")
@app.post("/student/{student_id}/record_score")
@app.post("/api/v1/record_score")
@app.post("/record_score")
async def record_student_score_endpoint(
    record: Dict[str, Any],
    student_id: Optional[str] = None,
    auth_student_id: str = Depends(get_authenticated_student_id)
):
    """Records a completed assessment bundle score for a student into MongoDB using motor."""
    effective_student_id = student_id or record.get("student_id") or auth_student_id
    verify_student_authorization(target_student_id=effective_student_id, authenticated_student_id=auth_student_id)
    if "student_id" in record:
        verify_student_authorization(target_student_id=str(record["student_id"]), authenticated_student_id=auth_student_id)

    code_status = record.get("code_status") or record.get("codeStatus")
    code_execution_status = record.get("code_execution_status") or record.get("codeExecutionStatus")
    code_tests_passed = record.get("code_tests_passed") if record.get("code_tests_passed") is not None else record.get("codeTestsPassed")
    code_tests_total = record.get("code_tests_total") if record.get("code_tests_total") is not None else record.get("codeTestsTotal")
    syntax_preview_passed = record.get("syntax_preview_passed") if record.get("syntax_preview_passed") is not None else record.get("syntaxPreviewPassed")
    syntax_preview_count = record.get("syntax_preview_count") if record.get("syntax_preview_count") is not None else record.get("syntaxPreviewCount")

    res = await record_student_score_internal_async(
        student_id=effective_student_id,
        concept=record.get("concept", "Variables"),
        difficulty=record.get("difficulty", "medium"),
        bundle_average_score=float(record.get("bundle_average_score", 0.0)),
        mcq_scores=record.get("mcq_scores", []),
        short_answer_score=float(record.get("short_answer_score", 0.0)),
        code_score=float(record.get("code_score", 0.0)),
        next_difficulty=record.get("next_difficulty"),
        scaffolding_reasoning=record.get("scaffolding_reasoning"),
        timestamp=record.get("timestamp"),
        submission_id=record.get("submission_id"),
        code_status=code_status,
        code_execution_status=code_execution_status,
        code_tests_passed=code_tests_passed,
        code_tests_total=code_tests_total,
        syntax_preview_passed=syntax_preview_passed,
        syntax_preview_count=syntax_preview_count,
        evidence_records=record.get("evidence_records")
    )
    return res

@app.get("/api/v1/student/{student_id}/mastery", response_model=StudentMasteryResponse)
@app.get("/api/v1/knowledge_state/{student_id}", response_model=StudentMasteryResponse)
async def get_student_knowledge_state(
    student_id: str,
    auth_student_id: str = Depends(get_authenticated_student_id)
):
    """Fetches full knowledge state breakdown and individual mastery state for a student from MongoDB using motor."""
    verify_student_authorization(target_student_id=student_id, authenticated_student_id=auth_student_id)
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
async def update_student_mastery_endpoint(
    student_id: str,
    payload: Dict[str, Any],
    auth_student_id: str = Depends(get_authenticated_student_id)
):
    """Updates individual student mastery state in MongoDB using motor."""
    verify_student_authorization(target_student_id=student_id, authenticated_student_id=auth_student_id)
    k_state = payload.get("knowledge_state", {})
    diffs = payload.get("concept_difficulties", {})
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        db = get_motor_db()
        await db["student_states"].update_one(
            {"student_id": student_id},
            {
                "$set": {"knowledge_state": k_state, "concept_difficulties": diffs, "updated_at": now_iso},
                "$setOnInsert": {"version": 1}
            },
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
def get_concept_bundle(
    concept: str,
    difficulty: Optional[str] = Query(None),
    _auth: None = Depends(verify_service_secret)
):
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
async def update_interaction(
    req: InteractionRequest,
    auth_student_id: str = Depends(get_authenticated_student_id)
):
    """
    Processes single student response submission via modality analyzers (MCQ, Code, Short Answer),
    calculates continuous evidence score [0.0, 1.0], updates student knowledge state,
    and implements difficulty scaffolding (< 0.5 -> easier, > 0.8 -> harder).
    """
    verify_student_authorization(target_student_id=req.student_id, authenticated_student_id=auth_student_id)
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
        analysis = code_analyzer.evaluate(code_string=req.student_response)
        score = 0.0
        is_success = False
        feedback = "Host code execution is permanently disabled. Tests not executed."
        single_grading = {
            "activity_type": "Code",
            "pass_fraction": 0.0,
            "passed_test_cases": 0,
            "total_test_cases": 0,
            "is_compilable": bool(analysis.get("is_compilable", False)),
            "syntax_valid": bool(analysis.get("syntax_valid", False)),
            "syntax_error": analysis.get("syntax_error"),
            "runtime_error": "Host code execution is permanently disabled.",
            "evidence_score": 0.0
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

    if act_code == 1:
        # Code execution permanently disabled: maintain difficulty and do NOT update EMA tracker
        next_diff = cur_diff
        diff_reason = "Code execution is permanently disabled; difficulty maintained."
        stu_tr = await get_student_tracker(req.student_id)
        concept_state = stu_tr.state.get(req.concept, {"mastery": 0.30, "uncertainty": 0.50})
        updated_state = {
            "mastery": float(concept_state.get("mastery", 0.30)),
            "uncertainty": float(concept_state.get("uncertainty", 0.50))
        }
    else:
        # Difficulty Scaffolding Policy:
        # If last evidence score < 0.5 -> route to easier question
        # If last evidence score > 0.8 -> route to harder question
        next_diff, diff_reason = selector.scaffold_difficulty(
            last_evidence_score=score,
            current_difficulty=cur_diff
        )

        async with get_student_lock(req.student_id):
            db = get_motor_db()
            persisted_tracker = await get_student_tracker(req.student_id, reload_from_db=True)
            state_doc = await db["student_states"].find_one({"student_id": req.student_id})
            raw_ver = state_doc.get("version") if state_doc else None
            expected_ver = raw_ver if (isinstance(raw_ver, int) and not isinstance(raw_ver, bool)) else 0

            staged_tracker = copy.deepcopy(persisted_tracker)
            staged_diffs = dict(student_concept_difficulty.get(req.student_id, {}))
            staged_diffs[req.concept] = next_diff

            updated_state = staged_tracker.update_state(
                concept_name_or_id=req.concept,
                evidence_score=score,
                activity_type=act_code,
                response_time_sec=req.response_time_sec,
                difficulty=cur_diff
            )

            try:
                await persist_student_mastery_state(
                    req.student_id,
                    staged_tracker,
                    staged_diffs,
                    expected_version=expected_ver
                )
            except Exception:
                _student_trackers.pop(req.student_id, None)
                try:
                    await get_student_tracker(req.student_id, reload_from_db=True)
                except Exception:
                    pass
                raise

            _student_trackers[req.student_id] = staged_tracker
            student_concept_difficulty[req.student_id] = staged_diffs
            tracker.update_state(
                concept_name_or_id=req.concept,
                evidence_score=score,
                activity_type=act_code,
                response_time_sec=req.response_time_sec,
                difficulty=cur_diff
            )

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

@app.post("/api/v1/analyze_short_answer", response_model=AnalyzeShortAnswerResponse)
async def analyze_short_answer(
    req: AnalyzeShortAnswerRequest,
    _service_verified: None = Depends(verify_service_secret)
):
    """
    Stateless endpoint for semantic short-answer evaluation via ShortAnswerAnalyzer (SBERT).
    Reuses server-side reference-answer rubrics; accepts only concept, difficulty, and student_response.
    Never updates EMA tracker, knowledge states, or database collections.
    """
    concept = (req.concept or "").strip()
    if not concept:
        raise HTTPException(status_code=400, detail="Missing required concept parameter.")

    diff = (req.difficulty or "medium").lower().strip()
    if diff not in ("easy", "medium", "hard"):
        diff = "medium"

    student_text = (req.student_response or "").strip()
    if len(student_text) > 5000:
        raise HTTPException(status_code=400, detail="Student response exceeds maximum allowable length of 5000 characters.")

    # Server-side reference rubric loading (never client-provided)
    sa_data = get_short_answer_for_concept(concept, difficulty=diff)
    ref_text = sa_data.get("reference_answer", "")

    # Evaluate using existing initialized ShortAnswerAnalyzer singleton
    sa_analysis = short_answer_analyzer.evaluate(
        student_response=student_text,
        reference_answer=ref_text
    )

    ev_score = float(sa_analysis.get("evidence_score", 0.0))
    sim_pct = float(sa_analysis.get("similarity_percentage", round(ev_score * 100.0, 1)))
    model_used = str(sa_analysis.get("model_used", "none"))
    fallback_active = "lexical_fallback" in model_used.lower() or model_used == "none"

    if fallback_active and "lexical" in model_used.lower():
        feedback = f"Lexical Token Overlap Score: {sim_pct:.1f}% (Lexical fallback active - Transformer offline)"
    elif not student_text:
        feedback = "Empty student response."
    else:
        feedback = f"SBERT Semantic Similarity Score: {sim_pct:.1f}%"

    return AnalyzeShortAnswerResponse(
        evidence_score=ev_score,
        similarity_percentage=sim_pct,
        is_acceptable=bool(sa_analysis.get("is_acceptable", ev_score >= 0.3)),
        missing_keywords=list(sa_analysis.get("missing_keywords", [])),
        feedback=feedback,
        model_used=model_used,
        fallback_active=fallback_active
    )

@app.post("/api/v1/evaluate_code", response_model=EvaluateCodeResponse)
async def evaluate_code(
    req: EvaluateCodeRequest,
    _service_verified: None = Depends(verify_service_secret)
):
    """
    Stateless endpoint for isolated Docker Python code evaluation.
    Loads authoritative test cases server-side from data/reference_answers.json;
    never executes untrusted code inside the FastAPI host process.
    """
    raw_concept = (req.concept or "").strip()
    if not raw_concept:
        raise HTTPException(status_code=400, detail="Missing required concept parameter.")

    canonical_concept = next(
        (k for k in REFERENCE_ANSWERS.keys() if k.lower() == raw_concept.lower()),
        None
    )
    if not canonical_concept:
        raise HTTPException(status_code=400, detail=f"Invalid concept: {raw_concept}")

    diff = (req.difficulty or "medium").lower().strip()
    if diff not in ("easy", "medium", "hard"):
        raise HTTPException(status_code=400, detail=f"Invalid difficulty: {req.difficulty}")

    code_string = req.code_string or ""
    if len(code_string) > MAX_CODE_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Submitted code exceeds maximum allowable length of {MAX_CODE_LENGTH} characters."
        )

    code_data = get_coding_task_for_concept(canonical_concept, difficulty=diff)
    test_cases = list(code_data.get("test_cases", []) or [])

    try:
        sandbox_res = await asyncio.wait_for(
            asyncio.to_thread(
                default_sandbox_evaluator.evaluate,
                code_string,
                test_cases,
                5.0,
            ),
            timeout=8.0,
        )
    except asyncio.TimeoutError:
        return EvaluateCodeResponse(
            code_status="EVALUATED",
            code_execution_status="EXECUTED",
            code_score=0.0,
            code_tests_passed=0,
            code_tests_total=len(test_cases),
            syntax_valid=True,
            syntax_error=None,
            runtime_error="Sandbox evaluation exceeded maximum request duration.",
            test_results=[],
            feedback="Sandbox evaluation timed out.",
        )

    return EvaluateCodeResponse(**sandbox_res.to_dict())

@app.post("/api/v1/evaluate_bundle", response_model=BundleAssessmentResponse)
async def evaluate_bundle(
    req: BundleAssessmentRequest,
    auth_student_id: str = Depends(get_authenticated_student_id)
):
    """
    Evaluates a complete 5-question concept assessment bundle at a specified difficulty level:
    - 3 MCQs
    - 1 Conceptual Short Answer (SBERT)
    - 1 Coding Sandbox challenge (with test case validation)
    Updates tracker state and computes scaffolded difficulty for the next assessment round.
    Returns granular grading_details for each question in the bundle.
    """
    verify_student_authorization(target_student_id=req.student_id, authenticated_student_id=auth_student_id)
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

    # 1. Evaluate 3 MCQs (without mutating cached trackers prior to persistence)
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

    # Short-Answer scores are admitted into EMA tracker under Modality-Weighted Alpha policy.

    # 3. Evaluate Coding Challenge (Host execution permanently quarantined)
    code_analysis = code_analyzer.evaluate(code_string=req.code_response)
    code_score = 0.0
    pass_frac = 0.0
    code_passed = 0
    code_total = 0
    feedbacks.append("Coding: Host code execution is permanently disabled. Tests not executed.")

    code_grading_detail = CodingGradingDetail(
        problem=code_data.get("problem", "Write Python code."),
        code_string=req.code_response,
        evidence_score=0.0,
        pass_fraction=0.0,
        passed_test_cases=0,
        total_test_cases=0,
        is_compilable=bool(code_analysis.get("is_compilable", False)),
        syntax_valid=bool(code_analysis.get("syntax_valid", False)),
        syntax_error=code_analysis.get("syntax_error"),
        runtime_error="Host code execution is permanently disabled.",
        feedback="Host code execution is permanently disabled. Tests not executed."
    )

    # 4. Compute overall bundle average
    # Aligns with safe composite policy: 60% MCQ + 40% Short Answer; quarantined Code excluded
    mcq_fraction = float(np.mean(mcq_scores)) if mcq_scores else 0.0
    bundle_avg = float((mcq_fraction * 0.6) + (sa_score * 0.4))

    # Difficulty Scaffolding based on bundle average performance:
    next_diff, diff_reason = selector.scaffold_difficulty(
        last_evidence_score=bundle_avg,
        current_difficulty=diff
    )

    # Stage tracker and difficulty mutations in a copy, persist first, then commit caches
    bundle_sub_id = f"sub_{req.student_id}_{uuid.uuid4().hex}"
    async with get_student_lock(req.student_id):
        db = get_motor_db()
        persisted_tracker = await get_student_tracker(req.student_id, reload_from_db=True)
        state_doc = await db["student_states"].find_one({"student_id": req.student_id})
        raw_ver = state_doc.get("version") if state_doc else None
        expected_ver = raw_ver if (isinstance(raw_ver, int) and not isinstance(raw_ver, bool)) else 0

        staged_tracker = copy.deepcopy(persisted_tracker)
        staged_diffs = dict(student_concept_difficulty.get(req.student_id, {}))
        staged_diffs[req.concept] = next_diff

        for score in mcq_scores:
            staged_tracker.update_state(
                req.concept,
                evidence_score=score,
                modality="MCQ",
                response_time_sec=req.response_time_sec / 5.0,
                difficulty=diff
            )
            c_curr = staged_tracker.state[req.concept]
            if c_curr.get("history"):
                c_curr["history"][-1]["submission_id"] = bundle_sub_id

        # Admit Short Answer into staged tracker under Modality-Weighted Alpha
        staged_tracker.update_state(
            req.concept,
            evidence_score=sa_score,
            modality="SHORT_ANSWER",
            response_time_sec=req.response_time_sec / 5.0,
            difficulty=diff
        )
        c_curr = staged_tracker.state[req.concept]
        if c_curr.get("history"):
            c_curr["history"][-1]["submission_id"] = bundle_sub_id

        c_curr = staged_tracker.state[req.concept]
        c_curr["last_submission_id"] = bundle_sub_id
        if "processed_submissions" not in c_curr:
            c_curr["processed_submissions"] = []
        if bundle_sub_id not in c_curr["processed_submissions"]:
            c_curr["processed_submissions"].append(bundle_sub_id)

        try:
            await persist_student_mastery_state(
                req.student_id,
                staged_tracker,
                staged_diffs,
                expected_version=expected_ver
            )
        except Exception:
            _student_trackers.pop(req.student_id, None)
            try:
                await get_student_tracker(req.student_id, reload_from_db=True)
            except Exception:
                pass
            raise

        _student_trackers[req.student_id] = staged_tracker
        student_concept_difficulty[req.student_id] = staged_diffs
        for score in mcq_scores:
            tracker.update_state(
                req.concept,
                evidence_score=score,
                modality="MCQ",
                response_time_sec=req.response_time_sec / 5.0,
                difficulty=diff
            )
        tracker.update_state(
            req.concept,
            evidence_score=sa_score,
            modality="SHORT_ANSWER",
            response_time_sec=req.response_time_sec / 5.0,
            difficulty=diff
        )

    stu_tr = staged_tracker
    test_cases_count = len(code_data.get("test_cases", [])) or 2
    code_syntax_valid = bool(code_analysis.get("syntax_valid", False))

    mcq_details_list = [
        {
            "question_id": d.question_id,
            "selected_option": d.selected_option,
            "correct_option": d.correct_option,
            "is_correct": d.is_correct,
            "evidence_score": d.evidence_score,
            "feedback": f"Selected: {d.selected_option}"
        }
        for d in mcq_grading_details
    ]
    coding_eval_output = {
        "code_status": "PENDING_SECURE_EVALUATION",
        "code_execution_status": "NOT_PERFORMED",
        "code_score": 0.0,
        "code_tests_passed": 0,
        "code_tests_total": test_cases_count,
        "syntax_valid": code_syntax_valid,
        "runtime_error": "Host code execution is permanently disabled.",
        "feedback": "Host code execution is permanently disabled. Tests not executed."
    }

    # Hand off raw code and test cases to transient evaluation queue before privacy masking
    raw_code = getattr(req, "code_response", getattr(req, "code_submission", ""))
    evaluation_queue.put_nowait({
        "submission_id": bundle_sub_id,
        "code_string": raw_code,
        "test_cases": code_data.get("test_cases", []),
        "student_id": req.student_id,
        "concept": req.concept,
        "difficulty": diff,
    })

    embedded_evidence = build_embedded_bundle_evidence(
        student_id=req.student_id,
        submission_id=bundle_sub_id,
        concept=req.concept,
        difficulty=diff,
        mcq_scores=mcq_scores,
        short_answer_score=sa_score,
        code_score=code_score,
        code_status="PENDING_SECURE_EVALUATION",
        code_execution_status="NOT_PERFORMED",
        code_tests_passed=0,
        code_tests_total=test_cases_count,
        mcq_details_list=mcq_details_list,
        sa_evaluator_output=sa_analysis,
        coding_evaluator_output=coding_eval_output
    )

    await record_student_score_internal_async(
        student_id=req.student_id,
        concept=req.concept,
        difficulty=diff,
        bundle_average_score=bundle_avg,
        mcq_scores=mcq_scores,
        short_answer_score=sa_score,
        code_score=code_score,
        next_difficulty=next_diff,
        scaffolding_reasoning=diff_reason,
        submission_id=bundle_sub_id,
        code_status="PENDING_SECURE_EVALUATION",
        code_execution_status="NOT_PERFORMED",
        code_tests_passed=0,
        code_tests_total=test_cases_count,
        syntax_preview_passed=code_syntax_valid,
        syntax_preview_count=test_cases_count if code_syntax_valid else 0,
        evidence_records=embedded_evidence
    )

    concept_state = stu_tr.state.get(req.concept, {"mastery": 0.30, "uncertainty": 0.50})

    return BundleAssessmentResponse(
        student_id=req.student_id,
        concept=req.concept,
        mcq_scores=mcq_scores,
        short_answer_score=sa_score,
        code_score=code_score,
        bundle_average_score=bundle_avg,
        updated_mastery=float(concept_state.get("mastery", 0.30)),
        updated_uncertainty=float(concept_state.get("uncertainty", 0.50)),
        feedbacks=feedbacks,
        difficulty=diff,
        next_recommended_difficulty=next_diff,
        scaffolding_reasoning=diff_reason,
        grading_details=BundleGradingDetails(
            mcqs=mcq_grading_details,
            short_answer=sa_grading_detail,
            coding=code_grading_detail
        ),
        evidence_records=embedded_evidence
    )

@app.post("/api/v1/recommend", response_model=RecommendationResponse)
async def get_recommendation(
    req: RecommendationRequest,
    auth_student_id: str = Depends(get_authenticated_student_id)
):
    """
    Computes priority scores (1.0 - mastery) * (1.0 + uncertainty), routes optimal activity modality,
    implements difficulty scaffolding (< 0.5 -> easier, > 0.8 -> harder), and returns question details.
    """
    verify_student_authorization(target_student_id=req.student_id, authenticated_student_id=auth_student_id)
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


