from __future__ import annotations
from ..config import settings


# Simple heuristic: if top-k retrieval coverage < threshold OR question length > N OR conflicting citations
# then escalate to GPT-5. Isolatable via feature flag.


def choose_model(auto_escalate: bool, retrieval_score: float, q_len: int, conflicts: int) -> str:
    model = settings.GPT5_MINI_MODEL
    if auto_escalate and (retrieval_score < 0.45 or q_len > 280 or conflicts >= 2):
        model = settings.GPT5_FULL_MODEL
    return model