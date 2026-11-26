"""
src/models/behavior_akt.py

Behavior-Aware Attention-based Knowledge Tracing (Behavior-AKT) with MC Dropout Uncertainty Estimation.
Fuses concept embeddings, activity type embeddings, and continuous behavioral feature projections.
Uses causal look-ahead self-attention masks and Monte Carlo (MC) Dropout (N=20) for epistemic & aleatoric uncertainty estimation.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Tuple, Optional, List, Any

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
        return x + self.pe[:, :x.size(1), :]

class BehaviorAKT(nn.Module):
    """
    Behavior-Aware Attention-based Knowledge Tracing Model with MC Dropout.
    
    Inputs:
    - concept_ids: (batch_size, seq_len)
    - activity_types: (batch_size, seq_len)
    - continuous_features: (batch_size, seq_len, num_continuous_features)
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
        dropout: float = 0.2,
        max_seq_len: int = 100
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_concepts = num_concepts
        self.dropout_rate = dropout

        # Embeddings
        self.concept_embed = nn.Embedding(num_concepts + 1, embed_dim, padding_idx=0)
        self.activity_embed = nn.Embedding(num_activities + 1, embed_dim, padding_idx=0)
        self.behavior_proj = nn.Linear(num_continuous_features, embed_dim)

        # Feature Fusion projection layer
        self.fusion_layer = nn.Sequential(
            nn.Linear(embed_dim * 3, embed_dim),
            nn.LayerNorm(embed_dim),
            nn.ReLU(),
            nn.Dropout(dropout)
        )

        self.pos_encoder = PositionalEncoding(embed_dim, max_len=max_seq_len)

        # Causal Transformer Encoder Layer
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

        # Prediction Head
        self.prediction_head = nn.Sequential(
            nn.Linear(embed_dim * 2, dim_feedforward),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(dim_feedforward, 1),
            nn.Sigmoid()
        )

    def generate_causal_mask(self, seq_len: int, device: torch.device) -> torch.Tensor:
        """
        Generates causal look-ahead mask (-inf for future positions j > i)
        to prevent future interactions from leaking into past predictions.
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
        Forward pass with causal self-attention.
        """
        batch_size, seq_len = concept_ids.shape
        device = concept_ids.device

        # 1. Feature Embeddings & Projections
        c_emb = self.concept_embed(concept_ids)
        a_emb = self.activity_embed(activity_types)
        b_emb = self.behavior_proj(continuous_features)

        # 2. Fuse vectors
        fused = torch.cat([c_emb, a_emb, b_emb], dim=-1)
        x = self.fusion_layer(fused)

        # 3. Add Positional Encoding
        x = self.pos_encoder(x)

        # 4. Generate Causal Look-Ahead Mask
        causal_mask = self.generate_causal_mask(seq_len, device)

        # 5. Transformer Encoder
        hidden_states = self.transformer_encoder(x, mask=causal_mask)

        # 6. Target query
        if target_concept_ids is None:
            target_concept_ids = concept_ids

        t_emb = self.target_concept_embed(target_concept_ids)

        # 7. Predict Mastery
        out_features = torch.cat([hidden_states, t_emb], dim=-1)
        predictions = self.prediction_head(out_features).squeeze(-1)
        return predictions

    def predict_with_uncertainty(
        self,
        concept_ids: torch.Tensor,
        activity_types: torch.Tensor,
        continuous_features: torch.Tensor,
        target_concept_ids: Optional[torch.Tensor] = None,
        padding_mask: Optional[torch.Tensor] = None,
        num_samples: int = 20
    ) -> Dict[str, torch.Tensor]:
        """
        Performs Monte Carlo (MC) Dropout using N=num_samples stochastic forward passes
        to estimate Epistemic and Aleatoric Uncertainty.
        
        Parameters:
        - num_samples: Number of MC dropout iterations (N=20 standard)
        
        Returns:
        - Dict with:
            - 'mean_mastery': mean predicted probability (batch_size, seq_len)
            - 'epistemic_uncertainty': model parameter variance (batch_size, seq_len)
            - 'aleatoric_uncertainty': data noise entropy (batch_size, seq_len)
            - 'total_uncertainty': combined uncertainty standard deviation
            - 'samples': raw predictions tensor (num_samples, batch_size, seq_len)
        """
        # Handle MPS device limitation for scaled_dot_product_attention dropout
        orig_device = concept_ids.device
        if orig_device.type == "mps":
            self.to("cpu")
            c_ids = concept_ids.to("cpu")
            a_types = activity_types.to("cpu")
            c_feats = continuous_features.to("cpu")
            t_c_ids = target_concept_ids.to("cpu") if target_concept_ids is not None else None
            p_mask = padding_mask.to("cpu") if padding_mask is not None else None

            res = self.predict_with_uncertainty(
                concept_ids=c_ids,
                activity_types=a_types,
                continuous_features=c_feats,
                target_concept_ids=t_c_ids,
                padding_mask=p_mask,
                num_samples=num_samples
            )

            self.to(orig_device)
            return {k: v.to(orig_device) for k, v in res.items()}

        # Ensure dropout layers are active during inference for MC sampling
        self.train()
        
        sample_preds = []
        with torch.no_grad():
            for _ in range(num_samples):
                preds = self.forward(
                    concept_ids=concept_ids,
                    activity_types=activity_types,
                    continuous_features=continuous_features,
                    target_concept_ids=target_concept_ids,
                    padding_mask=padding_mask
                )
                sample_preds.append(preds)

        # Stack predictions into shape: (num_samples, batch_size, seq_len)
        stacked_preds = torch.stack(sample_preds, dim=0)

        # 1. Mean Predicted Mastery (p_bar)
        mean_mastery = torch.mean(stacked_preds, dim=0)

        # 2. Epistemic Uncertainty (Variance across MC dropout passes)
        epistemic_unc = torch.var(stacked_preds, dim=0, unbiased=True)

        # 3. Aleatoric Uncertainty (Average noise / entropy across samples: p * (1 - p))
        aleatoric_unc = torch.mean(stacked_preds * (1.0 - stacked_preds), dim=0)

        # 4. Total Uncertainty (Standard Deviation of Epistemic + Aleatoric)
        total_unc = torch.sqrt(epistemic_unc + aleatoric_unc + 1e-8)

        # Revert model to eval mode
        self.eval()

        return {
            "mean_mastery": mean_mastery,
            "epistemic_uncertainty": epistemic_unc,
            "aleatoric_uncertainty": aleatoric_unc,
            "total_uncertainty": total_unc,
            "samples": stacked_preds
        }

def train_behavior_akt_epoch(
    model: nn.Module,
    dataloader: torch.utils.data.DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
    device: torch.device
) -> float:
    """Trains Behavior-AKT model for one epoch."""
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

        loss = criterion(preds[valid_indices], target_scores[valid_indices])
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * valid_indices.sum().item()
        total_count += valid_indices.sum().item()

    return total_loss / max(total_count, 1)

def evaluate_behavior_akt(
    model: nn.Module,
    dataloader: torch.utils.data.DataLoader,
    criterion: nn.Module,
    device: torch.device
) -> Tuple[float, float]:
    """Evaluates Behavior-AKT model returning loss and binary accuracy."""
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
