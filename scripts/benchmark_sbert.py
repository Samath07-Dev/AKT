"""
scripts/benchmark_sbert.py

Executes rigorous side-by-side benchmarking between baseline all-MiniLM-L6-v2
and domain fine-tuned models/sbert_programming_minilm strictly on the held-out test split.
Outputs quantitative discrimination margin (delta), rejection rate of hard negatives,
and semantic alignment metrics with zero data leakage.
"""

import sys
import time
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import List, Dict, Any
import numpy as np
from src.analyzers.short_answer_analyzer import ShortAnswerAnalyzer


def run_benchmark(
    test_data_path: str = "data/sbert_test_dataset.json",
    fine_tuned_model_dir: str = "models/sbert_programming_minilm"
):
    print("=" * 75)
    print("      Domain SBERT Benchmark: Baseline vs Fine-Tuned Checkpoint      ")
    print("=" * 75)

    with open(test_data_path, "r", encoding="utf-8") as f:
        test_pairs: List[Dict[str, Any]] = json.load(f)

    print(f"Loaded {len(test_pairs)} strictly held-out evaluation pairs from {test_data_path}.\n")

    print("Loading Baseline model: 'sentence-transformers/all-MiniLM-L6-v2'...")
    baseline_analyzer = ShortAnswerAnalyzer(model_name="sentence-transformers/all-MiniLM-L6-v2")

    print(f"Loading Fine-Tuned model from: '{fine_tuned_model_dir}'...")
    finetuned_analyzer = ShortAnswerAnalyzer(model_name=fine_tuned_model_dir)

    # Buckets
    categories = ["positive", "partial", "hard_negative"]
    results = {
        "baseline": {cat: [] for cat in categories},
        "finetuned": {cat: [] for cat in categories}
    }

    t0_base = time.perf_counter()
    for item in test_pairs:
        cat = item["category"]
        res = baseline_analyzer.evaluate(item["student_text"], item["reference_answer"])
        results["baseline"][cat].append(res["evidence_score"])
    t_base_total = (time.perf_counter() - t0_base) * 1000.0 / len(test_pairs)

    t0_ft = time.perf_counter()
    for item in test_pairs:
        cat = item["category"]
        res = finetuned_analyzer.evaluate(item["student_text"], item["reference_answer"])
        results["finetuned"][cat].append(res["evidence_score"])
    t_ft_total = (time.perf_counter() - t0_ft) * 1000.0 / len(test_pairs)

    # Compute Statistics
    base_pos = np.mean(results["baseline"]["positive"]) if results["baseline"]["positive"] else 0.0
    ft_pos = np.mean(results["finetuned"]["positive"]) if results["finetuned"]["positive"] else 0.0

    base_part = np.mean(results["baseline"]["partial"]) if results["baseline"]["partial"] else 0.0
    ft_part = np.mean(results["finetuned"]["partial"]) if results["finetuned"]["partial"] else 0.0

    base_neg = np.mean(results["baseline"]["hard_negative"]) if results["baseline"]["hard_negative"] else 0.0
    ft_neg = np.mean(results["finetuned"]["hard_negative"]) if results["finetuned"]["hard_negative"] else 0.0

    base_margin = base_pos - base_neg
    ft_margin = ft_pos - ft_neg

    base_neg_rejection = np.mean([1 if s <= 0.40 else 0 for s in results["baseline"]["hard_negative"]]) * 100.0
    ft_neg_rejection = np.mean([1 if s <= 0.40 else 0 for s in results["finetuned"]["hard_negative"]]) * 100.0

    print("\n" + "=" * 75)
    print("                     EVALUATION BENCHMARK RESULTS                    ")
    print("=" * 75)
    print(f"| {'Metric':<36} | {'Baseline':<12} | {'Fine-Tuned':<12} | {'Delta':<10} |")
    print(f"|{'-' * 38}|{'-' * 14}|{'-' * 14}|{'-' * 12}|")
    print(f"| {'True Positive Paraphrases (Mean)':<36} | {base_pos:10.4f}   | {ft_pos:10.4f}   | {ft_pos - base_pos:+9.4f}  |")
    print(f"| {'Partial Explanations (Mean)':<36} | {base_part:10.4f}   | {ft_part:10.4f}   | {ft_part - base_part:+9.4f}  |")
    print(f"| {'Hard Negatives / Misconceptions (Mean)':<36} | {base_neg:10.4f}   | {ft_neg:10.4f}   | {ft_neg - base_neg:+9.4f}  |")
    print(f"| {'Discrimination Margin (Pos - Neg)':<36} | {base_margin:10.4f}   | {ft_margin:10.4f}   | {ft_margin - base_margin:+9.4f}  |")
    print(f"| {'Hard Negative Rejection Rate (<=0.40)':<36} | {base_neg_rejection:9.1f}%   | {ft_neg_rejection:9.1f}%   | {ft_neg_rejection - base_neg_rejection:+8.1f}%  |")
    print(f"| {'Inference Latency (ms / item)':<36} | {t_base_total:9.2f} ms | {t_ft_total:9.2f} ms | {t_ft_total - t_base_total:+8.2f} ms |")
    print("=" * 75)

    print("\nConcept-Level Discrimination Margin Highlights (Held-Out Test Set):")
    # Concept breakdown
    concept_map: Dict[str, Dict[str, List[float]]] = {}
    for item in test_pairs:
        c = item["concept"]
        if c not in concept_map:
            concept_map[c] = {"base_pos": [], "base_neg": [], "ft_pos": [], "ft_neg": []}

        cat = item["category"]
        b_res = baseline_analyzer.evaluate(item["student_text"], item["reference_answer"])["evidence_score"]
        f_res = finetuned_analyzer.evaluate(item["student_text"], item["reference_answer"])["evidence_score"]

        if cat == "positive":
            concept_map[c]["base_pos"].append(b_res)
            concept_map[c]["ft_pos"].append(f_res)
        elif cat == "hard_negative":
            concept_map[c]["base_neg"].append(b_res)
            concept_map[c]["ft_neg"].append(f_res)

    for c, stats in sorted(concept_map.items()):
        if stats["base_pos"] and stats["base_neg"]:
            b_m = np.mean(stats["base_pos"]) - np.mean(stats["base_neg"])
            f_m = np.mean(stats["ft_pos"]) - np.mean(stats["ft_neg"])
            print(f"  - {c:<20}: Baseline Margin = {b_m:+.3f}  -->  Fine-Tuned Margin = {f_m:+.3f} (Gain: {f_m - b_m:+.3f})")


if __name__ == "__main__":
    run_benchmark()
