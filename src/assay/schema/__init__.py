"""Target schemas for extraction."""

from assay.schema.invoice import Invoice, LineItem, invoice_json_schema

__all__ = ["Invoice", "LineItem", "invoice_json_schema"]
