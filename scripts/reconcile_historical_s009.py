#!/usr/bin/env python3
"""
scripts/reconcile_historical_s009.py

Controlled S009 Historical EMA Replay Utility (Phase 3.3.4.35B).
Performs restart-safe, idempotent, in-place reconciliation of existing historical
assessment records for student S009 in database akt_tutor_test.

Strict Safety Guarantees:
1. Enforces multi-factor verification gate:
   - AKT_TEST_DB_VERIFIED=true
   - AKT_TEST_DB_ISOLATION_VERIFIED=true
   - MONGO_DB_NAME=akt_tutor_test
2. Never accesses or modifies production database 'akt_tutor'.
3. Never inserts new score documents; updates existing records strictly in-place.
4. Uses existing KnowledgeStateTracker EMA transitions (alpha=0.20, activity_type=0).
5. Supports --dry-run and --apply modes.
"""

import os
import sys
import argparse
from datetime import datetime, timezone
from bson import ObjectId
import pymongo

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.engine.knowledge_state import KnowledgeStateTracker

TARGET_STUDENT_ID = "S009"
APPROVED_TEST_DB = "akt_tutor_test"
FORBIDDEN_PROD_DB = "akt_tutor"

EXPECTED_DOC_IDS = {
    "Exception Handling": ObjectId("6af0bb50fd999b6b2429a997"),
    "Loops": ObjectId("6af0c433fd999b6b2429a998")
}

EXPECTED_TIMESTAMPS = {
    "Exception Handling": "2026-11-08T18:11:28.274Z",
    "Loops": "2026-11-08T18:49:23.759Z"
}

EXPECTED_MCQS = {
    "Exception Handling": [1.0, 0.0, 0.0],
    "Loops": [1.0, 1.0, 1.0]
}

TARGET_VALUES = {
    "Exception Handling": {
        "mastery": 0.2816,
        "uncertainty": 0.3070625,
        "attempts": 3
    },
    "Loops": {
        "mastery": 0.6416,
        "uncertainty": 0.3070625,
        "attempts": 3
    }
}

OTHER_8_CONCEPTS = [
    "Variables", "Conditionals", "Functions", "Arrays",
    "Syntax", "OOP", "Dictionaries", "File Handling"
]


def verify_environment_gates():
    """Validates multi-factor isolation flags and environment variables."""
    flag_verified = os.getenv("AKT_TEST_DB_VERIFIED", "").strip().lower() == "true"
    flag_isolation = os.getenv("AKT_TEST_DB_ISOLATION_VERIFIED", "").strip().lower() == "true"
    env_db = os.getenv("MONGO_DB_NAME", "").strip()

    if not flag_verified or not flag_isolation:
        sys.exit(
            "ABORT: Multi-factor verification flags missing or false.\n"
            "Both AKT_TEST_DB_VERIFIED=true and AKT_TEST_DB_ISOLATION_VERIFIED=true are required."
        )

    if env_db != APPROVED_TEST_DB:
        sys.exit(
            f"ABORT: MONGO_DB_NAME ('{env_db}') must equal exactly '{APPROVED_TEST_DB}'."
        )

    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/").strip()
    if "mongodb+srv://" in mongo_uri or "mongodb.net" in mongo_uri.lower():
        sys.exit("ABORT: Remote Atlas or SRV URI detected. Local test server required.")


def connect_and_verify_database():
    """Connects to MongoDB and verifies the database object strictly matches akt_tutor_test."""
    mongo_uri = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/")
    client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)

    # Ping server
    client.admin.command("ping")

    db = client[APPROVED_TEST_DB]
    if db.name != APPROVED_TEST_DB:
        sys.exit(f"ABORT: Database name '{db.name}' does not match '{APPROVED_TEST_DB}'.")
    if db.name == FORBIDDEN_PROD_DB:
        sys.exit(f"FATAL: Attempted connection to production database '{FORBIDDEN_PROD_DB}'. Aborting.")

    return client, db


