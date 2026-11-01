"""
src/data/preprocessor.py

Unified Data Preprocessor for Knowledge Tracing.
Handles raw log ingestion (CSEDM, Runestone, ASSISTments, custom schemas),
concept standardization, behavioral feature engineering, robust missing value handling,
student-level data splitting (preventing data leakage), and PyTorch Dataset creation.
"""

import os
import json
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader
from typing import Dict, List, Tuple, Optional, Union

# Concept mapping dictionary for Python domain standard concepts
DEFAULT_CONCEPT_MAP = {
    "Variables": 1,
    "Conditionals": 2,
    "Loops": 3,
    "Functions": 4,
    "Arrays": 5,
    "Syntax": 6,
    "OOP": 7,
    "Strings": 8,
    "Recursion": 9,
    "Unknown": 10
}

# Activity Type mapping: MCQ=0, Code=1, Text=2
ACTIVITY_TYPE_MAP = {
    "MCQ": 0,
    "mcq": 0,
    "multiple_choice": 0,
    "Code": 1,
    "code": 1,
    "programming": 1,
    "Submit": 1,
    "Text": 2,
    "text": 2,
    "short_answer": 2
}

class UnifiedDataPreprocessor:
    """
    Ingests raw interaction data from CSEDM, Runestone, or custom schemas
    and standardizes them into Unified Evidence Vectors.
    """
    def __init__(self, max_seq_len: int = 50):
        self.max_seq_len = max_seq_len
        self.concept_to_id: Dict[str, int] = dict(DEFAULT_CONCEPT_MAP)
        self.id_to_concept: Dict[int, str] = {v: k for k, v in self.concept_to_id.items()}
        self.next_concept_id = max(self.concept_to_id.values()) + 1 if self.concept_to_id else 1
        
        # Continuous feature normalization statistics
        self.time_mean: float = 0.0
        self.time_std: float = 1.0
        self.attempt_mean: float = 0.0
        self.attempt_std: float = 1.0

    def get_or_create_concept_id(self, concept_name: str) -> int:
        """Maps concept name string to a unique integer ID."""
        concept_str = str(concept_name).strip()
        if concept_str not in self.concept_to_id:
            self.concept_to_id[concept_str] = self.next_concept_id
            self.id_to_concept[self.next_concept_id] = concept_str
            self.next_concept_id += 1
        return self.concept_to_id[concept_str]

    def standardize_raw_df(self, df: pd.DataFrame, dataset_source: str = "auto") -> pd.DataFrame:
        """
        Ingests a DataFrame and converts columns to standard format:
        ['student_id', 'timestamp', 'concept_id', 'activity_type', 'evidence_score', 'response_time_sec', 'attempt_number']
        Handles missing columns, inconsistent types, and different schemas.
        """
        df = df.copy()

        # 1. Identify student ID column
        student_col = None
        for col in ["SubjectID", "student_id", "user_id", "Subject_Id", "Anon Student Id"]:
            if col in df.columns:
                student_col = col
                break
        if student_col is None:
            raise KeyError("Could not find a valid Student ID column in raw dataset.")
        df["student_id"] = df[student_col].astype(str)

        # 2. Identify Timestamp column & sort
        timestamp_col = None
        for col in ["ServerTimestamp", "timestamp", "created_at", "Timestamp", "Start Time", "ClientTimestamp"]:
            if col in df.columns:
                timestamp_col = col
                break
        
        if timestamp_col:
            if timestamp_col == "ClientTimestamp":
                # Epoch millisecond timestamps (e.g. 1636696834375)
                numeric_ts = pd.to_numeric(df[timestamp_col], errors="coerce")
                df["timestamp"] = pd.to_datetime(numeric_ts, unit="ms", errors="coerce")
            else:
                df["timestamp"] = pd.to_datetime(df[timestamp_col], errors="coerce")

            # Fill unparseable timestamps with fallback index
            if df["timestamp"].isnull().any():
                df["timestamp"] = df["timestamp"].fillna(method="ffill").fillna(pd.Timestamp("2026-01-01"))
        else:
            # Fallback: create artificial order index as timestamp
            df["timestamp"] = pd.date_range(start="2026-01-01", periods=len(df), freq="s")

        # 3. Sort strictly by student_id and timestamp to prevent temporal leakage
        df = df.sort_values(by=["student_id", "timestamp"]).reset_index(drop=True)

        # 4. Map Problem / Concept to Concept ID
        concept_col = None
        for col in ["ProblemID", "concept", "concept_name", "question_id", "skill_name", "problem_id", "AssignmentID", "CodeStateSection", "File"]:
            if col in df.columns:
                concept_col = col
                break
        
        if concept_col:
            # Handle empty/NA concept values robustly
            concept_series = df[concept_col].fillna("General_Task").astype(str)
            df["concept_id"] = concept_series.apply(self.get_or_create_concept_id)
        else:
            df["concept_id"] = self.get_or_create_concept_id("Unknown")

        # 5. Map Activity Type (MCQ=0, Code=1, Text=2)
        activity_col = None
        for col in ["EventType", "activity_type", "type", "problem_type", "action", "Action"]:
            if col in df.columns:
                activity_col = col
                break
        
        if activity_col:
            def map_act(val):
                val_str = str(val).lower()
                for key, code in ACTIVITY_TYPE_MAP.items():
                    if key.lower() in val_str:
                        return code
                return 1 if "submit" in val_str or "code" in val_str or "edit" in val_str or "run" in val_str or val_str == "r" else 0
            df["activity_type"] = df[activity_col].apply(map_act)
        else:
            # Infer activity type based on dataset source
            if "csedm" in dataset_source.lower() or "code" in dataset_source.lower():
                df["activity_type"] = 1
            else:
                df["activity_type"] = 0

        # 6. Map Evidence Score (0.0 to 1.0)
        score_col = None
        for col in ["Correct", "evidence_score", "score", "correctness", "is_correct", "X-Compilable"]:
            if col in df.columns:
                score_col = col
                break
        
        if score_col:
            # Convert boolean or float/int to float [0.0, 1.0]
            def parse_score(val):
                if pd.isna(val):
                    return 0.0
                if isinstance(val, bool):
                    return 1.0 if val else 0.0
                val_str = str(val).strip().upper()
                if val_str in ["TRUE", "T", "1", "1.0", "CORRECT"]:
                    return 1.0
                if val_str in ["FALSE", "F", "0", "0.0", "INCORRECT"]:
                    return 0.0
                try:
                    score_flt = float(val)
                    return float(np.clip(score_flt, 0.0, 1.0))
                except ValueError:
                    return 0.0
            df["evidence_score"] = df[score_col].apply(parse_score)
        else:
            df["evidence_score"] = 0.0

        # 7. Compute or extract Response Time in Seconds
        if "response_time_sec" in df.columns:
            df["response_time_sec"] = pd.to_numeric(df["response_time_sec"], errors="coerce").fillna(0.0)
        elif "time_taken" in df.columns:
            df["response_time_sec"] = pd.to_numeric(df["time_taken"], errors="coerce").fillna(0.0)
        else:
            # Estimate response time as time diff between consecutive student events (max 300s)
            df["time_diff"] = df.groupby("student_id")["timestamp"].diff().dt.total_seconds().fillna(10.0)
            df["response_time_sec"] = df["time_diff"].clip(lower=0.0, upper=300.0)
            df.drop(columns=["time_diff"], inplace=True)

        # 8. Compute Attempt Number per (student_id, concept_id)
        if "attempt_number" in df.columns:
            df["attempt_number"] = pd.to_numeric(df["attempt_number"], errors="coerce").fillna(1)
        else:
            df["attempt_number"] = df.groupby(["student_id", "concept_id"]).cumcount() + 1

        selected_cols = [
            "student_id", "timestamp", "concept_id", "activity_type", 
            "evidence_score", "response_time_sec", "attempt_number"
        ]
        return df[selected_cols]

    def fit_normalization(self, df: pd.DataFrame):
        """Fits normalization statistics on the training DataFrame."""
        self.time_mean = float(df["response_time_sec"].mean())
        self.time_std = float(df["response_time_sec"].std() + 1e-6)
        self.attempt_mean = float(df["attempt_number"].mean())
        self.attempt_std = float(df["attempt_number"].std() + 1e-6)

    def normalize_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalizes response time and attempt number continuous features."""
        df = df.copy()
        df["norm_response_time"] = (df["response_time_sec"] - self.time_mean) / self.time_std
        df["norm_attempt_number"] = (df["attempt_number"] - self.attempt_mean) / self.attempt_std
        return df

    def split_by_student(self, df: pd.DataFrame, train_ratio: float = 0.8, seed: int = 42) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Splits dataset into Train and Validation sets strictly at the STUDENT level.
        Prevents data leakage across dataset splits.
        """
        unique_students = df["student_id"].unique()
        np.random.seed(seed)
        np.random.shuffle(unique_students)
        
        n_train = int(len(unique_students) * train_ratio)
        train_students = set(unique_students[:n_train])
        val_students = set(unique_students[n_train:])
        
        train_df = df[df["student_id"].isin(train_students)].copy()
        val_df = df[df["student_id"].isin(val_students)].copy()
        
        return train_df, val_df

    def process_sequences(self, df: pd.DataFrame) -> List[Dict[str, np.ndarray]]:
        """
        Converts standardized DataFrame into windowed sequences per student.
        Returns a list of dictionary samples for KTDataset.
        """
        normalized_df = self.normalize_features(df)
        samples = []

        for student_id, group in normalized_df.groupby("student_id"):
            group = group.sort_values("timestamp")
            
            c_ids = group["concept_id"].values
            act_types = group["activity_type"].values
            scores = group["evidence_score"].values
            times = group["norm_response_time"].values
            attempts = group["norm_attempt_number"].values

            seq_len = len(c_ids)
            # Break long sequences into chunks of max_seq_len
            for i in range(0, seq_len, self.max_seq_len):
                chunk_c = c_ids[i:i + self.max_seq_len]
                chunk_act = act_types[i:i + self.max_seq_len]
                chunk_score = scores[i:i + self.max_seq_len]
                chunk_time = times[i:i + self.max_seq_len]
                chunk_attempt = attempts[i:i + self.max_seq_len]

                chunk_len = len(chunk_c)
                if chunk_len < 2:
                    continue  # Require at least 2 interactions for sequence prediction (t -> t+1)

                samples.append({
                    "student_id": student_id,
                    "seq_len": chunk_len,
                    "concept_ids": chunk_c,
                    "activity_types": chunk_act,
                    "scores": chunk_score,
                    "response_times": chunk_time,
                    "attempt_numbers": chunk_attempt,
                })
        return samples

