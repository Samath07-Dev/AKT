"""
app.py

Streamlit Application: Personalized Student Dashboard & Interactive Activity Arena for Intelligent Knowledge Tracing.
Features:
- Student Registration & Login flow backed by MongoDB and FastAPI backend
- Personalized Student Dashboard with welcome header, interactive concept grid/selector, historical score table,
  and personalized mastery/uncertainty radar charts
- Direct routing to Interactive Activity Arena via 'Start Practice' button
- Complete 5-Question Concept Assessment Bundle across 3 Difficulty Levels (Easy, Medium, Hard)
- Form-batched submission logic with multi-modality analyzers (MCQ, SBERT Short Answer, Python Code Challenge)
- Optimized for ultra-fast frontend performance using st.session_state caching and @st.cache_data / @st.cache_resource
"""

import os
import json
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any, Optional
import numpy as np
import pandas as pd
import torch
import requests
from pymongo import MongoClient
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from src.analyzers import MCQAnalyzer, CodeAnalyzer, ShortAnswerAnalyzer
from src.engine import KnowledgeStateTracker, AdaptiveActivitySelector
from src.models import BehaviorAKT

# Page Configuration
st.set_page_config(
    page_title="Adaptive Knowledge Tracing | Student Dashboard & Arena",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Glassmorphism Aesthetic Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #6366F1, #06B6D4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.0rem;
        color: #94A3B8;
        margin-bottom: 1.5rem;
    }
    .card {
        background-color: #1E293B;
        padding: 1.1rem;
        border-radius: 12px;
        border: 1px solid #334155;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        text-align: center;
    }
    .concept-tile {
        background: #1E293B;
        padding: 1.0rem;
        border-radius: 10px;
        border: 1px solid #334155;
        text-align: center;
        margin-bottom: 0.8rem;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .concept-tile:hover {
        border-color: #38BDF8;
        transform: translateY(-2px);
    }
    .rec-card {
        background: linear-gradient(135deg, #1E1B4B, #0F172A);
        padding: 1.3rem;
        border-radius: 12px;
        border: 1px solid #6366F1;
        margin-bottom: 1.5rem;
    }
    .auth-container {
        max-width: 520px;
        margin: 2.0rem auto;
        background: #1E293B;
        padding: 2.2rem;
        border-radius: 16px;
        border: 1px solid #475569;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #38BDF8;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .status-badge {
        background-color: #10B981;
        color: white;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .diff-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        margin-left: 6px;
    }
    .diff-easy { background-color: rgba(16, 185, 129, 0.2); color: #34D399; border: 1px solid #10B981; }
    .diff-medium { background-color: rgba(245, 158, 11, 0.2); color: #FBBF24; border: 1px solid #F59E0B; }
    .diff-hard { background-color: rgba(239, 68, 68, 0.2); color: #F87171; border: 1px solid #EF4444; }
</style>
""", unsafe_allow_html=True)

# Configuration: Backend API & MongoDB
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "akt_tutor")
REF_ANSWERS_PATH = os.path.join("data", "reference_answers.json")

# In-memory stores for fallback if MongoDB or API is temporarily offline
_app_in_memory_users: Dict[str, Dict[str, Any]] = {}
_app_in_memory_scores: Dict[str, List[Dict[str, Any]]] = {}

# -------------------------------------------------------------------
# MONGODB & API AUTHENTICATION HELPERS
# -------------------------------------------------------------------
def get_mongodb_connection():
    """Returns MongoDB database handle or None if connection fails."""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=1500)
        client.admin.command('ping')
        return client[MONGO_DB_NAME]
    except Exception:
        return None

def api_or_db_register(username: str, password: str, full_name: str = "", email: str = "") -> Tuple[bool, str, Dict[str, Any]]:
    """Registers a student via FastAPI endpoint or directly via MongoDB with SHA-256."""
    u_clean = username.strip()
    p_clean = password.strip()
    if len(u_clean) < 3:
        return False, "Username must be at least 3 characters.", {}
    if len(p_clean) < 4:
        return False, "Password must be at least 4 characters.", {}

    # 1. Try FastAPI endpoint
    try:
        url = f"{API_BASE_URL.rstrip('/')}/register"
        resp = requests.post(url, json={
            "username": u_clean,
            "password": p_clean,
            "full_name": full_name or u_clean,
            "email": email or ""
        }, timeout=0.8)
        if resp.status_code == 200:
            data = resp.json()
            return True, "Registration successful!", {
                "student_id": data.get("student_id", f"STU_{uuid.uuid4().hex[:6].upper()}"),
                "username": data.get("username", u_clean),
                "full_name": data.get("full_name", full_name or u_clean)
            }
        elif resp.status_code == 400:
            return False, resp.json().get("detail", "Username already exists."), {}
    except Exception:
        pass

    # 2. Direct MongoDB fallback
    db = get_mongodb_connection()
    u_lower = u_clean.lower()
    pw_hash = hashlib.sha256(p_clean.encode("utf-8")).hexdigest()

    if db is not None:
        try:
            if db["users"].find_one({"username": u_lower}):
                return False, f"Username '{u_clean}' is already registered.", {}
            count = db["users"].count_documents({}) + 1
            student_id = f"S{count:03d}"
            init_mastery = {
                kc: {"mastery": 0.30, "uncertainty": 0.50, "history": []}
                for kc in ["Variables", "Conditionals", "Loops", "Functions", "Arrays", "Syntax", "OOP", "Dictionaries", "File Handling", "Exception Handling"]
            }
            init_diffs = {kc: "medium" for kc in init_mastery.keys()}
            user_doc = {
                "username": u_lower,
                "display_username": u_clean,
                "password_hash": pw_hash,
                "student_id": student_id,
                "full_name": full_name or u_clean,
                "email": email or "",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "mastery_state": init_mastery,
                "concept_difficulties": init_diffs
            }
            db["users"].insert_one(user_doc)
            db["student_states"].update_one(
                {"student_id": student_id},
                {"$set": {
                    "student_id": student_id,
                    "username": u_lower,
                    "knowledge_state": init_mastery,
                    "concept_difficulties": init_diffs,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }},
                upsert=True
            )
            return True, "Registration successful!", {
                "student_id": student_id,
                "username": u_clean,
                "full_name": full_name or u_clean,
                "mastery_state": init_mastery
            }
        except Exception as e:
            pass

    # 3. In-memory fallback
    if u_lower in _app_in_memory_users:
        return False, f"Username '{u_clean}' is already registered.", {}
    student_id = f"S{len(_app_in_memory_users) + 1:03d}"
    init_mastery = {
        kc: {"mastery": 0.30, "uncertainty": 0.50, "history": []}
        for kc in ["Variables", "Conditionals", "Loops", "Functions", "Arrays", "Syntax", "OOP", "Dictionaries", "File Handling", "Exception Handling"]
    }
    user_doc = {
        "username": u_lower,
        "display_username": u_clean,
        "password_hash": pw_hash,
        "student_id": student_id,
        "full_name": full_name or u_clean,
        "email": email or "",
        "mastery_state": init_mastery
    }
    _app_in_memory_users[u_lower] = user_doc
    return True, "Registration successful!", {
        "student_id": student_id,
        "username": u_clean,
        "full_name": full_name or u_clean,
        "mastery_state": init_mastery
    }

def api_or_db_login(username: str, password: str) -> Tuple[bool, str, Dict[str, Any]]:
    """Authenticates a student via FastAPI endpoint or directly via MongoDB."""
    u_clean = username.strip()
    p_clean = password.strip()
    if not u_clean or not p_clean:
        return False, "Please enter both username and password.", {}

    # 1. Try FastAPI endpoint
    try:
        url = f"{API_BASE_URL.rstrip('/')}/login"
        resp = requests.post(url, json={"username": u_clean, "password": p_clean}, timeout=0.8)
        if resp.status_code == 200:
            data = resp.json()
            return True, "Login successful!", {
                "student_id": data.get("student_id", "S001"),
                "username": data.get("username", u_clean),
                "full_name": data.get("full_name", u_clean)
            }
        elif resp.status_code == 401:
            return False, "Invalid username or password.", {}
    except Exception:
        pass

    # 2. Direct MongoDB fallback
    db = get_mongodb_connection()
    u_lower = u_clean.lower()
    pw_hash = hashlib.sha256(p_clean.encode("utf-8")).hexdigest()

    if db is not None:
        try:
            user = db["users"].find_one({"username": u_lower})
            if user and user.get("password_hash") == pw_hash:
                return True, "Login successful!", {
                    "student_id": user.get("student_id", "S001"),
                    "username": user.get("display_username", u_clean),
                    "full_name": user.get("full_name", u_clean)
                }
            elif user:
                return False, "Invalid username or password.", {}
        except Exception:
            pass

    # 3. In-memory fallback
    user = _app_in_memory_users.get(u_lower)
    if user and user.get("password_hash") == pw_hash:
        return True, "Login successful!", {
            "student_id": user.get("student_id", "S001"),
            "username": user.get("display_username", u_clean),
            "full_name": user.get("full_name", u_clean)
        }

    return False, "Invalid username or password.", {}

def api_or_db_get_student_history(student_id: str) -> List[Dict[str, Any]]:
    """Retrieves score history for a student from FastAPI or MongoDB."""
    # 1. Try FastAPI endpoint
    try:
        url = f"{API_BASE_URL.rstrip('/')}/api/v1/student/{student_id}/history"
        resp = requests.get(url, timeout=0.8)
        if resp.status_code == 200:
            return resp.json().get("history", [])
    except Exception:
        pass

    # 2. Direct MongoDB fallback
    db = get_mongodb_connection()
    if db is not None:
        try:
            records = list(db["scores"].find({"student_id": student_id}, {"_id": 0}).sort([("timestamp", -1), ("_id", -1)]))
            if records:
                return records
        except Exception:
            pass

    # 3. In-memory fallback
    return _app_in_memory_scores.get(student_id, [])

def api_or_db_record_score(
    student_id: str,
    concept: str,
    difficulty: str,
    bundle_average_score: float,
    mcq_scores: List[float],
    short_answer_score: float,
    code_score: float,
    next_difficulty: str,
    scaffolding_reasoning: str
):
    """Persists a completed bundle score record to FastAPI and MongoDB."""
    rec = {
        "student_id": student_id,
        "concept": concept,
        "difficulty": difficulty,
        "bundle_average_score": float(bundle_average_score),
        "mcq_scores": [float(s) for s in mcq_scores],
        "short_answer_score": float(short_answer_score),
        "code_score": float(code_score),
        "next_difficulty": next_difficulty,
        "scaffolding_reasoning": scaffolding_reasoning,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    # 1. Try FastAPI endpoint
    try:
        url = f"{API_BASE_URL.rstrip('/')}/api/v1/student/{student_id}/record_score"
        requests.post(url, json=rec, timeout=0.8)
    except Exception:
        pass

    # 2. Direct MongoDB fallback
    db = get_mongodb_connection()
    if db is not None:
        try:
            db["scores"].insert_one(dict(rec))
        except Exception:
            pass

    # 3. In-memory fallback
    if student_id not in _app_in_memory_scores:
        _app_in_memory_scores[student_id] = []
    _app_in_memory_scores[student_id].insert(0, rec)

def api_or_db_get_student_mastery_state(student_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves individual student knowledge and mastery state from FastAPI or MongoDB."""
    # 1. Try FastAPI endpoint
    try:
        url = f"{API_BASE_URL.rstrip('/')}/api/v1/student/{student_id}/mastery"
        resp = requests.get(url, timeout=0.8)
        if resp.status_code == 200:
            data = resp.json()
            if "knowledge_state" in data and data["knowledge_state"]:
                return data["knowledge_state"]
    except Exception:
        pass

    # 2. Direct MongoDB fallback
    db = get_mongodb_connection()
    if db is not None:
        try:
            state_doc = db["student_states"].find_one({"student_id": student_id})
            if state_doc and "knowledge_state" in state_doc and state_doc["knowledge_state"]:
                return state_doc["knowledge_state"]
            user_doc = db["users"].find_one({"student_id": student_id})
            if user_doc and "mastery_state" in user_doc and user_doc["mastery_state"]:
                return user_doc["mastery_state"]
        except Exception:
            pass

    return None

def api_or_db_save_student_mastery_state(
    student_id: str,
    knowledge_state: Dict[str, Any],
    concept_diff: Optional[Dict[str, str]] = None
):
    """Persists updated individual student mastery state to FastAPI and MongoDB."""
    # 1. Try FastAPI endpoint
    try:
        url = f"{API_BASE_URL.rstrip('/')}/api/v1/student/{student_id}/mastery"
        requests.post(url, json={
            "knowledge_state": knowledge_state,
            "concept_difficulties": concept_diff or {}
        }, timeout=0.8)
    except Exception:
        pass

    # 2. Direct MongoDB fallback
    db = get_mongodb_connection()
    now_iso = datetime.now(timezone.utc).isoformat()
    if db is not None:
        try:
            db["student_states"].update_one(
                {"student_id": student_id},
                {"$set": {
                    "student_id": student_id,
                    "knowledge_state": knowledge_state,
                    "concept_difficulties": concept_diff or {},
                    "updated_at": now_iso
                }},
                upsert=True
            )
            db["users"].update_one(
                {"student_id": student_id},
                {"$set": {"mastery_state": knowledge_state, "updated_at": now_iso}}
            )
        except Exception:
            pass

# -------------------------------------------------------------------
# CACHED DATA & RESOURCE LOADERS
# -------------------------------------------------------------------
@st.cache_data
def load_reference_answers() -> dict:
    """Loads reference answers JSON file once and caches it in memory."""
    if os.path.exists(REF_ANSWERS_PATH):
        with open(REF_ANSWERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

REFERENCE_ANSWERS = load_reference_answers()

@st.cache_resource
def load_analyzers():
    """Initializes and caches heavy neural NLP and code analyzers and the selector engine."""
    mcq = MCQAnalyzer()
    code = CodeAnalyzer()
    short_ans = ShortAnswerAnalyzer(model_name="sentence-transformers/all-MiniLM-L6-v2")
    selector_engine = AdaptiveActivitySelector()
    return mcq, code, short_ans, selector_engine

mcq_analyzer, code_analyzer, short_answer_analyzer, selector = load_analyzers()

@st.cache_data(ttl=30, show_spinner=False)
def check_api_status(api_url: str = API_BASE_URL) -> bool:
    """Checks whether the FastAPI backend microservice is reachable."""
    try:
        r = requests.get(f"{api_url.rstrip('/')}/", timeout=0.3)
        return r.status_code == 200
    except Exception:
        return False

@st.cache_data(ttl=600, show_spinner=False)
def fetch_concept_bundle_from_api_or_cache(
    concept: str,
    difficulty: str = "medium",
    api_base_url: str = API_BASE_URL
) -> dict:
    """
    Fetches the targeted 5-question assessment bundle (3 MCQs, 1 Short Answer, 1 Coding challenge).
    Tries the FastAPI microservice endpoint first.
    If the API is offline or unreachable, falls back seamlessly to the cached local reference answers.
    Cached via @st.cache_data to prevent redundant network or disk overhead.
    """
    diff = str(difficulty).lower().strip()
    
    # 1. Try fetching from FastAPI Microservice
    try:
        url = f"{api_base_url.rstrip('/')}/api/v1/concept_bundle/{concept}"
        resp = requests.get(url, params={"difficulty": diff}, timeout=0.5)
        if resp.status_code == 200:
            payload = resp.json()
            bundle = payload.get("bundle", {})
            if bundle and ("mcqs" in bundle or "short_answer" in bundle or "coding" in bundle):
                return {
                    "concept": concept,
                    "difficulty": diff,
                    "bundle": bundle,
                    "source": "FastAPI Microservice (Live API)"
                }
    except Exception:
        pass

    # 2. Fallback to Local Reference Answers Database
    ref_data = load_reference_answers()
    kc_bundle = ref_data.get(concept, ref_data.get("Variables", {}))

    # Parse MCQs for the requested difficulty
    raw_mcqs = kc_bundle.get("mcqs", {})
    if isinstance(raw_mcqs, dict):
        mcqs_list = raw_mcqs.get(diff, raw_mcqs.get("medium", []))
    elif isinstance(raw_mcqs, list):
        mcqs_list = raw_mcqs
    else:
        mcqs_list = []

    # Parse Short Answer
    raw_sa = kc_bundle.get("short_answer", {})
    if isinstance(raw_sa, dict):
        if diff in raw_sa:
            sa_info = raw_sa[diff]
        elif "medium" in raw_sa:
            sa_info = raw_sa["medium"]
        elif "question" in raw_sa:
            sa_info = raw_sa
        else:
            sa_info = list(raw_sa.values())[0] if raw_sa else {}
    else:
        sa_info = {}

    # Parse Coding Problem
    raw_code = kc_bundle.get("coding", {})
    if isinstance(raw_code, dict):
        if diff in raw_code:
            code_info = raw_code[diff]
        elif "medium" in raw_code:
            code_info = raw_code["medium"]
        elif "problem" in raw_code:
            code_info = raw_code
        else:
            code_info = list(raw_code.values())[0] if raw_code else {}
    else:
        code_info = {}

    return {
        "concept": concept,
        "difficulty": diff,
        "bundle": {
            "mcqs": mcqs_list,
            "short_answer": sa_info,
            "coding": code_info
        },
        "source": "Local Reference Store (Cached)"
    }

# -------------------------------------------------------------------
# CACHED DATA FORMATTING & HEAVY UI COMPONENT BUILDERS
# -------------------------------------------------------------------
@st.cache_data
def compute_dashboard_metrics(masteries: tuple, uncertainties: tuple) -> Tuple[float, float]:
    """Calculates global average mastery and uncertainty, cached across widget reruns."""
    avg_m = float(np.mean(masteries)) if masteries else 0.0
    avg_u = float(np.mean(uncertainties)) if uncertainties else 0.0
    return avg_m, avg_u

@st.cache_data
def get_cached_recommendation_info(state_signature: tuple) -> dict:
    """Computes the uncertainty-guided next activity recommendation based on state signature."""
    state_dict = {
        item[0]: {
            "mastery": item[1],
            "uncertainty": item[2],
            "history": []
        }
        for item in state_signature
    }
    return selector.recommend_next_activity(state_dict)

@st.cache_data
def build_radar_chart(masteries: tuple, uncertainties: tuple, concepts: tuple) -> go.Figure:
    """Builds and caches the Plotly Radar Chart figure for student mastery and uncertainty."""
    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=list(masteries) + [masteries[0]],
        theta=list(concepts) + [concepts[0]],
        fill='toself',
        name='Mastery (μ)',
        line_color='#38BDF8',
        fillcolor='rgba(56, 189, 248, 0.25)'
    ))
    fig_radar.add_trace(go.Scatterpolar(
        r=list(uncertainties) + [uncertainties[0]],
        theta=list(concepts) + [concepts[0]],
        fill='toself',
        name='Uncertainty (σ)',
        line_color='#F43F5E',
        fillcolor='rgba(244, 63, 94, 0.25)'
    ))
    fig_radar.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 1.0]),
            bgcolor='rgba(0,0,0,0)'
        ),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=-0.1),
        margin=dict(l=30, r=30, t=20, b=20)
    )
    return fig_radar

