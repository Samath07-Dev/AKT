# Machine Learning & Cognitive Science Research Context

**Document:** `project_handover/ML_RESEARCH_CONTEXT.md`  
**Project:** Adaptive Knowledge Tracing (AKT) & Multimodal Intelligent Tutoring System  
**Audience:** Incoming Machine Learning Engineers, Educational Data Mining Researchers, and Google Gemini Pro  

---

## 1. Research Problem & Theoretical Framework

In Computer Science Education (CSEd), modeling a student's evolving cognitive state requires tracking heterogeneous learning interactions. A student does not merely answer multiple-choice questions; they formulate freeform natural language explanations, write iterative code, encounter syntax and runtime exceptions, and inspect progressive hints.

Traditional Knowledge Tracing models suffer from two primary limitations:
1. **Unimodal Binary Simplification:** Reducing all student evidence to a single binary variable $y_t \in \{0, 1\}$ discards rich formative signals (e.g. semantic proximity in short answers or structural validity in code).
2. **Deterministic Overconfidence:** Deep learning KT models (such as standard DKT or basic AKT) produce uncalibrated probability predictions without estimating **epistemic uncertainty** (model ignorance due to scarce observations) or **aleatoric uncertainty** (inherent noise in student problem-solving).

This project implements an integrated pipeline bridging offline deep neural knowledge tracing with real-time adaptive educational scaffolding.

---

## 2. Neural Model Architectures

The repository provides three distinct neural knowledge tracing models in `src/models/`:

### A. Deep Knowledge Tracing (DKT Baseline)
- **Source File:** `src/models/dkt.py`
- **Architecture:** Recurrent Neural Network (LSTM or GRU).
  - Concept Embedding: Maps `concept_id` $\in [1, K]$ to $d$-dimensional dense space ($d=64$).
  - Continuous Feature Projection: Dense linear layer projecting behavioral telemetry (e.g. response time, attempt count) to $d$-dimensions.
  - Fusion Layer: Concatenation followed by linear projection with ReLU.
  - Recurrent Backbone: 1-layer LSTM ($h=128$, dropout $=0.1$).
  - Prediction Head: Linear layer outputting mastery logits across all concepts.
- **Input Features:** `concept_ids: (B, T)`, `continuous_features: (B, T, F)`.
- **Output:** Predicted response probability $\hat{y}_{t+1} \in [0, 1]$ for the target concept.

### B. Attention-based Knowledge Tracing (AKT Baseline)
- **Source File:** `src/models/akt.py`
- **Architecture:** Causal Multi-Head Self-Attention Network inspired by Ghosh et al.
  - Embeddings: Concept embeddings + Activity type embeddings (MCQ, Short Answer, Coding).
  - Positional Encoding: Fixed sinusoidal positional encodings preserving sequence order.
  - Causal Attention Mask: Lower-triangular attention mask preventing lookahead into future interactions.
  - Self-Attention Layers: Multi-head attention ($H=4$, $d_k=16$) with residual connections and layer normalization.
  - Prediction Head: Concept-specific feed-forward network with Sigmoid activation.
- **Input Features:** `concept_ids: (B, T)`, `activity_types: (B, T)`, `continuous_features: (B, T, F)`.
- **Pretrained Checkpoint:** `data/processed/akt_baseline.pt` ($447\text{ KB}$, PyTorch state dict).

### C. Behavior-Aware AKT with MC Dropout (Behavior-AKT)
- **Source File:** `src/models/behavior_akt.py`
- **Architecture:** Multimodal Attention Network with Bayesian Uncertainty Approximation.
  - Feature Fusion: Joint embedding of concept IDs, activity modality IDs (0: MCQ, 1: Coding, 2: Short Answer), and continuous telemetry.
  - Monte Carlo (MC) Dropout: Dropout layers ($p=0.20$) remain active during inference.
  - Stochastic Sampling ($N=20$ forward passes):
    $$\mu = \frac{1}{N} \sum_{i=1}^N \hat{y}^{(i)}, \quad \sigma^2 = \frac{1}{N} \sum_{i=1}^N \left(\hat{y}^{(i)} - \mu\right)^2$$
  - Epistemic Uncertainty ($\sigma$): Quantifies model uncertainty due to lack of student data for a given concept.

