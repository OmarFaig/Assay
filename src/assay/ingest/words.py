"""Word-level text extraction from DocILE documents.

About 30% of DocILE PDFs are scans with no text layer, so PyMuPDF alone
silently yields nothing for roughly a third of the corpus. DocILE ships
pre-computed OCR for every document, so this module reads the embedded text
layer when there is one and falls back to that OCR when there is not.

Both paths produce the same `Word` records with page-normalized [0, 1]
coordinates, matching the convention the shipped OCR already uses, so callers
do not need to know which source a document came from.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pymupdf

Source = Literal["pdf", "ocr"]

# A page whose text layer yields fewer characters than this is treated as a
# scan. Empty layers usually give exactly 0, but some scans carry a stray
# artifact or two, so the check is a threshold rather than a test for empty.
MIN_TEXT_LAYER_CHARS = 20


@dataclass(frozen=True, slots=True)
class Word:
    """A single token with its location on the page.

    `bbox` is (x0, y0, x1, y1) normalized to [0, 1] against page dimensions,
    with the origin at the top-left. `confidence` is None for words read from
    a PDF text layer, where the characters are exact rather than predicted.
    """

    text: str
    page: int
    bbox: tuple[float, float, float, float]
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class Document:
    doc_id: str
    words: tuple[Word, ...]
    source: Source
    page_count: int

    @property
    def text(self) -> str:
        """Words joined in reading order, one line per page break."""
        out: list[str] = []
        current = 0
        for w in self.words:
            if w.page != current:
                out.append("\n")
                current = w.page
            out.append(w.text)
        return " ".join(out).replace(" \n ", "\n")

    def page(self, index: int) -> tuple[Word, ...]:
        return tuple(w for w in self.words if w.page == index)


def _pdf_words(path: Path) -> tuple[tuple[Word, ...], int, bool]:
    """Read the embedded text layer.

    Returns the words, the page count, and whether the layer was usable at all.

    PyMuPDF reports word boxes in unrotated cropbox space, while `page.rect`
    is rotation-adjusted, so on a /Rotate 90 page the two disagree and naive
    division overflows [0, 1]. Mapping through `rotation_matrix` first puts
    boxes in the same display orientation a renderer would produce, which is
    also the orientation the shipped OCR was computed in.
    """
    words: list[Word] = []
    total_chars = 0

    with pymupdf.open(path) as doc:
        page_count = doc.page_count
        for index, page in enumerate(doc):
            rect = page.rect
            if not rect.width or not rect.height:
                continue
            rotate = page.rotation_matrix
            for x0, y0, x1, y1, text, *_ in page.get_text("words"):
                text = text.strip()
                if not text:
                    continue
                total_chars += len(text)
                box = pymupdf.Rect(x0, y0, x1, y1) * rotate
                words.append(
                    Word(
                        text=text,
                        page=index,
                        bbox=_clamp(
                            box.x0 / rect.width,
                            box.y0 / rect.height,
                            box.x1 / rect.width,
                            box.y1 / rect.height,
                        ),
                    )
                )

    return tuple(words), page_count, total_chars >= MIN_TEXT_LAYER_CHARS


def _clamp(x0: float, y0: float, x1: float, y1: float) -> tuple[float, float, float, float]:
    """Clip a normalized box to the page.

    Glyphs sometimes sit a hair outside the page box — a header baseline above
    the top edge, say — which is legitimate in the PDF but not useful to
    callers reasoning in page-relative space.
    """
    x0, x1 = sorted((min(max(x0, 0.0), 1.0), min(max(x1, 0.0), 1.0)))
    y0, y1 = sorted((min(max(y0, 0.0), 1.0), min(max(y1, 0.0), 1.0)))
    return x0, y0, x1, y1


def _ocr_words(path: Path) -> tuple[tuple[Word, ...], int]:
    """Read DocILE's pre-computed OCR.

    The format nests pages -> blocks -> lines -> words, and word geometry is
    already normalized as [[x0, y0], [x1, y1]].
    """
    payload = json.loads(path.read_text())
    pages = payload["pages"]
    words: list[Word] = []

    for index, page in enumerate(pages):
        for block in page.get("blocks", ()):
            for line in block.get("lines", ()):
                for word in line.get("words", ()):
                    text = word["value"].strip()
                    if not text:
                        continue
                    # snapped_geometry is fitted to the detected text baseline
                    # and is tighter where present; geometry is always there.
                    (x0, y0), (x1, y1) = word.get("snapped_geometry") or word["geometry"]
                    words.append(
                        Word(
                            text=text,
                            page=index,
                            bbox=(x0, y0, x1, y1),
                            confidence=word.get("confidence"),
                        )
                    )

    return tuple(words), len(pages)


def extract(
    doc_id: str, root: Path | str = "data/docile", *, force: Source | None = None
) -> Document:
    """Extract words for one document, preferring the PDF text layer.

    Pass `force` to pin a source and skip the fallback, which is useful when
    comparing the two against each other.
    """
    root = Path(root)
    pdf_path = root / "pdfs" / f"{doc_id}.pdf"
    ocr_path = root / "ocr" / f"{doc_id}.json"

    if force != "ocr":
        words, page_count, usable = _pdf_words(pdf_path)
        if usable or force == "pdf":
            return Document(doc_id, words, "pdf", page_count)

    words, page_count = _ocr_words(ocr_path)
    return Document(doc_id, words, "ocr", page_count)


def doc_ids(root: Path | str = "data/docile", split: str = "trainval") -> list[str]:
    """Document ids for a split (`train`, `val`, or `trainval`)."""
    return json.loads((Path(root) / f"{split}.json").read_text())


def extract_split(root: Path | str = "data/docile", split: str = "trainval") -> Iterator[Document]:
    for doc_id in doc_ids(root, split):
        yield extract(doc_id, root)