def run_preflight_checks(db):
    """Executes mandatory preflight checks against S009 documents in akt_tutor_test."""
    print("=" * 70)
    print("1. RUNNING PREFLIGHT CHECKS")
    print("=" * 70)

    # 1. Check exact score count for S009
    score_count = db["scores"].count_documents({"student_id": TARGET_STUDENT_ID})
    print(f"[*] S009 score document count: {score_count} (Expected: 2)")
    if score_count != 2:
        sys.exit(f"ABORT: Expected exactly 2 score documents for {TARGET_STUDENT_ID}, found {score_count}.")

    scores = list(db["scores"].find({"student_id": TARGET_STUDENT_ID}).sort("timestamp", 1))

    # 2. Verify score document contents and IDs
    for doc in scores:
        concept = doc.get("concept")
        doc_id = doc.get("_id")
        timestamp = doc.get("timestamp")
        mcqs = doc.get("mcq_scores")

        print(f"\n[*] Inspecting score doc: concept='{concept}', _id={doc_id}")
        if concept not in EXPECTED_DOC_IDS:
            sys.exit(f"ABORT: Unexpected concept '{concept}' for {TARGET_STUDENT_ID}.")

        expected_id = EXPECTED_DOC_IDS[concept]
        if doc_id != expected_id:
            sys.exit(f"ABORT: Document _id '{doc_id}' does not match expected '{expected_id}'.")

        expected_ts = EXPECTED_TIMESTAMPS[concept]
        if timestamp != expected_ts:
            sys.exit(f"ABORT: Document timestamp '{timestamp}' does not match expected '{expected_ts}'.")

        expected_mcqs = EXPECTED_MCQS[concept]
        if mcqs != expected_mcqs:
            sys.exit(f"ABORT: Document mcq_scores {mcqs} does not match expected {expected_mcqs}.")

    # 3. Check student_states document
    state_doc = db["student_states"].find_one({"student_id": TARGET_STUDENT_ID})
    if not state_doc:
        sys.exit(f"ABORT: student_states document missing for {TARGET_STUDENT_ID}.")

    ks = state_doc.get("knowledge_state", {})
    print(f"\n[*] Inspecting current S009 knowledge_state in student_states:")
    for concept in ["Exception Handling", "Loops"]:
        c_state = ks.get(concept, {})
        mastery = c_state.get("mastery")
        uncertainty = c_state.get("uncertainty")
        attempts = c_state.get("attempts", 0)
        history = c_state.get("history", [])
        print(f"    - {concept}: mastery={mastery}, uncertainty={uncertainty}, attempts={attempts}, history_len={len(history)}")

    for concept in OTHER_8_CONCEPTS:
        c_state = ks.get(concept, {})
        if c_state.get("mastery") != 0.30 or c_state.get("uncertainty") != 0.50:
            sys.exit(f"ABORT: Concept '{concept}' not at expected prior (0.30, 0.50).")

    print("\n[+] ALL PREFLIGHT CHECKS PASSED SUCCESSFULLY.")
    return scores, state_doc


