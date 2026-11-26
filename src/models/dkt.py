"""
src/models/dkt.py

Deep Knowledge Tracing (DKT) Baseline Model implementation in PyTorch.
Uses a Recurrent Neural Network (LSTM / GRU) to model student knowledge state dynamics over time.
"""

import math
import torch
import torch.nn as nn
from typing import Dict, Tuple, Optional

class DKTBaseline(nn.Module):
    """
    Deep Knowledge Tracing (DKT) Baseline model using LSTM.
    
    Inputs:
    - concept_ids: (batch_size, seq_len)
    - continuous_features: (batch_size, seq_len, num_continuous_features)
    """
    def __init__(
        self,
        num_concepts: int = 50,
        num_continuous_features: int = 3,
        embed_dim: int = 64,
        hidden_dim: int = 128,
        num_layers: int = 1,
        dropout: float = 0.1
    ):
        super().__init__()
        self.num_concepts = num_concepts
        self.embed_dim = embed_dim
        self.hidden_dim = hidden_dim

        # Concept embedding
        self.concept_embed = nn.Embedding(num_concepts + 1, embed_dim, padding_idx=0)
        self.behavior_proj = nn.Linear(num_continuous_features, embed_dim)

        # Fusion projection
        self.input_projection = nn.Sequential(
            nn.Linear(embed_dim * 2, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout)
        )

        # Recurrent layer (LSTM)
        self.rnn = nn.LSTM(
            input_size=hidden_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0
        )

        # Target concept query embedding
        self.target_concept_embed = nn.Embedding(num_concepts + 1, embed_dim, padding_idx=0)

        # Output prediction head
        self.prediction_head = nn.Sequential(
            nn.Linear(hidden_dim + embed_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1),
            nn.Sigmoid()
        )

    def forward(
        self,
        concept_ids: torch.Tensor,
        continuous_features: torch.Tensor,
        target_concept_ids: Optional[torch.Tensor] = None,
        padding_mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Forward pass for DKT baseline.
        
        Returns:
        - predictions: (batch_size, seq_len) probability of correct answer
        """
        # 1. Embed concept and project continuous features
        c_emb = self.concept_embed(concept_ids)
        b_emb = self.behavior_proj(continuous_features)

        # 2. Fuse inputs
        fused = torch.cat([c_emb, b_emb], dim=-1)
        x = self.input_projection(fused)

        # 3. Process through LSTM
        rnn_out, _ = self.rnn(x)  # (batch_size, seq_len, hidden_dim)

        # 4. Target query
        if target_concept_ids is None:
            target_concept_ids = concept_ids

        t_emb = self.target_concept_embed(target_concept_ids)

        # 5. Predict mastery
        out_features = torch.cat([rnn_out, t_emb], dim=-1)
        predictions = self.prediction_head(out_features).squeeze(-1)
        return predictions

def train_dkt_epoch(
    model: nn.Module,
    dataloader: torch.utils.data.DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
    device: torch.device
) -> float:
    """Trains DKT model for one epoch."""
    model.train()
    total_loss = 0.0
    total_count = 0

    for batch in dataloader:
        concept_ids = batch["concept_ids"].to(device)
        continuous_features = batch["continuous_features"].to(device)
        target_concepts = batch["target_concepts"].to(device)
        target_scores = batch["target_scores"].to(device)
        target_mask = batch["target_mask"].to(device)

        optimizer.zero_grad()

        preds = model(
            concept_ids=concept_ids,
            continuous_features=continuous_features,
            target_concept_ids=target_concepts,
            padding_mask=batch["mask"].to(device)
        )

        valid_indices = (target_mask > 0)
        if valid_indices.sum() == 0:
            continue

        loss = criterion(preds[valid_indices], target_scores[valid_indices])
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * valid_indices.sum().item()
        total_count += valid_indices.sum().item()

    return total_loss / max(total_count, 1)

def evaluate_dkt(
    model: nn.Module,
    dataloader: torch.utils.data.DataLoader,
    criterion: nn.Module,
    device: torch.device
) -> Tuple[float, float]:
    """Evaluates DKT model returning loss and accuracy."""
    model.eval()
    total_loss = 0.0
    correct_count = 0
    total_count = 0

    with torch.no_grad():
        for batch in dataloader:
            concept_ids = batch["concept_ids"].to(device)
            continuous_features = batch["continuous_features"].to(device)
            target_concepts = batch["target_concepts"].to(device)
            target_scores = batch["target_scores"].to(device)
            target_mask = batch["target_mask"].to(device)

            preds = model(
                concept_ids=concept_ids,
                continuous_features=continuous_features,
                target_concept_ids=target_concepts,
                padding_mask=batch["mask"].to(device)
            )

            valid_indices = (target_mask > 0)
            if valid_indices.sum() == 0:
                continue

            valid_preds = preds[valid_indices]
            valid_targets = target_scores[valid_indices]

            loss = criterion(valid_preds, valid_targets)
            total_loss += loss.item() * valid_indices.sum().item()

            binary_preds = (valid_preds >= 0.5).float()
            binary_targets = (valid_targets >= 0.5).float()
            correct_count += (binary_preds == binary_targets).sum().item()
            total_count += valid_indices.sum().item()

    avg_loss = total_loss / max(total_count, 1)
    accuracy = correct_count / max(total_count, 1)
    return avg_loss, accuracy
