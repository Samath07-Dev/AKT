"""
run_presentation_experiments.py

Executes model training and evaluation across DKT, AKT, and Behavior-AKT on the dataset,
computes evaluation metrics (AUC, Accuracy, F1, RMSE, MAE, Mean sigma),
and conducts ablation tests on Behavior-AKT to generate Presentation-3 slide tables.
"""

import os
import json
import random
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from sklearn.metrics import roc_auc_score, accuracy_score, f1_score, mean_squared_error, mean_absolute_error

from src.data.preprocessor import UnifiedDataPreprocessor, KTDataset, create_sample_datasets, load_raw_file_in_chunks
from src.models import DKTBaseline, AKTBaseline, BehaviorAKT
from src.models.dkt import train_dkt_epoch
from src.models.akt import train_akt_epoch
from src.models.behavior_akt import train_behavior_akt_epoch

# Set seeds for reproducibility
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(SEED)

def compute_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> dict:
    """Computes exact AUC, Accuracy, F1, RMSE, and MAE given ground truth and predicted probabilities."""
    binary_pred = (y_prob >= 0.5).astype(int)
    binary_true = (y_true >= 0.5).astype(int)
    
    # Handle edge case where y_true has only one class
    if len(np.unique(binary_true)) < 2:
        auc = 0.5
    else:
        auc = float(roc_auc_score(binary_true, y_prob))
        
    acc = float(accuracy_score(binary_true, binary_pred))
    f1 = float(f1_score(binary_true, binary_pred, zero_division=0))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_prob)))
    mae = float(mean_absolute_error(y_true, y_prob))
    
    return {
        "AUC": auc,
        "Accuracy": acc,
        "F1": f1,
        "RMSE": rmse,
        "MAE": mae
    }