@st.cache_data
def build_priority_bar_chart(priorities_tuple: tuple) -> go.Figure:
    """Builds and caches the Plotly Express Bar Chart for concept priority scores."""
    priorities_df = pd.DataFrame([dict(p) for p in priorities_tuple])
    fig_bar = px.bar(
        priorities_df,
        x="concept",
        y="priority_score",
        color="priority_score",
        color_continuous_scale="Purples",
        labels={"priority_score": "Priority Score", "concept": "Concept"},
        title="Uncertainty-Guided Priority: (1.0 - μ) * (1.0 + σ)"
    )
    fig_bar.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        coloraxis_showscale=False,
        margin=dict(l=30, r=30, t=35, b=20)
    )
    return fig_bar

@st.cache_data
def format_recommendation_card_html(
    rec_concept: str,
    rec_activity: str,
    activity_code: int,
    rec_diff: str,
    priority_score: float,
    concept_mastery: float,
    concept_uncertainty: float,
    reasoning: str,
    prerequisite_fallback: bool,
    original_concept: Optional[str],
    modality_downgraded: bool,
    difficulty_floor: bool
) -> str:
    """Formats the styled recommendation card HTML, cached to avoid unnecessary string allocations."""
    diff_style_class = f"diff-{rec_diff}"
    extra_badges = ""
    if prerequisite_fallback:
        extra_badges += f' <span class="diff-badge diff-hard">Prerequisite Fallback (from {original_concept})</span>'
    if modality_downgraded:
        extra_badges += ' <span class="diff-badge diff-medium">Modality Downgraded ➔ MCQ</span>'
    if difficulty_floor:
        extra_badges += ' <span class="diff-badge diff-easy">Difficulty Floor (Cycle New)</span>'

    return f"""
<div class="rec-card">
    <h3>⚡ Uncertainty-Guided Target Concept Recommendation & Policy Scaffolding</h3>
    <p><b>Recommended Concept</b>: <span style="color: #38BDF8; font-size: 1.2rem; font-weight:700;">{rec_concept}</span> &nbsp;|&nbsp; 
       <b>Recommended Modality</b>: <span style="color: #A855F7; font-size: 1.2rem; font-weight:700;">{rec_activity}</span> (Code: {activity_code}) &nbsp;|&nbsp;
       <b>Scaffolded Difficulty</b>: <span class="diff-badge {diff_style_class}">{rec_diff.upper()}</span>
       {extra_badges}
    </p>
    <p><b>Priority Score</b>: <code>{priority_score:.4f}</code> &nbsp;|&nbsp; 
       <b>Mastery (μ)</b>: <code>{concept_mastery*100:.1f}%</code> &nbsp;|&nbsp; 
       <b>Uncertainty (σ)</b>: <code>{concept_uncertainty*100:.1f}%</code></p>
    <p style="color: #CBD5E1;"><b>Policy Reasoning</b>: {reasoning}</p>
</div>
"""

