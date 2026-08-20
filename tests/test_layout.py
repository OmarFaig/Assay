"""Line grouping, tested on synthetic geometry so it runs without the dataset."""

from __future__ import annotations

from assay.ingest import Document, Word


def doc(*boxes: tuple[str, float, float, float, float], pages: int = 1) -> Document:
    words = tuple(Word(text=t, page=0, bbox=(x0, y0, x1, y1)) for t, x0, y0, x1, y1 in boxes)
    return Document(doc_id="synthetic", words=words, source="pdf", page_count=pages)


def test_words_on_one_baseline_join_into_a_line():
    d = doc(("Total", 0.1, 0.5, 0.2, 0.52), ("1190.00", 0.8, 0.5, 0.9, 0.52))
    assert d.layout() == "Total 1190.00"


def test_separate_baselines_become_separate_lines():
    d = doc(("Net", 0.1, 0.50, 0.2, 0.52), ("Gross", 0.1, 0.60, 0.2, 0.62))
    assert d.layout() == "Net\nGross"


def test_line_is_ordered_left_to_right_regardless_of_input_order():
    d = doc(("second", 0.8, 0.5, 0.9, 0.52), ("first", 0.1, 0.5, 0.2, 0.52))
    assert d.layout() == "first second"


def test_taller_word_still_shares_its_line():
    # A bold total is set larger than its label; a fixed baseline-distance test
    # would split them, an overlap test keeps them together.
    d = doc(("TOTAL", 0.1, 0.50, 0.25, 0.56), ("1190.00", 0.8, 0.52, 0.9, 0.54))
    assert d.layout() == "TOTAL 1190.00"


def test_layout_beats_text_at_keeping_rows_apart():
    d = doc(
        ("Widget", 0.1, 0.30, 0.2, 0.32),
        ("10.00", 0.8, 0.30, 0.9, 0.32),
        ("Gadget", 0.1, 0.40, 0.2, 0.42),
        ("20.00", 0.8, 0.40, 0.9, 0.42),
    )
    # `text` flattens both rows into one run-on line; `layout` keeps the table.
    assert "\n" not in d.text
    assert d.layout() == "Widget 10.00\nGadget 20.00"


def test_empty_document_is_empty():
    assert doc().layout() == ""