def simulate_or_execute_replay(db, scores, state_doc, dry_run=True):
    """Performs dry-run simulation or live in-place execution of the replay protocol."""
    mode_str = "DRY-RUN SIMULATION (NO WRITES)" if dry_run else "LIVE REPLAY EXECUTION (--apply)"
    print("\n" + "=" * 70)
    print(f"2. {mode_str}")
    print("=" * 70)

    # Initialize tracker from existing state
    tracker = KnowledgeStateTracker()
    ks = state_doc.get("knowledge_state", {})
    for c_name, c_data in ks.items():
        tracker.set_concept_state(
            c_name,
            mastery=float(c_data.get("mastery", 0.30)),
            uncertainty=float(c_data.get("uncertainty", 0.50)),
            history=c_data.get("history", []),
            attempts=int(c_data.get("attempts", len(c_data.get("history", [])))),
            last_submission_id=c_data.get("last_submission_id"),
            processed_submissions=c_data.get("processed_submissions", []),
            consecutive_easy_failures=c_data.get("consecutive_easy_failures", 0)
        )

    score_updates = []
    total_observations = 0

    for doc in scores:
        concept = doc["concept"]
        doc_id = doc["_id"]
        mcqs = doc["mcq_scores"]
        diff = doc.get("difficulty", "medium")
        timestamp = doc["timestamp"]

        # Deterministic token derived from immutable document _id
        sub_id = f"sub_legacy_{TARGET_STUDENT_ID.lower()}_{str(doc_id)}"

        c_curr = tracker.state.get(concept, {})
        processed_subs = c_curr.get("processed_submissions", [])
        history = c_curr.get("history", [])

        already_applied = (
            sub_id in processed_subs or
            any(h.get("submission_id") == sub_id for h in history)
        )

        print(f"\n--- Reconciling Score Doc [{doc_id}] ({concept}) ---")
        print(f"    Deterministic Token: {sub_id}")
        print(f"    Original Timestamp:  {timestamp}")
        print(f"    Already Applied:     {already_applied}")

        applied_in_doc = 0
        if not already_applied:
            print("    Applying MCQ Transitions sequentially:")
            for obs_idx, score_val in enumerate(mcqs):
                prev_m = tracker.state[concept]["mastery"]
                prev_u = tracker.state[concept]["uncertainty"]

                tracker.update_state(
                    concept_name_or_id=concept,
                    evidence_score=float(score_val),
                    activity_type=0,
                    difficulty=diff
                )
                new_m = tracker.state[concept]["mastery"]
                new_u = tracker.state[concept]["uncertainty"]
                att = tracker.state[concept]["attempts"]

                # Tag submission token on newly appended history entry
                if tracker.state[concept].get("history"):
                    tracker.state[concept]["history"][-1]["submission_id"] = sub_id
                    tracker.state[concept]["history"][-1]["timestamp"] = timestamp

                print(f"      Step {obs_idx + 1} (e={score_val}): mastery {prev_m:.4f} -> {new_m:.4f}, uncertainty {prev_u:.7f} -> {new_u:.7f} (attempts={att})")
                applied_in_doc += 1
                total_observations += 1

            # Update concept tokens
            tracker.state[concept]["last_submission_id"] = sub_id
            if "processed_submissions" not in tracker.state[concept]:
                tracker.state[concept]["processed_submissions"] = []
            if sub_id not in tracker.state[concept]["processed_submissions"]:
                tracker.state[concept]["processed_submissions"].append(sub_id)

        final_m = tracker.state[concept]["mastery"]
        final_u = tracker.state[concept]["uncertainty"]
        final_att = tracker.state[concept]["attempts"]
        print(f"    Final Concept State: mastery={final_m:.4f}, uncertainty={final_u:.7f}, attempts={final_att}")

        # Assert target values
        exp = TARGET_VALUES[concept]
        if abs(final_m - exp["mastery"]) > 1e-4:
            sys.exit(f"ABORT: Calculated mastery {final_m} does not match expected {exp['mastery']}.")
        if abs(final_u - exp["uncertainty"]) > 1e-4:
            sys.exit(f"ABORT: Calculated uncertainty {final_u} does not match expected {exp['uncertainty']}.")
        if final_att != exp["attempts"]:
            sys.exit(f"ABORT: Calculated attempts {final_att} does not match expected {exp['attempts']}.")

        score_updates.append({
            "_id": doc_id,
            "submission_id": sub_id,
            "applied_count": applied_in_doc
        })

    # Verify other 8 concepts were untouched
    for c in OTHER_8_CONCEPTS:
        if tracker.state[c]["mastery"] != 0.30 or tracker.state[c]["uncertainty"] != 0.50 or tracker.state[c]["attempts"] != 0:
            sys.exit(f"ABORT: Invariance violated for concept '{c}'.")

    if dry_run:
        print("\n[+] DRY-RUN SUCCESSFUL: All calculations verified against target criteria.")
        print(f"[+] Total MCQ observations to apply: {total_observations}")
        print("[+] ZERO database writes were performed.")
        return

    # LIVE EXECUTION (--apply)
    print("\n>>> EXECUTING DURABLE REPLAY WRITES TO akt_tutor_test <<<")
    now_iso = datetime.now(timezone.utc).isoformat()
    new_knowledge_state = tracker.get_knowledge_state()

    # Step 1: Persist canonical student_states
    current_ver = state_doc.get("version", 1) if state_doc.get("version") is not None else 1
    state_payload = {
        "student_id": TARGET_STUDENT_ID,
        "knowledge_state": new_knowledge_state,
        "version": current_ver + 1,
        "updated_at": now_iso
    }

    res_state = db["student_states"].update_one(
        {"student_id": TARGET_STUDENT_ID},
        {"$set": state_payload}
    )
    if res_state.matched_count != 1:
        sys.exit("FATAL: Failed to update canonical student_states document!")
    print(f"[+] Updated student_states for {TARGET_STUDENT_ID} (version: {current_ver + 1})")

    # Step 2: In-place update score documents in scores collection
    for item in score_updates:
        doc_id = item["_id"]
        sub_id = item["submission_id"]
        applied = item["applied_count"]

        res_score = db["scores"].update_one(
            {"_id": doc_id, "student_id": TARGET_STUDENT_ID},
            {"$set": {
                "submission_id": sub_id,
                "bkt_processed": True,
                "bkt_processed_at": now_iso,
                "bkt_observations_applied": applied
            }}
        )
        if res_score.matched_count != 1:
            sys.exit(f"FATAL: In-place score update failed for document {doc_id}!")
        print(f"[+] Updated score document [{doc_id}] in-place: submission_id='{sub_id}', bkt_processed=True")

    # Step 3: Update secondary projection users.mastery_state
    res_user = db["users"].update_one(
        {"student_id": TARGET_STUDENT_ID},
        {"$set": {
            "mastery_state": new_knowledge_state,
            "updated_at": now_iso
        }}
    )
    print(f"[+] Synchronized secondary projection in users collection (matched: {res_user.matched_count})")

    print("\n[+] REPLAY COMMITTED SUCCESSFULLY.")