@st.cache_data
def get_cached_scaffold_difficulty(last_score: Optional[float], current_diff: str) -> Tuple[str, str]:
    """Caches difficulty scaffolding policy calculations."""
    return selector.scaffold_difficulty(last_evidence_score=last_score, current_difficulty=current_diff)

@st.cache_data
def format_test_cases_code_blocks(test_cases_json: str) -> str:
    """Formats Python assert test cases into a unified code block string."""
    test_cases = json.loads(test_cases_json) if test_cases_json else []
    if not test_cases:
        return ""
    lines = []
    for t_idx, tc in enumerate(test_cases):
        call_str = tc.get("call", tc.get("input", ""))
        exp_str = tc.get("expected", "")
        desc_str = tc.get("description", "")
        lines.append(f"# Test {t_idx+1}: {desc_str}\nassert {call_str} == {repr(exp_str)}")
    return "\n\n".join(lines)

# -------------------------------------------------------------------
# CACHED EVALUATOR FUNCTIONS
# -------------------------------------------------------------------
@st.cache_data
def evaluate_mcq_cached(student_option: str, correct_option: str) -> dict:
    """Evaluates MCQ option correctness with cached results."""
    return mcq_analyzer.evaluate(student_option=student_option, correct_option=correct_option)

@st.cache_data
def evaluate_short_answer_cached(student_response: str, reference_answer: str) -> dict:
    """Evaluates conceptual short answer using SBERT embeddings with cached results."""
    return short_answer_analyzer.evaluate(student_response=student_response, reference_answer=reference_answer)

