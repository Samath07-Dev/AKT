"""
src/models/akt.py

Baseline Attention-based Knowledge Tracing (AKT) Model implementation in PyTorch.
Incorporates concept embeddings, activity type embeddings, continuous behavioral feature projections,
causal multi-head self-attention, and sequence prediction heads.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Tuple, Optional

class PositionalEncoding(nn.Module):
    """Sinusoidal Positional Encoding for Sequential Self-Attention."""
    def __init__(self, embed_dim: int, max_len: int = 500):
        super().__init__()
        pe = torch.zeros(max_len, embed_dim)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, embed_dim, 2).float() * (-math.log(10000.0) / embed_dim))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x shape: (batch_size, seq_len, embed_dim)
        return x + self.pe[:, :x.size(1), :]

class AKTBaseline(nn.Module):
    """
    Attention-based Knowledge Tracing (AKT) Model.
    
    Inputs:
    - concept_ids: (batch_size, seq_len)
    - activity_types: (batch_size, seq_len)
    - continuous_features: (batch_size, seq_len, num_continuous_features)
    
    Architecture:
    1. Concept & Activity Type Embeddings
    2. Continuous Behavior Projection (score, response time, attempt number)
    3. Feature Fusion Layer + Positional Encoding
    4. Causal Transformer Encoder (Multi-Head Self-Attention)
    5. Concept Mastery Prediction Head (Sigmoid Output)
    """
    def __init__(
        self,
        num_concepts: int = 50,
        num_activities: int = 5,
        num_continuous_features: int = 3,
        embed_dim: int = 64,
        nhead: int = 4,
        num_layers: int = 2,
        dim_feedforward: int = 128,
        dropout: float = 0.1,
        max_seq_len: int = 100
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_concepts = num_concepts

        # Embeddings
        self.concept_embed = nn.Embedding(num_concepts + 1, embed_dim, padding_idx=0)
        self.activity_embed = nn.Embedding(num_activities + 1, embed_dim, padding_idx=0)
        self.behavior_proj = nn.Linear(num_continuous_features, embed_dim)

        # Feature Fusion projection: maps [concept + activity + behavior] -> embed_dim
        self.fusion_layer = nn.Sequential(
            nn.Linear(embed_dim * 3, embed_dim),
            nn.LayerNorm(embed_dim),
            nn.ReLU(),
            nn.Dropout(dropout)
        )

        self.pos_encoder = PositionalEncoding(embed_dim, max_len=max_seq_len)

        # Transformer Encoder Layer with Causal Attention Mask
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            activation='relu',
            batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        # Target concept query embedding
        self.target_concept_embed = nn.Embedding(num_concepts + 1, embed_dim, padding_idx=0)

        # Final Mastery Prediction Head
        self.prediction_head = nn.Sequential(
            nn.Linear(embed_dim * 2, dim_feedforward),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(dim_feedforward, 1),
            nn.Sigmoid()
        )

    def generate_causal_mask(self, seq_len: int, device: torch.device) -> torch.Tensor:
        """
        Generates lower-triangular float mask (0 for unmasked, -1e9 for masked) 
        to prevent future timesteps from leaking into past across hardware targets.
        """
        mask = torch.triu(torch.full((seq_len, seq_len), float('-inf'), device=device), diagonal=1)
        return mask

    def forward(
        self,
        concept_ids: torch.Tensor,
        activity_types: torch.Tensor,
        continuous_features: torch.Tensor,
        target_concept_ids: Optional[torch.Tensor] = None,
        padding_mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Forward pass.
        - concept_ids: (batch_size, seq_len)
        - activity_types: (batch_size, seq_len)
        - continuous_features: (batch_size, seq_len, 3)
        - target_concept_ids: (batch_size, seq_len) target concept to predict mastery for
        - padding_mask: (batch_size, seq_len) 1.0 for valid tokens, 0.0 for padding
        
        Returns:
        - predictions: (batch_size, seq_len) probability of correctly answering target concept
        """
        batch_size, seq_len = concept_ids.shape
        device = concept_ids.device

        # 1. Look up embeddings
        c_emb = self.concept_embed(concept_ids)  # (batch_size, seq_len, embed_dim)
        a_emb = self.activity_embed(activity_types)  # (batch_size, seq_len, embed_dim)
        b_emb = self.behavior_proj(continuous_features)  # (batch_size, seq_len, embed_dim)

        # 2. Fuse features
        fused = torch.cat([c_emb, a_emb, b_emb], dim=-1)  # (batch_size, seq_len, embed_dim * 3)
        x = self.fusion_layer(fused)  # (batch_size, seq_len, embed_dim)

        # 3. Add Positional Encoding
        x = self.pos_encoder(x)

        # 4. Generate Causal Attention Mask
        causal_mask = self.generate_causal_mask(seq_len, device)

        # 5. Transform sequence through Transformer Encoder
        hidden_states = self.transformer_encoder(
            x,
            mask=causal_mask
        )  # (batch_size, seq_len, embed_dim)

        # 6. Target concept query representation
        if target_concept_ids is None:
            # If target concepts not specified, predict on current concept
            target_concept_ids = concept_ids

        t_emb = self.target_concept_embed(target_concept_ids)  # (batch_size, seq_len, embed_dim)

        # 7. Concatenate hidden state with target concept query
        out_features = torch.cat([hidden_states, t_emb], dim=-1)  # (batch_size, seq_len, embed_dim * 2)

        # 8. Compute mastery predictions
        predictions = self.prediction_head(out_features).squeeze(-1)  # (batch_size, seq_len)
        return predictions

def train_akt_epoch(
    model: nn.Module,
    dataloader: torch.utils.data.DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
    device: torch.device
) -> float:
    """Trains AKT model for one epoch using Binary Cross Entropy Loss on valid masked tokens."""
    model.train()
    total_loss = 0.0
    total_count = 0

    for batch in dataloader:
        concept_ids = batch["concept_ids"].to(device)
        activity_types = batch["activity_types"].to(device)
        continuous_features = batch["continuous_features"].to(device)
        target_concepts = batch["target_concepts"].to(device)
        target_scores = batch["target_scores"].to(device)
        target_mask = batch["target_mask"].to(device)

        optimizer.zero_grad()

        # Forward pass
        preds = model(
            concept_ids=concept_ids,
            activity_types=activity_types,
            continuous_features=continuous_features,
            target_concept_ids=target_concepts,
            padding_mask=batch["mask"].to(device)
        )

        # Compute loss strictly over valid target timesteps
        valid_indices = (target_mask > 0)
        if valid_indices.sum() == 0:
            continue

        loss = criterion(preds[valid_indices], target_scores[valid_indices])
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * valid_indices.sum().item()
        total_count += valid_indices.sum().item()

    return total_loss / max(total_count, 1)

def evaluate_akt(
    model: nn.Module,
    dataloader: torch.utils.data.DataLoader,
    criterion: nn.Module,
    device: torch.device
) -> Tuple[float, float]:
    """Evaluates AKT model on validation/test set, returning Loss and Binary Accuracy."""
    model.eval()
    total_loss = 0.0
    correct_count = 0
    total_count = 0

    with torch.no_grad():
        for batch in dataloader:
            concept_ids = batch["concept_ids"].to(device)
            activity_types = batch["activity_types"].to(device)
            continuous_features = batch["continuous_features"].to(device)
            target_concepts = batch["target_concepts"].to(device)
            target_scores = batch["target_scores"].to(device)
            target_mask = batch["target_mask"].to(device)

            preds = model(
                concept_ids=concept_ids,
                activity_types=activity_types,
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