class KTDataset(Dataset):
    """
    PyTorch Dataset for Attention-based Knowledge Tracing (AKT).
    Yields padded sequence tensors of fixed max_seq_len.
    """
    def __init__(self, samples: List[Dict[str, np.ndarray]], max_seq_len: int = 50):
        self.samples = samples
        self.max_seq_len = max_seq_len

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        sample = self.samples[idx]
        seq_len = sample["seq_len"]

        # Pad vectors to max_seq_len
        concept_ids = np.zeros(self.max_seq_len, dtype=np.int64)
        activity_types = np.zeros(self.max_seq_len, dtype=np.int64)
        scores = np.zeros(self.max_seq_len, dtype=np.float32)
        response_times = np.zeros(self.max_seq_len, dtype=np.float32)
        attempt_numbers = np.zeros(self.max_seq_len, dtype=np.float32)
        mask = np.zeros(self.max_seq_len, dtype=np.float32)

        concept_ids[:seq_len] = sample["concept_ids"]
        activity_types[:seq_len] = sample["activity_types"]
        scores[:seq_len] = sample["scores"]
        response_times[:seq_len] = sample["response_times"]
        attempt_numbers[:seq_len] = sample["attempt_numbers"]
        mask[:seq_len] = 1.0

        # Continuous features shape: (max_seq_len, 3) -> [score, response_time, attempt_number]
        continuous_features = np.stack([scores, response_times, attempt_numbers], axis=-1)

        # Targets for next-step prediction: shift by 1 timestep
        target_concepts = np.zeros(self.max_seq_len, dtype=np.int64)
        target_scores = np.zeros(self.max_seq_len, dtype=np.float32)
        target_mask = np.zeros(self.max_seq_len, dtype=np.float32)

        if seq_len > 1:
            target_concepts[:seq_len - 1] = sample["concept_ids"][1:seq_len]
            target_scores[:seq_len - 1] = sample["scores"][1:seq_len]
            target_mask[:seq_len - 1] = 1.0

        return {
            "concept_ids": torch.tensor(concept_ids, dtype=torch.long),
            "activity_types": torch.tensor(activity_types, dtype=torch.long),
            "continuous_features": torch.tensor(continuous_features, dtype=torch.float32),
            "target_concepts": torch.tensor(target_concepts, dtype=torch.long),
            "target_scores": torch.tensor(target_scores, dtype=torch.float32),
            "mask": torch.tensor(mask, dtype=torch.float32),
            "target_mask": torch.tensor(target_mask, dtype=torch.float32)
        }