---

## 3. Real-Time Adaptive Engine & Scaffolding Policy

In the live web application (`api.py`), real-time interaction updates use the dedicated runtime engine in `src/engine/`:

### A. Real-Time Knowledge State Tracker (EMA)
- **Source File:** `src/engine/knowledge_state.py`
- **Mathematical Update Rule:**
  Rather than running expensive neural backprop or full sequence passes on every user click, the production runtime maintains sequential mastery via an **Exponential Moving Average (EMA)**:
  $$\mu_{t} = (1 - \alpha) \cdot \mu_{t-1} + \alpha \cdot e_t$$
  $$\sigma_{t} = \max\left(\sigma_{\min}, \; \sigma_{t-1} \cdot \beta\right)$$
  - $\alpha$: Learning rate / evidence weight ($\alpha=0.20$).
  - $e_t$: Incoming evidence score ($e_t \in \{0.0, 1.0\}$ for admitted MCQ items).
  - $\beta$: Uncertainty decay parameter ($\beta=0.90$), reducing uncertainty as observations accumulate.
  - **Priors:** Every concept initializes at $\mu_0 = 0.30$ (30% prior mastery) and $\sigma_0 = 0.50$ (50% prior uncertainty).
  - **Cognitive Safety:** Only binary MCQ items (`activity_type=0`) update the EMA tracker. Short Answer and Coding are excluded from EMA state mutation.

### B. Uncertainty-Guided Adaptive Selector
- **Source File:** `src/engine/adaptive_selector.py`
- **Priority Score Formula:**
  $$\text{Priority}(c) = \left(1.0 - \mu_c\right) \times \left(1.0 + \sigma_c\right)$$
  - High priority is assigned to concepts that are both **unmastered** (low $\mu$) and **uncertain** (high $\sigma$).
- **Modality Routing Thresholds:**
  - **MCQ (0):** High uncertainty or low mastery ($\mu < 0.50$ or $\sigma \ge 0.35$).
  - **Short Answer (2):** Moderate mastery with low uncertainty ($0.50 \le \mu < 0.75$ and $\sigma < 0.35$).
  - **Coding Challenge (1):** High mastery ($\mu \ge 0.75$).
- **4-Tier Scaffolding Rules:**
  1. *Difficulty Scaffolding:* Bundle score $< 0.5$ downgrades difficulty (`hard` $\to$ `medium` $\to$ `easy`); score $> 0.8$ upgrades difficulty.
  2. *Difficulty Floor:* Score $< 0.5$ on `easy` maintains the `easy` floor and cycles to an unattempted question.
  3. *Modality Downgrade:* Failing ($< 0.5$) an `easy` Coding or Short Answer question immediately downgrades the recommended modality to MCQ.
  4. *Prerequisite Fallback:* Failing 3 `easy` questions consecutively routes back to a prerequisite concept in the curriculum graph.

---

## 4. Multimodal Analyzers

| Modality | Analyzer Class | File Path | Evaluation Methodology | Raw Score Bounds |
| :--- | :--- | :--- | :--- | :--- |
| **MCQ** | `MCQAnalyzer` | `src/analyzers/mcq_analyzer.py` | Exact string key comparison against canonical answer; optional distractor partial-credit weighting. | $0.0$ or $1.0$ (binary) |
| **Short Answer** | `ShortAnswerAnalyzer` | `src/analyzers/short_answer_analyzer.py` | Semantic cosine similarity between Sentence-BERT (`sentence-transformers/all-MiniLM-L6-v2`) embeddings of student text and rubric reference text. | $[-1.0, 1.0]$ raw cosine; normalized to $[0.0, 1.0]$ |
| **Coding** | `CodeAnalyzer` | `src/analyzers/code_analyzer.py` | Static AST validation (`ast.parse`) checking compilability and syntax validity. Host-process execution is permanently quarantined. | Binary syntax ($0.0$ or $1.0$) |
| **Coding Sandbox** | `SandboxRunner` | `src/analyzers/sandbox_runner.py` | Hardened non-root ephemeral Docker container execution against test cases with $5\text{s}$ timeout. Fails closed when Docker is offline. | Passed test cases / Total test cases; null if offline |

