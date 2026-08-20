"""Locating an extracted value back on the page.

Nothing in the model's output points at a word. The grammar produced a string,
and where that string came from is a separate matching problem — one that has to
be solved for review to show a person *why* a field was held back.

Matching is approximate on purpose. The model is asked to copy values verbatim
but normalisation still happens: `1,190.00` on the page becomes `1190.00` in the
record, a date is rewritten to ISO, an address spanning three lines arrives as
one string. Comparing on alphanumerics only absorbs all three.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from assay.ingest import Document, Word

# An address can run to a dozen words; beyond that a window is almost certainly
# spanning unrelated text and the search cost stops paying for itself.
MAX_WINDOW = 14


@dataclass(frozen=True, slots=True)
class Provenance:
    page: int
    bbox: tuple[float, float, float, float]
    words: tuple[Word, ...]
    ratio: float


def _normalise(text: str) -> str:
    return re.sub(r"[^0-9a-z]", "", text.lower())


def locate(document: Document, value: str, *, min_ratio: float = 0.75) -> Provenance | None:
    """Find the run of words that best matches `value`.

    Returns None when nothing clears `min_ratio`, which is the honest answer for
    a value the model synthesised rather than copied — and knowing a field has no
    source on the page is itself worth surfacing in review.
    """
    target = _normalise(value)
    if not target:
        return None

    best: Provenance | None = None
    for page_index in range(document.page_count):
        words = document.page(page_index)
        normalised = [_normalise(w.text) for w in words]
        for start in range(len(words)):
            joined = ""
            for length in range(MAX_WINDOW):
                if start + length >= len(words):
                    break
                joined += normalised[start + length]
                # Once a window is half again as long as the target, extending it
                # can only make the match worse.
                if len(joined) > len(target) * 1.5 + 4:
                    break
                ratio = SequenceMatcher(None, target, joined).ratio()
                if best is None or ratio > best.ratio:
                    run = words[start : start + length + 1]
                    best = Provenance(
                        page=page_index,
                        bbox=(
                            min(w.bbox[0] for w in run),
                            min(w.bbox[1] for w in run),
                            max(w.bbox[2] for w in run),
                            max(w.bbox[3] for w in run),
                        ),
                        words=run,
                        ratio=ratio,
                    )

    return best if best and best.ratio >= min_ratio else None