def create_sample_datasets(raw_dir: str = "data/raw"):
    """
    Creates sample raw CSEDM (Code) and Runestone (MCQ) CSV files for demonstration 
    and immediate zero-friction execution if raw files are not present.
    """
    os.makedirs(raw_dir, exist_ok=True)
    csedm_path = os.path.join(raw_dir, "csedm_sample.csv")
    runestone_path = os.path.join(raw_dir, "runestone_sample.csv")

    if not os.path.exists(csedm_path):
        # Sample CSEDM Code interactions
        csedm_data = []
        students = [f"S{i:03d}" for i in range(1, 21)]
        problems = ["Variables_p1", "Conditionals_p1", "Loops_p1", "Functions_p1", "Arrays_p1"]
        
        for s in students:
            base_time = pd.Timestamp("2026-02-01 10:00:00")
            for step, p in enumerate(problems * 2):
                correct = np.random.choice([True, False], p=[0.7, 0.3])
                csedm_data.append({
                    "SubjectID": s,
                    "ServerTimestamp": base_time + pd.Timedelta(minutes=step * 5 + np.random.randint(1, 4)),
                    "ProblemID": p,
                    "EventType": "Submit",
                    "Correct": correct
                })
        pd.DataFrame(csedm_data).to_csv(csedm_path, index=False)
        print(f"Created sample CSEDM dataset at {csedm_path}")

    if not os.path.exists(runestone_path):
        # Sample Runestone MCQ interactions
        runestone_data = []
        students = [f"R{i:03d}" for i in range(1, 21)]
        questions = ["Variables_mcq1", "Conditionals_mcq1", "Loops_mcq1", "Syntax_mcq1"]
        
        for s in students:
            base_time = pd.Timestamp("2026-02-01 14:00:00")
            for step, q in enumerate(questions * 3):
                score = np.random.choice([1.0, 0.0], p=[0.75, 0.25])
                runestone_data.append({
                    "student_id": s,
                    "timestamp": base_time + pd.Timedelta(minutes=step * 2 + np.random.randint(1, 3)),
                    "concept": q,
                    "activity_type": "MCQ",
                    "evidence_score": score,
                    "response_time_sec": float(np.random.randint(10, 60)),
                    "attempt_number": np.random.randint(1, 3)
                })
        pd.DataFrame(runestone_data).to_csv(runestone_path, index=False)
        print(f"Created sample Runestone dataset at {runestone_path}")

