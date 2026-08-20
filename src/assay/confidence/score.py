"""Per-field confidence scores, and the gate.

Provisional. Which aggregation is right is an open question in
`docs/architecture.md` and is settled by measuring calibration on held-out data,
not by argument — so all three candidates live here and the caller picks. What is
*not* provisional is the token filter: only informative tokens count, because a
grammar-forced position reports p=1.0 by construction and averaging those in
biases every score toward confident.

`min` is the default on the reasoning that a field is wrong if any part of it is
wrong — one misread digit ruins an amount — so the weakest token should set the
score. That is a hypothesis, not a result.
"""

from __future__ import annotations

import math
from typing import Literal

from assay.extract.evidence import Extraction, FieldEvidence

Method = Literal["min", "mean", "product"]


def field_score(evidence: FieldEvidence, *, method: Method = "min") -> float:
    """Confidence in one field, as a probability in [0, 1].

    A field with no informative tokens was fully determined by the grammar, so
    the model expressed no opinion and there is nothing to be confident about.
    Those score 1.0: they cannot be wrong in a way the model could have avoided.
    """
    probs = [math.exp(t.logprob) for t in evidence.informative_tokens]
    if not probs:
        return 1.0
    if method == "min":
        return min(probs)
    if method == "mean":
        return sum(probs) / len(probs)
    # Length-normalised product — the geometric mean. The raw product would
    # punish `vendor_address` for being long rather than for being uncertain.
    return math.exp(sum(math.log(max(p, 1e-12)) for p in probs) / len(probs))


def score_all(extraction: Extraction, *, method: Method = "min") -> dict[str, float]:
    return {path: field_score(f, method=method) for path, f in extraction.fields.items()}


def gate(
    extraction: Extraction, *, threshold: float = 0.85, method: Method = "min"
) -> tuple[dict[str, float], dict[str, float]]:
    """Split fields into (accepted, held for review) by score."""
    scores = score_all(extraction, method=method)
    accepted = {p: s for p, s in scores.items() if s >= threshold}
    held = {p: s for p, s in scores.items() if s < threshold}
    return accepted, held
