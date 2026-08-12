"""Assay — confidence-gated invoice extraction.

The pipeline runs in stages, one subpackage each:

    ingest      documents in, words out (PDF text layer, OCR fallback)
    extract     words in, a candidate `Invoice` out (constrained decoding)
    validate    arithmetic, format, and cross-field checks on that candidate
    confidence  per-field scores, and the gate that routes low-confidence work
    review      human-in-the-loop correction of whatever the gate held back
    api         HTTP surface over the above

`assay.extract` is the extraction *stage*. Reading words off a page is
ingestion and lives in `assay.ingest`.
"""

from assay.schema.invoice import Invoice, LineItem, invoice_json_schema

__all__ = ["Invoice", "LineItem", "invoice_json_schema"]