def load_raw_file_in_chunks(filepath: str, chunksize: int = 50_000, max_rows: Optional[int] = 100_000) -> pd.DataFrame:
    """
    Safely loads large CSV files (e.g. 1GB+ csedm runs.csv files) using chunking to prevent memory crashes.
    If max_rows is specified, limits total rows read for safe memory footprint.
    """
    chunks = []
    total_rows = 0
    
    try:
        # Check column names in first few rows to select relevant columns only
        first_chunk = pd.read_csv(filepath, nrows=5)
        possible_cols = [
            "SubjectID", "student_id", "user_id", "ClientTimestamp", "ServerTimestamp", "timestamp",
            "AssignmentID", "CodeStateSection", "File", "ProblemID", "concept", "EventType", "Action",
            "Correct", "evidence_score", "X-Compilable"
        ]
        matching_cols = [c for c in possible_cols if c in first_chunk.columns]
        cols_to_use = matching_cols if len(matching_cols) >= 2 else None

        for chunk in pd.read_csv(filepath, chunksize=chunksize, usecols=cols_to_use, low_memory=False):
            chunks.append(chunk)
            total_rows += len(chunk)
            if max_rows and total_rows >= max_rows:
                break
    except Exception as e:
        print(f"Error loading {filepath} in chunks: {e}")
        return pd.DataFrame()

    if not chunks:
        return pd.DataFrame()
    return pd.concat(chunks, ignore_index=True)

if __name__ == "__main__":
    print("=" * 60)
    print("      Testing Unified Data Preprocessor      ")
    print("=" * 60)
    
    # 1. Create sample raw datasets
    create_sample_datasets("data/raw")
    
    # 2. Test reading and standardizing sample CSEDM file
    sample_csedm = "data/raw/csedm_sample.csv"
    if os.path.exists(sample_csedm):
        preprocessor = UnifiedDataPreprocessor(max_seq_len=50)
        raw_df = pd.read_csv(sample_csedm)
        std_df = preprocessor.standardize_raw_df(raw_df, dataset_source="csedm_sample")
        
        print(f"Sample Ingestion Successful!")
        print(f"  -> Total Raw Rows: {len(raw_df)}")
        print(f"  -> Standardized Vectors Shape: {std_df.shape}")
        print(f"  -> Columns: {list(std_df.columns)}")
        print(f"  -> Sample Student Head:\n{std_df.head(3)}")
        
        # 3. Test PyTorch Dataset generation
        preprocessor.fit_normalization(std_df)
        samples = preprocessor.process_sequences(std_df)
        dataset = KTDataset(samples, max_seq_len=50)
        loader = DataLoader(dataset, batch_size=4, shuffle=False)
        
        for batch in loader:
            print(f"\nPyTorch Batch Tensors Created:")
            print(f"  - concept_ids shape: {batch['concept_ids'].shape}")
            print(f"  - activity_types shape: {batch['activity_types'].shape}")
            print(f"  - continuous_features shape: {batch['continuous_features'].shape}")
            print(f"  - target_scores shape: {batch['target_scores'].shape}")
            break
    print("\nPreprocessor standalone test complete.")