def verify_post_replay_state(db):
    """Performs thorough post-replay verification directly against MongoDB."""
    print("\n" + "=" * 70)
    print("3. VERIFYING POST-REPLAY STATE IN akt_tutor_test")
    print("=" * 70)

    # 1. Verify score count remains exactly 2 (zero duplicate documents)
    score_count = db["scores"].count_documents({"student_id": TARGET_STUDENT_ID})
    print(f"[*] Post-replay S009 score document count: {score_count} (Expected: 2)")
    assert score_count == 2, f"Expected 2 score documents, found {score_count}!"

    scores = list(db["scores"].find({"student_id": TARGET_STUDENT_ID}).sort("timestamp", 1))
    for doc in scores:
        concept = doc["concept"]
        doc_id = doc["_id"]
        sub_id = doc.get("submission_id")
        bkt_proc = doc.get("bkt_processed")
        applied = doc.get("bkt_observations_applied")

        expected_id = EXPECTED_DOC_IDS[concept]
        expected_sub_id = f"sub_legacy_{TARGET_STUDENT_ID.lower()}_{str(expected_id)}"

        print(f"[*] Score Doc [{doc_id}] ({concept}):")
        print(f"    - submission_id: {sub_id} (Expected: {expected_sub_id})")
        print(f"    - bkt_processed: {bkt_proc} (Expected: True)")
        print(f"    - bkt_observations_applied: {applied} (Expected: 3)")

        assert doc_id == expected_id
        assert sub_id == expected_sub_id
        assert bkt_proc is True
        assert applied == 3

    # 2. Verify student_states final values
    state_doc = db["student_states"].find_one({"student_id": TARGET_STUDENT_ID})
    assert state_doc is not None
    ks = state_doc["knowledge_state"]

    print("\n[*] Verifying Concept Knowledge States in student_states:")
    for concept in ["Exception Handling", "Loops"]:
        c = ks[concept]
        exp = TARGET_VALUES[concept]
        print(f"    - {concept}: mastery={c['mastery']}, uncertainty={c['uncertainty']}, attempts={c['attempts']}")
        assert abs(c["mastery"] - exp["mastery"]) < 1e-4
        assert abs(c["uncertainty"] - exp["uncertainty"]) < 1e-4
        assert c["attempts"] == exp["attempts"]
        assert len(c["history"]) == 3
        expected_sub = f"sub_legacy_{TARGET_STUDENT_ID.lower()}_{str(EXPECTED_DOC_IDS[concept])}"
        assert c["last_submission_id"] == expected_sub
        assert expected_sub in c["processed_submissions"]

    for concept in OTHER_8_CONCEPTS:
        c = ks[concept]
        assert c["mastery"] == 0.30
        assert c["uncertainty"] == 0.50
        assert c["attempts"] == 0
        assert len(c.get("history", [])) == 0

    print("\n[+] ALL POST-REPLAY ASSERTIONS VERIFIED!")


def main():
    parser = argparse.ArgumentParser(description="Controlled S009 Historical EMA Replay Utility")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Simulate replay without writing to database")
    group.add_argument("--apply", action="store_true", help="Execute durable in-place replay writes")

    args = parser.parse_args()

    verify_environment_gates()
    client, db = connect_and_verify_database()

    try:
        scores, state_doc = run_preflight_checks(db)
        simulate_or_execute_replay(db, scores, state_doc, dry_run=args.dry_run)
        if args.apply:
            verify_post_replay_state(db)
    finally:
        client.close()


if __name__ == "__main__":
    main()