def main():
    print("=" * 70)
    print("   Running Model Training & Evaluation for Presentation-3 Metrics   ")
    print("=" * 70)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Executing on hardware device: {device}")
    
    # 1. Dataset Ingestion
    data_raw_dir = "data/raw"
    create_sample_datasets(data_raw_dir)
    
    raw_files = []
    # Add Desktop CSEDM MainTable if available
    csedm_desktop_path = "/Users/abdulsamath/Desktop/adaptive-knowledge-tracing/data/raw/DataChallenge/MainTable.csv"
    if os.path.exists(csedm_desktop_path):
        raw_files.append(csedm_desktop_path)
        
    for root, _, files in os.walk(data_raw_dir):
        for f in files:
            if f.endswith(".csv"):
                raw_files.append(os.path.join(root, f))
                
    # Deduplicate while preserving order
    seen = set()
    dedup_files = []
    for f in raw_files:
        norm = os.path.abspath(f)
        if norm not in seen:
            seen.add(norm)
            dedup_files.append(f)
    raw_files = dedup_files
    
    print(f"Found {len(raw_files)} dataset source files.")
    
    preprocessor = UnifiedDataPreprocessor(max_seq_len=50)
    dfs = []
    for filepath in raw_files:
        try:
            base = os.path.basename(filepath)
            # Limit very large files to 15,000 rows for balanced representation & speed
            max_r = 15000 if ("runs" in base or "keystrokes" in base) else 50000
            df_raw = load_raw_file_in_chunks(filepath, chunksize=25000, max_rows=max_r)
            if not df_raw.empty:
                df_std = preprocessor.standardize_raw_df(df_raw, dataset_source=base)
                dfs.append(df_std)
                print(f"  ✓ {base}: Ingested {len(df_std)} rows ({df_std['student_id'].nunique()} students)")
        except Exception as e:
            print(f"  ⚠ Skipped {filepath}: {e}")
            
    combined_df = pd.concat(dfs, ignore_index=True)
    combined_df = combined_df.sort_values(by=["student_id", "timestamp"]).reset_index(drop=True)
    print(f"\nTotal Unified Interactions: {len(combined_df)}")
    print(f"Total Unique Students: {combined_df['student_id'].nunique()}")
    print(f"Total Unique Concepts Mapped: {len(preprocessor.concept_to_id)}")
    
    # 2. Student-level Train/Val Split
    preprocessor.fit_normalization(combined_df)
    train_df, val_df = preprocessor.split_by_student(combined_df, train_ratio=0.8, seed=SEED)
    print(f"Train set: {len(train_df)} interactions ({train_df['student_id'].nunique()} students)")
    print(f"Val set:   {len(val_df)} interactions ({val_df['student_id'].nunique()} students)")
    
    train_samples = preprocessor.process_sequences(train_df)
    val_samples = preprocessor.process_sequences(val_df)
    
    train_dataset = KTDataset(train_samples, max_seq_len=50)
    val_dataset = KTDataset(val_samples, max_seq_len=50)
    
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)
    
    num_concepts = preprocessor.next_concept_id
    criterion = nn.BCELoss()
    EPOCHS = 10
    
    # -------------------------------------------------------------
    # 1. Train and Evaluate DKT Baseline
    # -------------------------------------------------------------
    print("\n" + "=" * 50)
    print("1. Training DKT Baseline Model...")
    print("=" * 50)
    dkt_model = DKTBaseline(
        num_concepts=num_concepts,
        num_continuous_features=3,
        embed_dim=64,
        hidden_dim=128,
        num_layers=1,
        dropout=0.1
    ).to(device)
    dkt_opt = torch.optim.Adam(dkt_model.parameters(), lr=1e-3, weight_decay=1e-5)
    
    for epoch in range(1, EPOCHS + 1):
        loss = train_dkt_epoch(dkt_model, train_loader, dkt_opt, criterion, device)
        if epoch % 5 == 0 or epoch == EPOCHS:
            print(f"  DKT Epoch {epoch:02d}/{EPOCHS:02d} - Train Loss: {loss:.4f}")
            
    # Evaluate DKT on Validation Set
    dkt_model.eval()
    dkt_all_preds, dkt_all_targets = [], []
    with torch.no_grad():
        for batch in val_loader:
            concept_ids = batch["concept_ids"].to(device)
            continuous_features = batch["continuous_features"].to(device)
            target_concepts = batch["target_concepts"].to(device)
            target_scores = batch["target_scores"].to(device)
            target_mask = batch["target_mask"].to(device)
            
            preds = dkt_model(
                concept_ids=concept_ids,
                continuous_features=continuous_features,
                target_concept_ids=target_concepts,
                padding_mask=batch["mask"].to(device)
            )
            val_idx = (target_mask > 0)
            if val_idx.sum() > 0:
                dkt_all_preds.extend(preds[val_idx].cpu().numpy().tolist())
                dkt_all_targets.extend(target_scores[val_idx].cpu().numpy().tolist())
                
    dkt_metrics = compute_metrics(np.array(dkt_all_targets), np.array(dkt_all_preds))
    print(f"  ✓ DKT Val Results: AUC={dkt_metrics['AUC']:.4f}, Acc={dkt_metrics['Accuracy']*100:.2f}%, F1={dkt_metrics['F1']:.4f}, RMSE={dkt_metrics['RMSE']:.4f}, MAE={dkt_metrics['MAE']:.4f}")
    
    # -------------------------------------------------------------
    # 2. Train and Evaluate AKT Baseline
    # -------------------------------------------------------------
    print("\n" + "=" * 50)
    print("2. Training AKT Baseline Model...")
    print("=" * 50)
    akt_model = AKTBaseline(
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
    akt_opt = torch.optim.Adam(akt_model.parameters(), lr=1e-3, weight_decay=1e-5)
    
    for epoch in range(1, EPOCHS + 1):
        loss = train_akt_epoch(akt_model, train_loader, akt_opt, criterion, device)
        if epoch % 5 == 0 or epoch == EPOCHS:
            print(f"  AKT Epoch {epoch:02d}/{EPOCHS:02d} - Train Loss: {loss:.4f}")
            
    # Evaluate AKT on Validation Set
    akt_model.eval()
    akt_all_preds, akt_all_targets = [], []
    with torch.no_grad():
        for batch in val_loader:
            concept_ids = batch["concept_ids"].to(device)
            activity_types = batch["activity_types"].to(device)
            continuous_features = batch["continuous_features"].to(device)
            target_concepts = batch["target_concepts"].to(device)
            target_scores = batch["target_scores"].to(device)
            target_mask = batch["target_mask"].to(device)
            
            preds = akt_model(
                concept_ids=concept_ids,
                activity_types=activity_types,
                continuous_features=continuous_features,
                target_concept_ids=target_concepts,
                padding_mask=batch["mask"].to(device)
            )
            val_idx = (target_mask > 0)
            if val_idx.sum() > 0:
                akt_all_preds.extend(preds[val_idx].cpu().numpy().tolist())
                akt_all_targets.extend(target_scores[val_idx].cpu().numpy().tolist())
                
    akt_metrics = compute_metrics(np.array(akt_all_targets), np.array(akt_all_preds))
    print(f"  ✓ AKT Val Results: AUC={akt_metrics['AUC']:.4f}, Acc={akt_metrics['Accuracy']*100:.2f}%, F1={akt_metrics['F1']:.4f}, RMSE={akt_metrics['RMSE']:.4f}, MAE={akt_metrics['MAE']:.4f}")
    
    # -------------------------------------------------------------
    # 3. Train and Evaluate Behavior-AKT Model
    # -------------------------------------------------------------
    print("\n" + "=" * 50)
    print("3. Training Behavior-AKT Model (with MC Dropout)...")
    print("=" * 50)
    behavior_model = BehaviorAKT(
        num_concepts=num_concepts,
        num_activities=3,
        num_continuous_features=3,
        embed_dim=64,
        nhead=4,
        num_layers=2,
        dim_feedforward=128,
        dropout=0.2,
        max_seq_len=50
    ).to(device)
    behavior_opt = torch.optim.Adam(behavior_model.parameters(), lr=1e-3, weight_decay=1e-5)
    
    for epoch in range(1, EPOCHS + 1):
        loss = train_behavior_akt_epoch(behavior_model, train_loader, behavior_opt, criterion, device)
        if epoch % 5 == 0 or epoch == EPOCHS:
            print(f"  Behavior-AKT Epoch {epoch:02d}/{EPOCHS:02d} - Train Loss: {loss:.4f}")
            
    # Evaluate Behavior-AKT with MC Dropout (N=20 samples)
    behavior_all_preds, behavior_all_targets, behavior_all_sigmas = [], [], []
    with torch.no_grad():
        for batch in val_loader:
            concept_ids = batch["concept_ids"].to(device)
            activity_types = batch["activity_types"].to(device)
            continuous_features = batch["continuous_features"].to(device)
            target_concepts = batch["target_concepts"].to(device)
            target_scores = batch["target_scores"].to(device)
            target_mask = batch["target_mask"].to(device)
            
            unc_res = behavior_model.predict_with_uncertainty(
                concept_ids=concept_ids,
                activity_types=activity_types,
                continuous_features=continuous_features,
                target_concept_ids=target_concepts,
                padding_mask=batch["mask"].to(device),
                num_samples=20
            )
            val_idx = (target_mask > 0)
            if val_idx.sum() > 0:
                mean_m = unc_res["mean_mastery"][val_idx].cpu().numpy().tolist()
                tot_sig = unc_res["total_uncertainty"][val_idx].cpu().numpy().tolist()
                tgts = target_scores[val_idx].cpu().numpy().tolist()
                
                behavior_all_preds.extend(mean_m)
                behavior_all_sigmas.extend(tot_sig)
                behavior_all_targets.extend(tgts)
                
    behavior_metrics = compute_metrics(np.array(behavior_all_targets), np.array(behavior_all_preds))
    mean_sigma = float(np.mean(behavior_all_sigmas))
    print(f"  ✓ Behavior-AKT Val Results: AUC={behavior_metrics['AUC']:.4f}, Acc={behavior_metrics['Accuracy']*100:.2f}%, F1={behavior_metrics['F1']:.4f}, RMSE={behavior_metrics['RMSE']:.4f}, MAE={behavior_metrics['MAE']:.4f}, Mean σ={mean_sigma:.4f}")
    
    # -------------------------------------------------------------
    # 4. Ablation Suite on Behavior-AKT
    # -------------------------------------------------------------
    print("\n" + "=" * 50)
    print("4. Running Ablation Study on Behavior-AKT...")
    print("=" * 50)
    
    # Baseline Full Behavior-AKT
    full_auc = behavior_metrics["AUC"]
    full_rmse = behavior_metrics["RMSE"]
    
    # Ablation 1: w/o Behavior Features (zero out response_times and attempt_numbers)
    abl1_preds, abl1_targets = [], []
    with torch.no_grad():
        for batch in val_loader:
            concept_ids = batch["concept_ids"].to(device)
            activity_types = batch["activity_types"].to(device)
            continuous_features = batch["continuous_features"].clone().to(device)
            # Zero out response time (idx 1) and attempt count (idx 2), keeping only evidence score (idx 0)
            continuous_features[:, :, 1:] = 0.0
            
            target_concepts = batch["target_concepts"].to(device)
            target_scores = batch["target_scores"].to(device)
            target_mask = batch["target_mask"].to(device)
            
            unc_res = behavior_model.predict_with_uncertainty(
                concept_ids=concept_ids,
                activity_types=activity_types,
                continuous_features=continuous_features,
                target_concept_ids=target_concepts,
                padding_mask=batch["mask"].to(device),
                num_samples=20
            )
            val_idx = (target_mask > 0)
            if val_idx.sum() > 0:
                abl1_preds.extend(unc_res["mean_mastery"][val_idx].cpu().numpy().tolist())
                abl1_targets.extend(target_scores[val_idx].cpu().numpy().tolist())
    abl1_metrics = compute_metrics(np.array(abl1_targets), np.array(abl1_preds))
    print(f"  - Ablation 1 (w/o Behavior features): AUC={abl1_metrics['AUC']:.4f}, RMSE={abl1_metrics['RMSE']:.4f}")
    
    # Ablation 2: w/o SBERT / Code Evidence (binarize evidence score, neutralize activity embeddings)
    abl2_preds, abl2_targets = [], []
    with torch.no_grad():
        for batch in val_loader:
            concept_ids = batch["concept_ids"].to(device)
            # Neutralize activity types to single default modality (0 = MCQ)
            activity_types = torch.zeros_like(batch["activity_types"]).to(device)
            continuous_features = batch["continuous_features"].clone().to(device)
            # Coarsely binarize evidence score into {0.0, 1.0}
            continuous_features[:, :, 0] = (continuous_features[:, :, 0] >= 0.5).float()
            
            target_concepts = batch["target_concepts"].to(device)
            target_scores = batch["target_scores"].to(device)
            target_mask = batch["target_mask"].to(device)
            
            unc_res = behavior_model.predict_with_uncertainty(
                concept_ids=concept_ids,
                activity_types=activity_types,
                continuous_features=continuous_features,
                target_concept_ids=target_concepts,
                padding_mask=batch["mask"].to(device),
                num_samples=20
            )
            val_idx = (target_mask > 0)
            if val_idx.sum() > 0:
                abl2_preds.extend(unc_res["mean_mastery"][val_idx].cpu().numpy().tolist())
                abl2_targets.extend(target_scores[val_idx].cpu().numpy().tolist())
    abl2_metrics = compute_metrics(np.array(abl2_targets), np.array(abl2_preds))
    print(f"  - Ablation 2 (w/o SBERT/Code evidence): AUC={abl2_metrics['AUC']:.4f}, RMSE={abl2_metrics['RMSE']:.4f}")
    
    # Ablation 3: w/o MC Dropout (Deterministic single forward pass with eval mode)
    abl3_preds, abl3_targets = [], []
    behavior_model.eval()
    with torch.no_grad():
        for batch in val_loader:
            concept_ids = batch["concept_ids"].to(device)
            activity_types = batch["activity_types"].to(device)
            continuous_features = batch["continuous_features"].to(device)
            target_concepts = batch["target_concepts"].to(device)
            target_scores = batch["target_scores"].to(device)
            target_mask = batch["target_mask"].to(device)
            
            preds = behavior_model(
                concept_ids=concept_ids,
                activity_types=activity_types,
                continuous_features=continuous_features,
                target_concept_ids=target_concepts,
                padding_mask=batch["mask"].to(device)
            )
            val_idx = (target_mask > 0)
            if val_idx.sum() > 0:
                abl3_preds.extend(preds[val_idx].cpu().numpy().tolist())
                abl3_targets.extend(target_scores[val_idx].cpu().numpy().tolist())
    abl3_metrics = compute_metrics(np.array(abl3_targets), np.array(abl3_preds))
    print(f"  - Ablation 3 (w/o MC Dropout): AUC={abl3_metrics['AUC']:.4f}, RMSE={abl3_metrics['RMSE']:.4f}")
    
    # -------------------------------------------------------------
    # 5. Output Final Presentation Tables
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("                     PRESENTATION-3 SLIDE TABLES                    ")
    print("=" * 70)
    
    print("\n### Table 1: Model Comparative Testing Performance\n")
    print("| Model | AUC | Accuracy | F1-Score | RMSE | MAE | Mean $\\sigma$ (Uncertainty) |")
    print("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
    print(f"| **DKT (Baseline)** | {dkt_metrics['AUC']:.4f} | {dkt_metrics['Accuracy']*100:.2f}% | {dkt_metrics['F1']:.4f} | {dkt_metrics['RMSE']:.4f} | {dkt_metrics['MAE']:.4f} | — |")
    print(f"| **AKT (Baseline)** | {akt_metrics['AUC']:.4f} | {akt_metrics['Accuracy']*100:.2f}% | {akt_metrics['F1']:.4f} | {akt_metrics['RMSE']:.4f} | {akt_metrics['MAE']:.4f} | — |")
    print(f"| **Behavior-AKT (Proposed)** | **{behavior_metrics['AUC']:.4f}** | **{behavior_metrics['Accuracy']*100:.2f}%** | **{behavior_metrics['F1']:.4f}** | **{behavior_metrics['RMSE']:.4f}** | **{behavior_metrics['MAE']:.4f}** | **{mean_sigma:.4f}** |")
    
    print("\n### Table 2: Ablation Study on Behavior-AKT\n")
    print("| Model Architecture / Ablation Variant | AUC | RMSE | $\\Delta$ AUC | $\\Delta$ RMSE |")
    print("| :--- | :---: | :---: | :---: | :---: |")
    print(f"| **Behavior-AKT (Full Model)** | **{full_auc:.4f}** | **{full_rmse:.4f}** | Baseline | Baseline |")
    print(f"| w/o Behavior Features (No Time & Attempts) | {abl1_metrics['AUC']:.4f} | {abl1_metrics['RMSE']:.4f} | {abl1_metrics['AUC'] - full_auc:+.4f} | {abl1_metrics['RMSE'] - full_rmse:+.4f} |")
    print(f"| w/o SBERT & Code Evidence (Binarized Scoring) | {abl2_metrics['AUC']:.4f} | {abl2_metrics['RMSE']:.4f} | {abl2_metrics['AUC'] - full_auc:+.4f} | {abl2_metrics['RMSE'] - full_rmse:+.4f} |")
    print(f"| w/o MC Dropout (Deterministic Inference) | {abl3_metrics['AUC']:.4f} | {abl3_metrics['RMSE']:.4f} | {abl3_metrics['AUC'] - full_auc:+.4f} | {abl3_metrics['RMSE'] - full_rmse:+.4f} |")
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()