@st.cache_data
def evaluate_code_cached(code_string: str, passed_tests: int, total_tests: int, test_cases_json: str) -> dict:
    """Evaluates Python code syntax and test cases with cached results."""
    test_cases = json.loads(test_cases_json) if test_cases_json else []
    return code_analyzer.evaluate(
        code_string=code_string,
        passed_test_cases=passed_tests,
        total_test_cases=total_tests,
        test_cases=test_cases
    )

# -------------------------------------------------------------------
# STUDENT PROFILE PRESETS & INITIALIZATION
# -------------------------------------------------------------------
STUDENT_PRESETS = {
    "S001 (Beginner)": {"Variables": (0.45, 0.65), "Conditionals": (0.30, 0.70), "Loops": (0.20, 0.80), "Functions": (0.15, 0.75), "Arrays": (0.10, 0.85), "Syntax": (0.50, 0.60), "OOP": (0.05, 0.90), "Dictionaries": (0.10, 0.85), "File Handling": (0.05, 0.90), "Exception Handling": (0.05, 0.90)},
    "S002 (Developing)": {"Variables": (0.85, 0.15), "Conditionals": (0.60, 0.30), "Loops": (0.40, 0.50), "Functions": (0.55, 0.25), "Arrays": (0.40, 0.45), "Syntax": (0.88, 0.10), "OOP": (0.30, 0.55), "Dictionaries": (0.35, 0.50), "File Handling": (0.25, 0.60), "Exception Handling": (0.30, 0.55)},
    "S003 (Advanced)": {"Variables": (0.95, 0.05), "Conditionals": (0.92, 0.08), "Loops": (0.88, 0.10), "Functions": (0.85, 0.12), "Arrays": (0.80, 0.15), "Syntax": (0.96, 0.05), "OOP": (0.75, 0.18), "Dictionaries": (0.78, 0.16), "File Handling": (0.72, 0.20), "Exception Handling": (0.70, 0.22)}
}

# -------------------------------------------------------------------
# SESSION STATE INITIALIZATION
# -------------------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user_info" not in st.session_state:
    st.session_state.user_info = {}

if "current_page" not in st.session_state:
    st.session_state.current_page = "dashboard"

if "practice_concept" not in st.session_state:
    st.session_state.practice_concept = "Variables"

if "practice_difficulty" not in st.session_state:
    st.session_state.practice_difficulty = "medium"

if "student_history" not in st.session_state:
    st.session_state.student_history = []

if "tracker" not in st.session_state:
    st.session_state.tracker = KnowledgeStateTracker()

tracker = st.session_state.tracker

# ===================================================================
# FLOW 1: LOGIN & REGISTRATION FORMS (st.session_state.logged_in == False)
# ===================================================================
if not st.session_state.logged_in:
    st.markdown('<div class="main-header" style="text-align: center;">🎓 Adaptive Knowledge Tracing & Intelligent Tutor</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header" style="text-align: center;">Multi-Response Student Behaviour Modeling & Difficulty Scaffolding with PyTorch Behavior-AKT</div>', unsafe_allow_html=True)
    
    auth_col1, auth_col2, auth_col3 = st.columns([1, 2, 1])
    with auth_col2:
        auth_tab_login, auth_tab_register = st.tabs(["🔑 Student Login", "📝 New Student Registration"])
        
        # --- TAB 1: LOGIN ---
        with auth_tab_login:
            st.markdown("### Sign In to Your Learning Arena")
            with st.form("login_form"):
                login_user = st.text_input("Username", placeholder="e.g. alex123", key="login_username_input")
                login_pass = st.text_input("Password", type="password", placeholder="••••••••", key="login_password_input")
                login_submit = st.form_submit_button("🚀 Sign In to Dashboard", use_container_width=True)
                
                if login_submit:
                    success, msg, user_data = api_or_db_login(login_user, login_pass)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.user_info = user_data
                        st.session_state.current_page = "dashboard"
                        st.session_state.student_history = api_or_db_get_student_history(user_data["student_id"])
                        saved_state = api_or_db_get_student_mastery_state(user_data["student_id"])
                        if saved_state:
                            for c_name, c_data in saved_state.items():
                                st.session_state.tracker.set_concept_state(
                                    c_name,
                                    mastery=float(c_data.get("mastery", 0.30)),
                                    uncertainty=float(c_data.get("uncertainty", 0.50)),
                                    history=c_data.get("history", [])
                                )
                        st.success(f"Welcome back, {user_data.get('full_name', user_data.get('username'))}!")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
        
        # --- TAB 2: REGISTRATION ---
        with auth_tab_register:
            st.markdown("### Register New Student Profile")
            with st.form("register_form"):
                reg_name = st.text_input("Full Name (Optional)", placeholder="e.g. Alex Johnson", key="reg_fullname_input")
                reg_email = st.text_input("Email (Optional)", placeholder="e.g. alex@university.edu", key="reg_email_input")
                reg_user = st.text_input("Choose Username (min 3 chars)", placeholder="e.g. alex_tutor", key="reg_username_input")
                reg_pass = st.text_input("Choose Password (min 4 chars)", type="password", placeholder="••••••••", key="reg_password_input")
                reg_submit = st.form_submit_button("✨ Register & Create Student ID in MongoDB", use_container_width=True)
                
                if reg_submit:
                    success, msg, user_data = api_or_db_register(
                        username=reg_user,
                        password=reg_pass,
                        full_name=reg_name,
                        email=reg_email
                    )
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.user_info = user_data
                        st.session_state.current_page = "dashboard"
                        st.session_state.student_history = []
                        saved_state = api_or_db_get_student_mastery_state(user_data["student_id"])
                        if saved_state:
                            for c_name, c_data in saved_state.items():
                                st.session_state.tracker.set_concept_state(
                                    c_name,
                                    mastery=float(c_data.get("mastery", 0.30)),
                                    uncertainty=float(c_data.get("uncertainty", 0.50)),
                                    history=c_data.get("history", [])
                                )
                        st.success(f"🎉 Account registered! Assigned Student ID: **{user_data['student_id']}**")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
        
        # Quick Demo Access
        st.markdown("---")
        st.markdown("<p style='text-align: center; color: #94A3B8; font-size: 0.9rem;'>Or test immediately with a 1-click preset student:</p>", unsafe_allow_html=True)
        d_col1, d_col2, d_col3 = st.columns(3)
        with d_col1:
            if st.button("⚡ S001 (Beginner)", use_container_width=True):
                st.session_state.logged_in = True
                st.session_state.user_info = {"student_id": "S001", "username": "student_s001", "full_name": "S001 (Beginner Profile)"}
                st.session_state.current_page = "dashboard"
                st.session_state.student_history = api_or_db_get_student_history("S001")
                for c_name, (m, u) in STUDENT_PRESETS["S001 (Beginner)"].items():
                    st.session_state.tracker.set_concept_state(c_name, mastery=m, uncertainty=u)
                api_or_db_save_student_mastery_state("S001", st.session_state.tracker.get_knowledge_state())
                st.rerun()
        with d_col2:
            if st.button("⚡ S002 (Developing)", use_container_width=True):
                st.session_state.logged_in = True
                st.session_state.user_info = {"student_id": "S002", "username": "student_s002", "full_name": "S002 (Developing Profile)"}
                st.session_state.current_page = "dashboard"
                st.session_state.student_history = api_or_db_get_student_history("S002")
                for c_name, (m, u) in STUDENT_PRESETS["S002 (Developing)"].items():
                    st.session_state.tracker.set_concept_state(c_name, mastery=m, uncertainty=u)
                api_or_db_save_student_mastery_state("S002", st.session_state.tracker.get_knowledge_state())
                st.rerun()
        with d_col3:
            if st.button("⚡ S003 (Advanced)", use_container_width=True):
                st.session_state.logged_in = True
                st.session_state.user_info = {"student_id": "S003", "username": "student_s003", "full_name": "S003 (Advanced Profile)"}
                st.session_state.current_page = "dashboard"
                st.session_state.student_history = api_or_db_get_student_history("S003")
                for c_name, (m, u) in STUDENT_PRESETS["S003 (Advanced)"].items():
                    st.session_state.tracker.set_concept_state(c_name, mastery=m, uncertainty=u)
                api_or_db_save_student_mastery_state("S003", st.session_state.tracker.get_knowledge_state())
                st.rerun()

    st.stop()

