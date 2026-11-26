"""
src/engine package initialization.

Exposes core adaptive learning engine modules:
- KnowledgeStateTracker: Real-time student mastery and uncertainty state tracker
- AdaptiveActivitySelector: Priority scoring and threshold-based activity router
"""

from .knowledge_state import KnowledgeStateTracker
from .adaptive_selector import AdaptiveActivitySelector

__all__ = [
    "KnowledgeStateTracker",
    "AdaptiveActivitySelector"
]
