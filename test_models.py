"""
test_models.py

Verification script for DKTBaseline, AKTBaseline, and BehaviorAKT with MC Dropout Uncertainty.
"""

import torch
from src.models import DKTBaseline, AKTBaseline, BehaviorAKT

def test_all_models():
    print("=" * 60)
    print("         Verifying Knowledge Tracing Models          ")
    print("=" * 60)

    device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Testing on device: {device}")

    # Create dummy batch (batch_size=4, seq_len=10)
    batch_size = 4
    seq_len = 10
    num_concepts = 20

    concept_ids = torch.randint(1, num_concepts, (batch_size, seq_len)).to(device)
    activity_types = torch.randint(0, 3, (batch_size, seq_len)).to(device)
    continuous_features = torch.randn(batch_size, seq_len, 3).to(device)
    target_concepts = torch.randint(1, num_concepts, (batch_size, seq_len)).to(device)
    mask = torch.ones(batch_size, seq_len).to(device)

    # 1. Test DKTBaseline
    print("\n1. Testing DKT Baseline Model...")
    dkt_model = DKTBaseline(num_concepts=num_concepts, num_continuous_features=3, hidden_dim=64).to(device)
    dkt_preds = dkt_model(concept_ids, continuous_features, target_concepts, mask)
    print(f"  - DKT Output Shape: {dkt_preds.shape} (Expected: [{batch_size}, {seq_len}])")
    assert dkt_preds.shape == (batch_size, seq_len)
    assert (dkt_preds >= 0.0).all() and (dkt_preds <= 1.0).all()

    # 2. Test AKTBaseline
    print("\n2. Testing AKT Baseline Model...")
    akt_model = AKTBaseline(num_concepts=num_concepts, embed_dim=64, nhead=4).to(device)
    akt_preds = akt_model(concept_ids, activity_types, continuous_features, target_concepts, mask)
    print(f"  - AKT Output Shape: {akt_preds.shape} (Expected: [{batch_size}, {seq_len}])")
    assert akt_preds.shape == (batch_size, seq_len)
    assert (akt_preds >= 0.0).all() and (akt_preds <= 1.0).all()

    # 3. Test BehaviorAKT + MC Dropout Uncertainty (N=20)
    print("\n3. Testing Behavior-AKT Model + MC Dropout (N=20)...")
    behavior_model = BehaviorAKT(num_concepts=num_concepts, embed_dim=64, nhead=4, dropout=0.2).to(device)
    behavior_preds = behavior_model(concept_ids, activity_types, continuous_features, target_concepts, mask)
    print(f"  - Behavior-AKT Forward Shape: {behavior_preds.shape} (Expected: [{batch_size}, {seq_len}])")
    assert behavior_preds.shape == (batch_size, seq_len)

    # Test MC Dropout Uncertainty (N=20 passes)
    print("  - Running predict_with_uncertainty(num_samples=20)...")
    unc_res = behavior_model.predict_with_uncertainty(
        concept_ids=concept_ids,
        activity_types=activity_types,
        continuous_features=continuous_features,
        target_concept_ids=target_concepts,
        padding_mask=mask,
        num_samples=20
    )

    print(f"  - Samples Shape: {unc_res['samples'].shape} (Expected: [20, {batch_size}, {seq_len}])")
    print(f"  - Mean Mastery Shape: {unc_res['mean_mastery'].shape}")
    print(f"  - Epistemic Uncertainty Mean: {unc_res['epistemic_uncertainty'].mean().item():.6f}")
    print(f"  - Aleatoric Uncertainty Mean: {unc_res['aleatoric_uncertainty'].mean().item():.6f}")
    print(f"  - Total Uncertainty Mean:     {unc_res['total_uncertainty'].mean().item():.6f}")

    assert unc_res['samples'].shape == (20, batch_size, seq_len)
    assert unc_res['mean_mastery'].shape == (batch_size, seq_len)
    assert unc_res['epistemic_uncertainty'].shape == (batch_size, seq_len)
    assert unc_res['aleatoric_uncertainty'].shape == (batch_size, seq_len)
    assert unc_res['total_uncertainty'].shape == (batch_size, seq_len)

    print("\nAll model architectures and MC Dropout uncertainty estimation verified successfully!")

if __name__ == "__main__":
    test_all_models()