# ===================================================================
# LOGGED-IN SIDEBAR CONTROLS
# ===================================================================
user_info = st.session_state.get("user_info", {})
student_id = user_info.get("student_id", "S001")
full_name = user_info.get("full_name", user_info.get("username", "Student"))

# 1. User Profile Information in Sidebar
st.sidebar.markdown(f"### 👤 {full_name}")
st.sidebar.markdown(f"**Student ID**: `{student_id}` &nbsp; <span class='status-badge'>Online</span>", unsafe_allow_html=True)
st.sidebar.markdown("---")

# Compute knowledge state metrics for concept selector
state_dict = tracker.get_knowledge_state()
concepts_list = list(REFERENCE_ANSWERS.keys()) if REFERENCE_ANSWERS else list(state_dict.keys())
masteries = [state_dict.get(c, {}).get("mastery", 0.30) for c in concepts_list]
uncertainties = [state_dict.get(c, {}).get("uncertainty", 0.50) for c in concepts_list]
avg_m, avg_u = compute_dashboard_metrics(tuple(masteries), tuple(uncertainties))

state_sig = tuple(
    (c, round(state_dict.get(c, {}).get("mastery", 0.3), 4), round(state_dict.get(c, {}).get("uncertainty", 0.5), 4))
    for c in sorted(concepts_list)
)
rec_info = get_cached_recommendation_info(state_sig)

# 2. Concept Selector Dropdown & Difficulty Selector in Sidebar
st.sidebar.subheader("🎯 Learning Target")

default_c_idx = 0
if st.session_state.practice_concept in concepts_list:
    default_c_idx = concepts_list.index(st.session_state.practice_concept)
elif rec_info.get("recommended_concept") in concepts_list:
    default_c_idx = concepts_list.index(rec_info["recommended_concept"])

selected_kc = st.sidebar.selectbox(
    "Select Target Concept:",
    options=concepts_list,
    index=default_c_idx,
    key="sidebar_concept_selector"
)
st.session_state.practice_concept = selected_kc

# Calculate scaffolded difficulty for the selected concept
c_state = state_dict.get(selected_kc, {})
c_hist = c_state.get("history", [])
last_c_score = c_state.get("last_evidence_score", c_hist[-1]["evidence_score"] if c_hist else None)
last_c_diff = c_state.get("last_difficulty", "medium")
auto_c_diff, auto_c_reason = get_cached_scaffold_difficulty(last_c_score, current_diff=last_c_diff)

diff_choices = ["easy", "medium", "hard"]
def_diff_idx = diff_choices.index(auto_c_diff) if auto_c_diff in diff_choices else 1

selected_diff = st.sidebar.selectbox(
    "Difficulty Level:",
    options=diff_choices,
    index=def_diff_idx,
    format_func=lambda x: f"{'🟢 Easy' if x=='easy' else '🟡 Medium' if x=='medium' else '🔴 Hard'} ({x.title()})",
    key="sidebar_difficulty_selector"
)
st.session_state.practice_difficulty = selected_diff
st.sidebar.caption(f"💡 **Scaffolding Policy**: {auto_c_reason}")

# Sidebar Student Presets
with st.sidebar.expander("🎓 Student Profile Presets", expanded=False):
    preset_choice = st.selectbox("Apply Test Profile:", list(STUDENT_PRESETS.keys()), index=1, key="sb_preset_sel")
    if st.button("🔄 Apply Preset", use_container_width=True):
        preset_data = STUDENT_PRESETS[preset_choice]
        for c_name, (m, u) in preset_data.items():
            tracker.set_concept_state(c_name, mastery=m, uncertainty=u)
        api_or_db_save_student_mastery_state(student_id, tracker.get_knowledge_state())
        st.session_state.active_feedback = None
        st.sidebar.success(f"Applied profile {preset_choice}!")
        st.rerun()

# Sidebar System Status
with st.sidebar.expander("⚙️ System Status", expanded=False):
    mongo_ok = get_mongodb_connection() is not None
    if mongo_ok:
        st.success("🟢 MongoDB: Connected")
    else:
        st.info("⚪ MongoDB: In-Memory Fallback")

    api_ok = check_api_status(API_BASE_URL)
    if api_ok:
        st.success("🟢 API Service: Online (Live)")
    else:
        st.info("⚪ API Service: Offline (Local Cache)")

    st.caption("• PyTorch Behavior-AKT\n• SBERT Short Answer Rubric\n• Motor Async MongoDB Driver")

    if st.button("🧹 Clear App Cache", use_container_width=True):
        st.cache_data.clear()
        st.session_state.pop("current_question_bundle", None)
        st.session_state.pop("current_bundle_key", None)
        st.success("Cache cleared!")
        st.rerun()

