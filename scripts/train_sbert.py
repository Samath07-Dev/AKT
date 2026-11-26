"""
scripts/train_sbert.py

Fine-tunes sentence-transformers/all-MiniLM-L6-v2 on domain-specific programming
concept explanation pairs with Cosine Similarity loss to suppress misconceptions (hard negatives)
while preserving high similarity for semantically correct paraphrases.
"""

import os
import json
import random
import torch
from pathlib import Path
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import batch_to_device


def train_sbert(
    train_data_path: str = "data/sbert_train_dataset.json",
    output_dir: str = "models/sbert_programming_minilm",
    base_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    epochs: int = 4,
    batch_size: int = 16,
    learning_rate: float = 2e-5,
    seed: int = 42
):
    random.seed(seed)
    torch.manual_seed(seed)

    print(f"Loading training data from {train_data_path}...")
    with open(train_data_path, "r", encoding="utf-8") as f:
        train_pairs: List[Dict[str, Any]] = json.load(f)

    print(f"Loaded {len(train_pairs)} training examples.")

    device = torch.device("mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu"))
    print(f"Initializing base model '{base_model_name}' on device: {device}...")
    model = SentenceTransformer(base_model_name, device=str(device))

    # Optimizer & Scheduler
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=0.01)
    num_steps = (len(train_pairs) // batch_size + (1 if len(train_pairs) % batch_size != 0 else 0)) * epochs
    warmup_steps = int(num_steps * 0.1)

    print(f"Starting fine-tuning: {epochs} epochs, {num_steps} total steps, warmup: {warmup_steps} steps...")
    model.train()

    global_step = 0
    for epoch in range(1, epochs + 1):
        random.shuffle(train_pairs)
        epoch_loss = 0.0
        batches = 0

        for i in range(0, len(train_pairs), batch_size):
            batch = train_pairs[i:i + batch_size]
            if not batch:
                continue

            text_a = [item["student_text"] for item in batch]
            text_b = [item["reference_answer"] for item in batch]
            labels = torch.tensor([float(item["label"]) for item in batch], dtype=torch.float32, device=device)

            # Preprocess / Tokenize
            tok_a = batch_to_device(model.tokenize(text_a), device)
            tok_b = batch_to_device(model.tokenize(text_b), device)

            # Forward
            optimizer.zero_grad()
            emb_a = model(tok_a)["sentence_embedding"]
            emb_b = model(tok_b)["sentence_embedding"]

            # Cosine similarity bounded in [-1, 1], normalized loss against [0, 1] label
            cos_sim = torch.nn.functional.cosine_similarity(emb_a, emb_b)
            # Clip cosine similarity for loss target to non-negative domain
            sim_score = torch.clamp(cos_sim, 0.0, 1.0)

            loss = torch.nn.functional.mse_loss(sim_score, labels)
            loss.backward()

            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            epoch_loss += loss.item()
            batches += 1
            global_step += 1

        avg_loss = epoch_loss / max(batches, 1)
        print(f"  Epoch {epoch}/{epochs} Completed — Average MSE Loss: {avg_loss:.5f}")

    # Export fine-tuned model checkpoint
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    print(f"Saving fine-tuned model checkpoint to {out_path}...")
    model.save_pretrained(str(out_path))
    print("Fine-tuned SBERT model successfully saved!")


if __name__ == "__main__":
    train_sbert()
