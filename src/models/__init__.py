"""
src/models package initialization.

Exposes Knowledge Tracing model architectures:
- AKTBaseline: Standard Attention-based Knowledge Tracing
- DKTBaseline: Deep Knowledge Tracing (LSTM)
- BehaviorAKT: Behavior-Aware Attention-based Knowledge Tracing + MC Dropout Uncertainty
"""

from .akt import AKTBaseline
from .dkt import DKTBaseline
from .behavior_akt import BehaviorAKT

__all__ = [
    "AKTBaseline",
    "DKTBaseline",
    "BehaviorAKT"
]
