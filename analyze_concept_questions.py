"""
analyze_concept_questions.py

Script to group processed data by concept_id and activity_type (modality),
and compute the exact number of unique questions (Problem IDs) for each concept.
"""

import os
import pandas as pd
import numpy as np
from src.data.preprocessor import UnifiedDataPreprocessor, create_sample_datasets, load_raw_file_in_chunks, DEFAULT_CONCEPT_MAP

ACTIVITY_NAME_MAP = {
    0: "MCQ",
    1: "Coding",
    2: "Short Answer"
}

def map_domain_category(concept_str: str) -> str:
    concept_lower = str(concept_str).lower()
    domain_keywords = {
        "Variables": ["variable", "var", "assign", "inttofloat", "caststring", "stockchange", "leftovercandy"],
        "Conditionals": ["conditional", "if", "candrinkalcohol", "haseven", "isprime", "iseven", "hastwo", "overnine", "carefulsquare"],
        "Loops": ["loop", "for", "while", "oneton", "sumofdigits", "reducetopositive", "createnumberblock"],
        "Functions": ["function", "def", "raisetopower", "converttodegrees", "findroot", "factorial", "fibonacci", "gcd"],
        "Arrays": ["array", "list", "middleelement", "secondhalf", "listoflists", "friendoffriends", "findthecircle"],
        "Strings": ["string", "char", "nearestbus", "backwardscombine", "firstandlast", "singlepiglatin", "issubstring", "hello", "doublex", "ispunctuation", "anylowercase", "treasurehunt", "mostanagrams"],
        "Syntax": ["syntax", "semicolon", "indentation", "howmanyeggcartons", "kthdigit"],
        "OOP": ["oop", "class", "object", "inheritance"]
    }
    for category, keywords in domain_keywords.items():
        if any(kw in concept_lower for kw in keywords):
            return category
    return "General / Assignment"

def analyze_concept_questions():
    print("=" * 75)
    print("        UNIQUE QUESTIONS (PROBLEM IDs) PER CONCEPT & MODALITY        ")
    print("=" * 75)

    raw_dir = "data/raw"
    os.makedirs(raw_dir, exist_ok=True)

    # Ensure sample datasets exist if raw folder is empty
    create_sample_datasets(raw_dir)

    raw_files = []
    for root, _, files in os.walk(raw_dir):
        for f in files:
            if f.endswith(".csv") or f.endswith(".txt"):
                raw_files.append(os.path.join(root, f))

    csedm_desktop_path = "/Users/abdulsamath/Desktop/adaptive-knowledge-tracing/data/raw/DataChallenge/MainTable.csv"
    if os.path.exists(csedm_desktop_path):
        raw_files.append(csedm_desktop_path)

    print(f"Ingesting {len(raw_files)} raw data source file(s)...\n")

    preprocessor = UnifiedDataPreprocessor()
    extracted_records = []

    for filepath in raw_files:
        try:
            filename = os.path.basename(filepath)
            df_raw = load_raw_file_in_chunks(filepath, chunksize=50_000, max_rows=100_000)
            if df_raw.empty:
                continue

            prob_col = None
            for col in ["ProblemID", "concept", "concept_name", "question_id", "skill_name", "problem_id", "AssignmentID", "CodeStateSection", "File"]:
                if col in df_raw.columns:
                    prob_col = col
                    break
            
            if not prob_col:
                continue

            df_std = preprocessor.standardize_raw_df(df_raw, dataset_source=filename)
            df_std["problem_id"] = df_raw[prob_col].astype(str).values
            extracted_records.append(df_std)
        except Exception as e:
            print(f"Skipped file {filepath} due to error: {e}")

    if not extracted_records:
        raise RuntimeError("No records could be extracted from datasets!")

    combined_df = pd.concat(extracted_records, ignore_index=True)

    combined_df["concept_name"] = combined_df["concept_id"].map(preprocessor.id_to_concept).fillna("Other / General")
    combined_df["modality"] = combined_df["activity_type"].map(ACTIVITY_NAME_MAP).fillna("Unknown")
    combined_df["domain_category"] = combined_df["concept_name"].apply(map_domain_category)

    # ---------------------------------------------------------
    # TABLE 1: Breakdown by Granular Concept ID & Concept Name
    # ---------------------------------------------------------
    summary_granular = (
        combined_df.groupby(["concept_id", "concept_name", "modality"])["problem_id"]
        .nunique()
        .reset_index()
        .rename(columns={"problem_id": "unique_questions"})
    )

    pivot_granular = summary_granular.pivot(
        index=["concept_id", "concept_name"],
        columns="modality",
        values="unique_questions"
    ).fillna(0).astype(int)

    for mod in ["MCQ", "Short Answer", "Coding"]:
        if mod not in pivot_granular.columns:
            pivot_granular[mod] = 0

    pivot_granular = pivot_granular[["MCQ", "Short Answer", "Coding"]]
    pivot_granular["Total Unique Questions"] = pivot_granular.sum(axis=1)
    pivot_granular = pivot_granular.reset_index().sort_values(by="concept_id").reset_index(drop=True)

    print("TABLE 1: Breakdown by Granular concept_id & concept_name")
    print("-" * 75)
    print(pivot_granular.to_string(index=False))
    print("\n" + "=" * 75 + "\n")

    # ---------------------------------------------------------
    # TABLE 2: Domain Concept Category Summary
    # ---------------------------------------------------------
    summary_domain = (
        combined_df.groupby(["domain_category", "modality"])["problem_id"]
        .nunique()
        .reset_index()
        .rename(columns={"problem_id": "unique_questions"})
    )

    pivot_domain = summary_domain.pivot(
        index="domain_category",
        columns="modality",
        values="unique_questions"
    ).fillna(0).astype(int)

    for mod in ["MCQ", "Short Answer", "Coding"]:
        if mod not in pivot_domain.columns:
            pivot_domain[mod] = 0

    pivot_domain = pivot_domain[["MCQ", "Short Answer", "Coding"]]
    pivot_domain["Total Unique Questions"] = pivot_domain.sum(axis=1)
    pivot_domain = pivot_domain.reset_index().sort_values(by="Total Unique Questions", ascending=False).reset_index(drop=True)

    print("TABLE 2: Summary by Domain Concept Category")
    print("-" * 75)
    print(pivot_domain.to_string(index=False))
    print("\n" + "=" * 75)

    # ---------------------------------------------------------
    # GRAND TOTALS SUMMARY
    # ---------------------------------------------------------
    total_mcq = combined_df[combined_df["activity_type"] == 0]["problem_id"].nunique()
    total_coding = combined_df[combined_df["activity_type"] == 1]["problem_id"].nunique()
    total_short = combined_df[combined_df["activity_type"] == 2]["problem_id"].nunique()
    total_unique = combined_df["problem_id"].nunique()

    print("TOTAL UNIQUE QUESTIONS SUMMARY:")
    print(f"  - MCQ Questions          : {total_mcq}")
    print(f"  - Short Answer Questions : {total_short}")
    print(f"  - Coding Tasks           : {total_coding}")
    print(f"  - Grand Total Unique     : {total_unique}")
    print("=" * 75)

    return pivot_granular, pivot_domain

if __name__ == "__main__":
    analyze_concept_questions()