# 3. Logout Button in Sidebar
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Logout", use_container_width=True, type="secondary"):
    st.session_state.logged_in = False
    st.session_state.user_info = {}
    st.session_state.active_feedback = None
    st.session_state.current_page = "dashboard"
    st.session_state.student_history = []
    st.session_state.tracker = KnowledgeStateTracker()
    st.rerun()

# ===================================================================
# MAIN VIEW: WELCOME & TABS
# ===================================================================
st.markdown(f'<div class="main-header">Welcome, {full_name}! 👋</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="sub-header">Student ID: <b>{student_id}</b> | Active Target: <b>{selected_kc}</b> (<span class="diff-badge diff-{selected_diff}">{selected_diff.upper()}</span>) | <span class="status-badge">System Live</span></div>',
    unsafe_allow_html=True
)

tab_overview, tab_practice = st.tabs(["📊 Performance Overview", "🧠 Practice Arena"])

# ===================================================================
# TAB 1: 📊 PERFORMANCE OVERVIEW
# ===================================================================
with tab_overview:
    # 1. High-Level Metrics Horizontally at the Top via st.columns
    score_history = api_or_db_get_student_history(student_id)
    if score_history:
        overall_accuracy = float(np.mean([float(h.get("bundle_average_score", 0.0)) for h in score_history])) * 100
        total_attempts = len(score_history)
    else:
        overall_accuracy = avg_m * 100
        total_attempts = 0

    curr_kc_mastery = state_dict.get(selected_kc, {}).get("mastery", 0.30) * 100
    curr_kc_uncertainty = state_dict.get(selected_kc, {}).get("uncertainty", 0.50) * 100

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f'<div class="card"><div class="metric-label">Overall Accuracy</div><div class="metric-value">{overall_accuracy:.1f}%</div><div style="font-size:0.75rem; color:#94A3B8;">Across {total_attempts} completed sessions</div></div>',
            unsafe_allow_html=True
        )
    with col2:
        st.markdown(
            f'<div class="card"><div class="metric-label">Total Attempts</div><div class="metric-value">{total_attempts}</div><div style="font-size:0.75rem; color:#94A3B8;">Recorded in MongoDB</div></div>',
            unsafe_allow_html=True
        )
    with col3:
        st.markdown(
            f'<div class="card"><div class="metric-label">Current Mastery ({selected_kc})</div><div class="metric-value">{curr_kc_mastery:.1f}%</div><div style="font-size:0.75rem; color:#94A3B8;">Uncertainty (σ): {curr_kc_uncertainty:.1f}%</div></div>',
            unsafe_allow_html=True
        )
    with col4:
        st.markdown(
            f'<div class="card"><div class="metric-label">Top Recommendation</div><div class="metric-value" style="font-size:1.4rem;">{rec_info["recommended_concept"]}</div><div style="font-size:0.75rem; color:#94A3B8;">Priority Score: {rec_info["priority_score"]:.3f}</div></div>',
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Mastery / Uncertainty Radar Chart Centered Below Metrics
    st.subheader("🎯 Real-Time Knowledge State Radar Chart")
    r_col1, r_col2, r_col3 = st.columns([1, 4, 1])
    with r_col2:
        fig_radar = build_radar_chart(tuple(masteries), tuple(uncertainties), tuple(concepts_list))
        st.plotly_chart(fig_radar, use_container_width=True)

    st.markdown("---")

    # Concept Competency Grid
    st.subheader("📋 Concept Competencies Breakdown")
    # Display in rows of 5 for readability with 10 concepts
    grid_row_size = 5
    for row_start in range(0, len(concepts_list), grid_row_size):
        row_concepts = concepts_list[row_start:row_start + grid_row_size]
        grid_cols = st.columns(len(row_concepts))
        for idx, c_name in enumerate(row_concepts):
            c_m = state_dict.get(c_name, {}).get("mastery", 0.30)
            c_u = state_dict.get(c_name, {}).get("uncertainty", 0.50)
            badge_cls = "diff-easy" if c_m >= 0.75 else "diff-medium" if c_m >= 0.45 else "diff-hard"
            badge_lbl = "Mastered" if c_m >= 0.75 else "In Progress" if c_m >= 0.45 else "Focus Area"
            border_highlight = "border: 2px solid #38BDF8;" if c_name == selected_kc else ""
            with grid_cols[idx]:
                st.markdown(f"""
            <div class="concept-tile" style="{border_highlight}">
                <div style="font-weight:700; color: #F8FAFC; font-size: 0.95rem;">{c_name}</div>
                <div style="font-size: 1.2rem; font-weight:700; color: #38BDF8; margin: 4px 0;">{c_m*100:.0f}%</div>
                <div style="font-size: 0.75rem; color: #94A3B8;">σ: {c_u*100:.0f}%</div>
                <div style="margin-top: 6px;"><span class="diff-badge {badge_cls}" style="font-size: 0.7rem;">{badge_lbl}</span></div>
            </div>
            """, unsafe_allow_html=True)

    # Uncertainty-Guided Recommendation Policy Card
    rec_card_html = format_recommendation_card_html(
        rec_concept=rec_info["recommended_concept"],
        rec_activity=rec_info["recommended_activity"],
        activity_code=rec_info["activity_code"],
        rec_diff=rec_info.get("recommended_difficulty", "medium"),
        priority_score=rec_info["priority_score"],
        concept_mastery=rec_info["concept_mastery"],
        concept_uncertainty=rec_info["concept_uncertainty"],
        reasoning=rec_info["reasoning"],
        prerequisite_fallback=bool(rec_info.get("prerequisite_fallback_applied")),
        original_concept=rec_info.get("original_concept"),
        modality_downgraded=bool(rec_info.get("modality_downgraded")),
        difficulty_floor=bool(rec_info.get("difficulty_floor_active"))
    )
    st.markdown(rec_card_html, unsafe_allow_html=True)

    # 3. Historical Score Table inside st.expander('View History')
    with st.expander("📜 View History (Past Practice Sessions)", expanded=False):
        if score_history:
            history_rows = []
            for h in score_history:
                t_val = str(h.get("timestamp", "-")).replace("T", " ")
                history_rows.append({
                    "Date / Time": t_val[:19] if len(t_val) >= 19 else t_val,
                    "Concept": h.get("concept", "-"),
                    "Difficulty": str(h.get("difficulty", "-")).upper(),
                    "Bundle Avg": f"{float(h.get('bundle_average_score', 0.0)) * 100:.1f}%",
                    "MCQs Avg": f"{float(np.mean(h.get('mcq_scores', [0.0]))) * 100:.1f}%",
                    "Short Answer": f"{float(h.get('short_answer_score', 0.0)) * 100:.1f}%",
                    "Coding Score": f"{float(h.get('code_score', 0.0)) * 100:.1f}%",
                    "Next Level": str(h.get("next_difficulty", "-")).upper()
                })
            df_hist = pd.DataFrame(history_rows)
            st.dataframe(df_hist, use_container_width=True, hide_index=True)
        else:
            st.info("ℹ️ No practice assessment sessions recorded yet. Switch to the **'🧠 Practice Arena'** tab to complete your first 5-question assessment bundle!")

# ===================================================================
# TAB 2: 🧠 PRACTICE ARENA
# ===================================================================
with tab_practice:
    # Dedicated Placeholder for Clean Feedback Banners (Prevents Jarring Layout Shifts)
    feedback_placeholder = st.empty()

    if st.session_state.get("active_feedback"):
        fb = st.session_state.active_feedback
        with feedback_placeholder.container():
            st.markdown(f"""
            <div class="rec-card" style="border: 2px solid #38BDF8; margin-bottom: 1.5rem;">
                <h3 style="color: #38BDF8; margin-top:0;">🎯 Assessment Results — {fb['concept']} ({fb['difficulty'].upper()})</h3>
                <p><b>Updated Concept Mastery</b>: <code>{fb['updated_mastery']*100:.1f}%</code> &nbsp;|&nbsp; 
                   <b>Uncertainty (σ)</b>: <code>{fb['updated_uncertainty']*100:.1f}%</code></p>
            </div>
            """, unsafe_allow_html=True)

            # Overview Metrics
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Bundle Average", f"{fb['bundle_avg_score'] * 100:.1f}%")
            with m2:
                st.metric("MCQs Average", f"{np.mean(fb['mcq_scores']) * 100:.1f}%")
            with m3:
                st.metric("SBERT Similarity", f"{fb['short_answer']['similarity_percentage']:.1f}%")
            with m4:
                st.metric(
                    "Coding Pass Fraction",
                    f"{fb['coding']['passed_test_cases']}/{fb['coding']['total_test_cases']} ({fb['coding']['pass_fraction'] * 100:.1f}%)"
                )

            st.info(f"📈 **Scaffolding Policy Advice**: {fb['scaffolding']['explanation']}")

            # Detailed Question-by-Question Grading Breakdown
            with st.expander("🔍 Detailed Question-by-Question Grading Breakdown", expanded=True):
                # 1. MCQs Breakdown
                st.markdown("##### 1. Multiple Choice Questions Review")
                for mcq in fb["mcq_details"]:
                    if mcq["is_correct"]:
                        st.success(
                            f"✅ **MCQ {mcq['index']}**: **Correct!** (You selected `{mcq['selected_option']}`)\n\n"
                            f"**Question**: *{mcq['question']}*"
                        )
                    else:
                        st.error(
                            f"❌ **MCQ {mcq['index']}**: **Incorrect!** You selected `{mcq['selected_option']}`, but the **correct option is {mcq['correct_option']}**.\n\n"
                            f"**Question**: *{mcq['question']}*"
                        )

                # 2. Conceptual Short Answer Review
                st.markdown("##### 2. Conceptual Short Answer Review")
                sa_res = fb["short_answer"]
                sa_sim = sa_res["similarity_percentage"]
                if sa_res["is_acceptable"]:
                    st.success(f"✅ **SBERT Semantic Similarity Score**: **{sa_sim:.1f}%** (Conceptually Sound)")
                else:
                    st.error(f"❌ **SBERT Semantic Similarity Score**: **{sa_sim:.1f}%** (Below Acceptance Threshold)")

                st.markdown(f"**Your Response**:\n> *{sa_res['student_response'] if sa_res['student_response'].strip() else '(No response submitted)'}*")
                st.markdown(f"**Official Reference Rubric**:\n> *{sa_res['reference_answer']}*")

                if sa_res["missing_keywords"]:
                    st.warning(f"🔍 **Missing Conceptual Keywords**: **{', '.join(sa_res['missing_keywords'])}**")
                else:
                    st.success("🎉 All key conceptual terminology was accurately addressed!")

                # 3. Python Coding Sandbox Review
                st.markdown("##### 3. Python Coding Sandbox Review")
                code_res = fb["coding"]
                c_pass = code_res["passed_test_cases"]
                c_total = code_res["total_test_cases"]
                c_frac = code_res["pass_fraction"]

                if code_res["syntax_error"]:
                    st.error(f"🚨 **Syntax Error Detected**: `{code_res['syntax_error']}`")
                elif code_res["runtime_error"]:
                    st.error(f"⚠️ **Runtime Error Detected**: `{code_res['runtime_error']}`")
                else:
                    st.success("✅ Code compiled cleanly with no syntax or runtime errors!")

                if c_frac >= 1.0:
                    st.success(f"💯 **Test Cases Passed**: **{c_pass}/{c_total}** (Pass Fraction: **{c_frac * 100:.1f}%**)")
                elif c_frac > 0.0:
                    st.warning(f"⚠️ **Partial Pass**: **{c_pass}/{c_total}** unit test cases passed ({c_frac * 100:.1f}%)")
                else:
                    st.error(f"❌ **Failed Unit Tests**: **{c_pass}/{c_total}** test cases passed")

            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("➡️ Practice Next / Scaffolded Level", key="practice_next_btn", type="primary", use_container_width=True):
                    st.session_state.practice_difficulty = fb['scaffolding']['next_difficulty']
                    st.session_state.active_feedback = None
                    st.rerun()
            with btn_col2:
                if st.button("✕ Dismiss Feedback", key="dismiss_feedback_btn", use_container_width=True):
                    st.session_state.active_feedback = None
                    st.rerun()

            st.markdown("---")

    # Load Active Assessment Bundle (Cached in session state)
    bundle_key = f"{selected_kc}_{selected_diff}"
    if (
        "current_question_bundle" not in st.session_state
        or st.session_state.get("current_bundle_key") != bundle_key
    ):
        with st.spinner(f"Loading assessment bundle for {selected_kc} ({selected_diff.title()})..."):
            st.session_state.current_question_bundle = fetch_concept_bundle_from_api_or_cache(
                concept=selected_kc,
                difficulty=selected_diff,
                api_base_url=API_BASE_URL
            )
            st.session_state.current_bundle_key = bundle_key

    bundle_payload = st.session_state.current_question_bundle
    bundle = bundle_payload.get("bundle", {})
    mcqs_list = bundle.get("mcqs", [])
    sa_info = bundle.get("short_answer", {})
    code_info = bundle.get("coding", {})
    bundle_source = bundle_payload.get("source", "Session State")

    header_col1, header_col2 = st.columns([3, 1])
    with header_col1:
        st.markdown(f"### 📋 {selected_kc} Assessment Bundle — <span class='diff-badge diff-{selected_diff}'>{selected_diff.upper()}</span>", unsafe_allow_html=True)
        st.caption(f"Source: {bundle_source} | Complete all 5 questions below and submit simultaneously to update your knowledge state.")
    with header_col2:
        if st.button("🔄 Reload Questions", key=f"reload_btn_{bundle_key}", help="Force re-fetch bundle"):
            fetch_concept_bundle_from_api_or_cache.clear()
            st.session_state.current_question_bundle = fetch_concept_bundle_from_api_or_cache(
                concept=selected_kc,
                difficulty=selected_diff,
                api_base_url=API_BASE_URL
            )
            st.session_state.current_bundle_key = bundle_key
            st.rerun()

    # Form-Batched 5-Question Assessment
    with st.form(key=f"bundle_form_{selected_kc}_{selected_diff}"):
        # Group 1: 3 MCQs
        st.subheader("1. Multiple Choice Questions (3 MCQs)")
        selected_mcq_opts = []
        for idx, mcq in enumerate(mcqs_list[:3]):
            st.markdown(f"**MCQ {idx+1}**: {mcq.get('question', 'Question text')}")
            opt_choice = st.radio(
                f"Select Option for MCQ {idx+1}:",
                options=mcq.get("options", ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"]),
                key=f"mcq_{idx+1}_{selected_kc}_{selected_diff}"
            )
            opt_letter = opt_choice.split(")")[0].strip().upper()
            selected_mcq_opts.append(opt_letter)
            if idx < 2:
                st.markdown("---")

        st.markdown("---")

        # Group 2: 1 Conceptual Short Answer
        st.subheader("2. Conceptual Short Answer")
        st.markdown(f"**Question**: {sa_info.get('question', 'Explain the concept.')}")
        st.caption(f"ℹ️ Evaluated against official rubric: '{sa_info.get('reference_answer', '')}'")
        
        short_answer_text = st.text_area(
            "Write your explanation below:",
            value="",
            height=110,
            placeholder="Type your conceptual explanation...",
            key=f"sa_text_{selected_kc}_{selected_diff}"
        )

        st.markdown("---")

        # Group 3: 1 Coding Sandbox
        st.subheader("3. Python Coding Sandbox")
        st.markdown(f"**Problem Statement**: {code_info.get('problem', 'Write Python code solution.')}")
        
        code_solution_text = st.text_area(
            "Write Python Solution Code:",
            value=code_info.get("template", "def solution():\n    pass\n"),
            height=140,
            key=f"code_text_{selected_kc}_{selected_diff}"
        )
        
        test_cases = code_info.get("test_cases", [])
        if test_cases:
            st.markdown(f"**Included Unit Test Cases ({len(test_cases)}):**")
            test_cases_code = format_test_cases_code_blocks(json.dumps(test_cases))
            st.code(test_cases_code, language="python")

        t_col1, t_col2 = st.columns(2)
        with t_col1:
            default_passed = len(test_cases) if test_cases else 8
            passed_test_cases = st.slider("Passed Unit Test Cases:", 0, 10, min(10, default_passed), key=f"passed_slider_{selected_kc}_{selected_diff}")
        with t_col2:
            default_total = len(test_cases) if test_cases else 10
            total_test_cases = st.slider("Total Unit Test Cases:", 1, 10, min(10, max(1, default_total)), key=f"total_slider_{selected_kc}_{selected_diff}")

        st.markdown("<br>", unsafe_allow_html=True)
        submit_bundle_btn = st.form_submit_button("🚀 Submit Complete 5-Question Concept Assessment Bundle", use_container_width=True, type="primary")

    # Form Submission Handler
    if submit_bundle_btn:
        with st.spinner("Evaluating 5-question bundle & updating Behavior-AKT knowledge state..."):
            mcq_scores = []
            mcq_feedbacks = []
            mcq_details = []
            
            # 1. Evaluate 3 MCQs
            for idx, mcq in enumerate(mcqs_list[:3]):
                s_opt = selected_mcq_opts[idx] if idx < len(selected_mcq_opts) else "A"
                c_opt = mcq.get("correct_option", "A")
                eval_res = evaluate_mcq_cached(student_option=s_opt, correct_option=c_opt)
                score = eval_res["evidence_score"]
                is_corr = bool(eval_res["is_correct"])
                mcq_scores.append(score)
                status_str = "✅ Correct" if is_corr else f"❌ Incorrect (Correct: {c_opt})"
                mcq_feedbacks.append(f"MCQ {idx+1} ({selected_diff.title()}): {status_str} (Selected: {s_opt})")
                
                mcq_details.append({
                    "index": idx + 1,
                    "question": mcq.get("question", f"Question {idx+1}"),
                    "options": mcq.get("options", []),
                    "selected_option": s_opt,
                    "correct_option": c_opt,
                    "is_correct": is_corr,
                    "score": score
                })
                tracker.update_state(selected_kc, evidence_score=score, activity_type=0, difficulty=selected_diff)

            # 2. Evaluate Short Answer with SBERT
            ref_sa_text = sa_info.get("reference_answer", "Variables store data values in computer memory.")
            sa_eval = evaluate_short_answer_cached(student_response=short_answer_text, reference_answer=ref_sa_text)
            sa_score = float(sa_eval["evidence_score"])
            sim_pct = float(sa_eval.get("similarity_percentage", round(sa_score * 100, 1)))
            missing_kws = sa_eval.get("missing_keywords", [])
            is_sa_acceptable = bool(sa_eval.get("is_acceptable", sa_score >= 0.5))
            
            tracker.update_state(selected_kc, evidence_score=sa_score, activity_type=2, difficulty=selected_diff)

            # 3. Evaluate Coding Sandbox
            code_eval = evaluate_code_cached(
                code_string=code_solution_text,
                passed_tests=passed_test_cases,
                total_tests=total_test_cases,
                test_cases_json=json.dumps(code_info.get("test_cases", []))
            )
            code_score = float(code_eval["evidence_score"])
            code_passed = int(code_eval.get("passed_test_cases", passed_test_cases))
            code_total = int(code_eval.get("total_test_cases", total_test_cases))
            code_pass_frac = float(code_eval.get("pass_fraction", code_score))
            
            upd_state = tracker.update_state(selected_kc, evidence_score=code_score, activity_type=1, difficulty=selected_diff)
            bundle_avg_score = float(np.mean(mcq_scores + [sa_score, code_score]))

            # Difficulty Scaffolding Policy
            next_scaffold_diff, scaffold_explanation = selector.scaffold_difficulty(
                last_evidence_score=bundle_avg_score,
                current_difficulty=selected_diff
            )

            # Persist Score in MongoDB & Session History
            api_or_db_record_score(
                student_id=student_id,
                concept=selected_kc,
                difficulty=selected_diff,
                bundle_average_score=bundle_avg_score,
                mcq_scores=mcq_scores,
                short_answer_score=sa_score,
                code_score=code_score,
                next_difficulty=next_scaffold_diff,
                scaffolding_reasoning=scaffold_explanation
            )

            # Persist individual student mastery state to MongoDB
            api_or_db_save_student_mastery_state(student_id, tracker.get_knowledge_state(), {selected_kc: next_scaffold_diff})

            # Save full feedback into session state
            st.session_state.active_feedback = {
                "concept": selected_kc,
                "difficulty": selected_diff,
                "bundle_avg_score": bundle_avg_score,
                "mcq_scores": mcq_scores,
                "mcq_details": mcq_details,
                "short_answer": {
                    "question": sa_info.get("question", "Explain the concept."),
                    "student_response": short_answer_text,
                    "reference_answer": ref_sa_text,
                    "score": sa_score,
                    "similarity_percentage": sim_pct,
                    "missing_keywords": missing_kws,
                    "is_acceptable": is_sa_acceptable,
                    "feedback": sa_eval.get("feedback", "")
                },
                "coding": {
                    "problem": code_info.get("problem", "Write Python code solution."),
                    "code_string": code_solution_text,
                    "score": code_score,
                    "pass_fraction": code_pass_frac,
                    "passed_test_cases": code_passed,
                    "total_test_cases": code_total,
                    "is_compilable": bool(code_eval.get("is_compilable", True)),
                    "syntax_valid": bool(code_eval.get("syntax_valid", True)),
                    "syntax_error": code_eval.get("syntax_error"),
                    "runtime_error": code_eval.get("runtime_error")
                },
                "scaffolding": {
                    "next_difficulty": next_scaffold_diff,
                    "explanation": scaffold_explanation
                },
                "updated_mastery": upd_state["mastery"],
                "updated_uncertainty": upd_state["uncertainty"]
            }
            st.rerun()

# Footer
st.markdown("<br><hr>", unsafe_allow_html=True)
st.caption(f"Adaptive Knowledge Tracing System | Logged in as {full_name} ({student_id}) | Multi-Response Behavior AKT & Scaffolding.")