---

## 5. Research Datasets & Benchmarking

### Datasets
1. **CSEDM Data Challenge:**
   - Raw logs in `data/raw/csedm/` and `csedm_sample.csv`.
   - Captures code submissions, compilation events, timestamps, and test case pass fractions from college programming courses.
2. **Runestone Interactive E-Book Logs:**
   - Raw logs in `data/raw/runestone/` and `runestone_sample.csv`.
   - Captures reading progress, interactive multiple-choice answers, and practice exercise runs.

### Preprocessing Pipeline (`src/data/preprocessor.py`)
- Standardizes interaction vectors: maps concept names to integer IDs, normalizes response times using log-scaling, standardizes attempt counts.
- Enforces **student-level train/validation/test splits** (80/10/10) to prevent sequence leakage across splits.
- Builds PyTorch `KTDataset` generating fixed-length interaction windows ($\text{max\_seq\_len}=50$).

### Benchmarking Script (`run_presentation_experiments.py`)
- Executes comparative evaluation across DKT, AKT, and Behavior-AKT.
- Evaluation Metrics:
  - **Area Under the ROC Curve (AUC):** Primary classification metric.
  - **Accuracy & F1-Score:** Binary classification performance at threshold $0.5$.
  - **Root Mean Squared Error (RMSE) & Mean Absolute Error (MAE):** Calibration of predicted probability versus actual binary outcome.
  - **Mean Epistemic Uncertainty ($\bar{\sigma}$):** Average standard deviation across Monte Carlo samples.

---

## 6. Research Implementation Status Matrix

| Research Capability | Source Module | Implementation Status | Notes |
| :--- | :--- | :--- | :--- |
| DKT Baseline Model | `src/models/dkt.py` | **Implemented** | Functional PyTorch LSTM baseline. |
| AKT Baseline Model | `src/models/akt.py` | **Implemented** | Causal self-attention; weights saved in `akt_baseline.pt`. |
| Behavior-AKT Model | `src/models/behavior_akt.py` | **Implemented** | Multimodal embedding fusion + MC Dropout ($N=20$). |
| Real-Time Knowledge Tracker | `src/engine/knowledge_state.py` | **Implemented** | Production EMA mastery updates in `api.py`. |
| Adaptive Activity Selector | `src/engine/adaptive_selector.py` | **Implemented** | Priority formula and 4-tier scaffolding operational. |
| SBERT Semantic Evaluator | `src/analyzers/short_answer_analyzer.py`| **Implemented** | Uses `sentence-transformers/all-MiniLM-L6-v2`. |
| AST Syntax Analyzer | `src/analyzers/code_analyzer.py` | **Implemented** | Quarantined host-process security policy enforced. |
| Hardened Docker Sandbox | `src/analyzers/sandbox_runner.py` | **Implemented** | Docker runner operational; fails closed when daemon offline. |
| Canonical Evidence Schema | `src/schemas/evidence.py` | **Implemented** | Pydantic 2 `UnifiedEvidenceRecord` frozen and verified. |
| Harmonization Adapters | `src/evidence_adapters/` | **Implemented** | MCQ, Short Answer, and Coding adapters verified. |
| Embedded Score Persistence | `src/evidence_adapters/bundle_builder.py`| **Implemented** | Option A atomic embedded write in `scores` collection. |
| Research Policy on Code Mastery | Future Research | **Planned / Open** | Coding partial credit admission policy remains pending empirical validation. |
| Asynchronous Sandbox Worker | Future Implementation | **Planned / Open** | Background queue processing for pending code executions. |

