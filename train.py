"""
train.py

Training script for 50% Milestone Baseline AKT Model.
Ingests datasets (CSEDM, Runestone, or samples), standardizes vectors,
enforces student-level train/val splits to prevent data leakage, trains the baseline AKT PyTorch model,
and saves model weights and metadata for downstream visualization and Phase 2 adaptive engine.
"""

import os
import json
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import pandas as pd

from src.data.preprocessor import UnifiedDataPreprocessor, KTDataset, create_sample_datasets, load_raw_file_in_chunks
from src.models.akt import AKTBaseline, train_akt_epoch, evaluate_akt

def main():
    print("=" * 60)
    print("      AKT Baseline Model Training (50% Milestone)      ")
    print("=" * 60)

    # 1. Ensure sample/raw datasets exist
    data_raw_dir = "data/raw"
    data_proc_dir = "data/processed"
    os.makedirs(data_raw_dir, exist_ok=True)
    os.makedirs(data_proc_dir, exist_ok=True)

    create_sample_datasets(data_raw_dir)

    # 2. Look for available datasets recursively in data/raw
    raw_files = []
    for root, _, files in os.walk(data_raw_dir):
        for f in files:
            if f.endswith(".csv") or f.endswith(".txt"):
                raw_files.append(os.path.join(root, f))

    # Also check if CSEDM MainTable exists on Desktop
    csedm_desktop_path = "/Users/abdulsamath/Desktop/adaptive-knowledge-tracing/data/raw/DataChallenge/MainTable.csv"
    if os.path.exists(csedm_desktop_path):
        print(f"Found real CSEDM dataset at: {csedm_desktop_path}")
        raw_files.insert(0, csedm_desktop_path)

    print(f"Detected {len(raw_files)} dataset file(s) for ingestion.")

    # Initialize Preprocessor
    preprocessor = UnifiedDataPreprocessor(max_seq_len=50)

    dfs = []
    for filepath in raw_files:
        try:
            print(f"Ingesting raw file: {filepath}")
            # Use chunked loader for safe memory usage on 1GB+ runs files
            df_raw = load_raw_file_in_chunks(filepath, chunksize=50_000, max_rows=100_000)
            if df_raw.empty:
                print(f"  -> Empty or unparseable: {filepath}")
                continue

            df_std = preprocessor.standardize_raw_df(df_raw, dataset_source=os.path.basename(filepath))
            dfs.append(df_std)
            print(f"  -> Ingested {len(df_std)} interactions across {df_std['student_id'].nunique()} students.")
        except Exception as e:
            print(f"  -> Skipped {filepath} due to parsing error: {e}")

    if not dfs:
        raise RuntimeError("No valid dataset logs found!")

    combined_df = pd.concat(dfs, ignore_index=True)
    # Ensure chronological sorting per student
    combined_df = combined_df.sort_values(by=["student_id", "timestamp"]).reset_index(drop=True)
    print(f"\nTotal Unified Evidence Vectors: {len(combined_df)}")
    print(f"Total Unique Students: {combined_df['student_id'].nunique()}")
    print(f"Total Unique Concepts Mapped: {len(preprocessor.concept_to_id)}")

    # 3. Fit feature normalization statistics on training data
    preprocessor.fit_normalization(combined_df)

    # 4. Strict Student-Level Train / Val Split (Data Leakage Prevention)
    train_df, val_df = preprocessor.split_by_student(combined_df, train_ratio=0.8, seed=42)
    print(f"\nTrain set: {len(train_df)} interactions ({train_df['student_id'].nunique()} students)")
    print(f"Val set:   {len(val_df)} interactions ({val_df['student_id'].nunique()} students)")

    # 5. Process sequences and create PyTorch Datasets
    train_samples = preprocessor.process_sequences(train_df)
    val_samples = preprocessor.process_sequences(val_df)

    train_dataset = KTDataset(train_samples, max_seq_len=50)
    val_dataset = KTDataset(val_samples, max_seq_len=50)

    train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=16, shuffle=False)

    print(f"Created PyTorch DataLoaders (Train sequences: {len(train_samples)}, Val sequences: {len(val_samples)})")

    # 6. Instantiate Baseline AKT Model
    device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Using device: {device}")

    num_concepts = preprocessor.next_concept_id
    model = AKTBaseline(
        num_concepts=num_concepts,
        num_activities=3,
        num_continuous_features=3,
        embed_dim=64,
        nhead=4,
        num_layers=2,
        dim_feedforward=128,
        dropout=0.1,
        max_seq_len=50
    ).to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
    criterion = nn.BCELoss()

    # 7. Training Loop
    epochs = 10
    print("\nStarting Training Loop...")
    best_val_loss = float("inf")

    for epoch in range(1, epochs + 1):
        train_loss = train_akt_epoch(model, train_loader, optimizer, criterion, device)
        val_loss, val_acc = evaluate_akt(model, val_loader, criterion, device)

        print(f"Epoch {epoch:02d}/{epochs:02d} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val Acc: {val_acc * 100:.2f}%")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            # Save checkpoint
            model_save_path = os.path.join(data_proc_dir, "akt_baseline.pt")
            torch.save(model.state_dict(), model_save_path)

    print(f"\nTraining completed! Best Validation Loss: {best_val_loss:.4f}")
    
    # 8. Save Metadata & Concept Mapping
    meta_save_path = os.path.join(data_proc_dir, "akt_metadata.json")
    metadata = {
        "concept_to_id": preprocessor.concept_to_id,
        "id_to_concept": {str(k): v for k, v in preprocessor.id_to_concept.items()},
        "next_concept_id": preprocessor.next_concept_id,
        "time_mean": preprocessor.time_mean,
        "time_std": preprocessor.time_std,
        "attempt_mean": preprocessor.attempt_mean,
        "attempt_std": preprocessor.attempt_std,
        "num_concepts": num_concepts,
        "embed_dim": 64
    }
    with open(meta_save_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved model checkpoint to {data_proc_dir}/akt_baseline.pt")
    print(f"Saved preprocessor metadata to {meta_save_path}")

if __name__ == "__main__":
    main()
