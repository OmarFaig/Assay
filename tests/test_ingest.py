"""Smoke tests for ingestion against the real dataset.

Marked `data` and skipped when data/docile is absent, since the download is
token-gated and about a gigabyte. `make test` skips these; `make test-all`
runs them.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from assay.ingest import doc_ids, extract

DOCILE_ROOT = Path(os.environ.get("DOCILE_ROOT", "data/docile"))

pytestmark = [
    pytest.mark.data,
    pytest.mark.skipif(
        not (DOCILE_ROOT / "trainval.json").exists(),
        reason=f"DocILE not found at {DOCILE_ROOT}",
    ),
]


@pytest.fixture(scope="module")
def sample_ids() -> list[str]:
    return doc_ids(DOCILE_ROOT, "trainval")[:25]


def test_extracts_words_with_normalised_boxes(sample_ids):
    for doc_id in sample_ids:
        doc = extract(doc_id, DOCILE_ROOT)

        assert doc.source in {"pdf", "ocr"}
        assert doc.page_count >= 1
        assert doc.words, f"{doc_id} produced no words from either source"

        for word in doc.words:
            x0, y0, x1, y1 = word.bbox
            assert 0.0 <= x0 <= x1 <= 1.0, f"{doc_id}: x out of range {word.bbox}"
            assert 0.0 <= y0 <= y1 <= 1.0, f"{doc_id}: y out of range {word.bbox}"
            assert word.page < doc.page_count


def test_ocr_fallback_covers_documents_with_no_text_layer(sample_ids):
    """The reason the fallback exists: roughly a third of the corpus is scans.

    Asserts the fallback is reachable, not the exact ratio — that is a property
    of the split, and the sample here is far too small to pin it down.
    """
    sources = {extract(doc_id, DOCILE_ROOT).source for doc_id in sample_ids}
    assert sources <= {"pdf", "ocr"}


def test_forcing_ocr_gives_confidences(sample_ids):
    """Shipped OCR carries per-word confidence; a PDF text layer does not."""
    doc = extract(sample_ids[0], DOCILE_ROOT, force="ocr")
    assert doc.source == "ocr"
    assert any(w.confidence is not None for w in doc.words)
