"""Tests for the invoice schema.

The bulk of these guard the abstention path. It is easy to "tidy" a schema
into something that no longer lets the model say "not present" — adding a
required field, tightening a type, dropping a null branch — and the failure
that causes is silent and expensive, so it gets asserted rather than trusted.
"""

from __future__ import annotations

import datetime
import json
import re
from decimal import Decimal

import pytest

from assay.schema.invoice import Invoice, LineItem, invoice_json_schema

# Matches any regex lookahead/lookbehind construct.
LOOKAROUND = re.compile(r"\(\?[=!<]")


def test_empty_invoice_is_valid():
    """The whole point: a document yielding nothing at all must still parse."""
    invoice = Invoice()
    assert invoice.invoice_id is None
    assert invoice.total_gross is None
    assert invoice.line_items == []


def test_empty_line_item_is_valid():
    assert LineItem().description is None


def test_every_field_is_optional():
    for name, field in Invoice.model_fields.items():
        assert not field.is_required(), f"Invoice.{name} is required; it must be optional"
    for name, field in LineItem.model_fields.items():
        assert not field.is_required(), f"LineItem.{name} is required; it must be optional"


def test_explicit_nulls_parse():
    """The model emits `null`, not an omitted key — both must land on None."""
    payload = {name: None for name in Invoice.model_fields if name != "line_items"}
    payload["line_items"] = [dict.fromkeys(LineItem.model_fields)]

    invoice = Invoice.model_validate(payload)

    assert invoice.issue_date is None
    assert invoice.total_net is None
    assert len(invoice.line_items) == 1
    assert invoice.line_items[0].quantity is None


def test_money_round_trips_exactly_from_string():
    """Decimal cents survive; a float path would give 19.190000000000001."""
    invoice = Invoice.model_validate({"total_vat": "19.19", "total_gross": "119.19"})
    assert invoice.total_vat == Decimal("19.19")
    assert str(invoice.total_gross) == "119.19"


def test_dates_parse_from_iso():
    invoice = Invoice.model_validate({"issue_date": "2026-03-14"})
    assert invoice.issue_date == datetime.date(2026, 3, 14)


def test_impossible_date_is_rejected():
    """The grammar allows the shape; the validator rejects the semantics."""
    with pytest.raises(ValueError):
        Invoice.model_validate({"issue_date": "2026-13-45"})


def test_unknown_fields_are_rejected():
    with pytest.raises(ValueError):
        Invoice.model_validate({"vendor_iban": "DE89"})


class TestJsonSchema:
    def test_every_property_admits_null(self):
        schema = invoice_json_schema()
        for holder in (schema, schema["$defs"]["LineItem"]):
            for name, prop in holder["properties"].items():
                if name == "line_items":
                    continue  # empty list is the abstention, not null
                branches = [b.get("type") for b in prop["anyOf"]]
                assert "null" in branches, f"{name} has no null branch: {prop}"

    def test_all_keys_required_by_default(self):
        schema = invoice_json_schema()
        assert schema["required"] == list(schema["properties"])
        line_item = schema["$defs"]["LineItem"]
        assert line_item["required"] == list(line_item["properties"])

    def test_require_all_keys_can_be_disabled(self):
        schema = invoice_json_schema(require_all_keys=False)
        assert "required" not in schema or schema["required"] == []

    def test_additional_properties_forbidden_everywhere(self):
        schema = invoice_json_schema()
        assert schema["additionalProperties"] is False
        assert schema["$defs"]["LineItem"]["additionalProperties"] is False

    def test_no_regex_lookaround(self):
        """xgrammar and outlines compile patterns to finite automata, which
        cannot express lookaround. Pydantic's stock Decimal pattern has a
        negative lookahead, so this fails if the override is ever dropped."""
        blob = json.dumps(invoice_json_schema())
        assert not LOOKAROUND.search(blob)

    def test_dates_carry_an_enforceable_pattern(self):
        """`format: date` is advisory; backends may ignore it."""
        issue_date = invoice_json_schema()["properties"]["issue_date"]
        string_branch = next(b for b in issue_date["anyOf"] if b.get("type") == "string")
        assert "pattern" in string_branch
        assert re.fullmatch(string_branch["pattern"], "2026-03-14")

    def test_money_is_a_string_not_a_number(self):
        """A JSON number would reach Decimal via float and lose cents."""
        total = invoice_json_schema()["properties"]["total_gross"]
        assert {b.get("type") for b in total["anyOf"]} == {"string", "null"}

    def test_field_order_is_preserved(self):
        """Constrained decoding emits keys in schema order, so the order the
        fields are declared in is part of the prompt design."""
        assert list(invoice_json_schema()["properties"]) == list(Invoice.model_fields)

    def test_schema_is_json_serialisable(self):
        """vLLM ships it over the wire as JSON."""
        assert json.loads(json.dumps(invoice_json_schema()))

    def test_generated_output_validates(self):
        """A plausible constrained-decoder response, parsed back."""
        completion = json.dumps(
            {
                "invoice_id": "INV-2026-0042",
                "issue_date": "2026-03-14",
                "due_date": None,
                "vendor_name": "Teletime s.r.o.",
                "vendor_address": None,
                "vendor_vat_id": "CZ12345678",
                "customer_name": "Acme GmbH",
                "customer_vat_id": None,
                "currency": "EUR",
                "total_net": "100.00",
                "total_vat": "19.00",
                "total_gross": "119.00",
                "payment_iban": None,
                "line_items": [
                    {
                        "description": "Consulting",
                        "quantity": "2.5",
                        "unit_price": "40.00",
                        "line_net": "100.00",
                        "vat_rate": "19",
                    }
                ],
            }
        )

        invoice = Invoice.model_validate_json(completion)

        assert invoice.invoice_id == "INV-2026-0042"
        assert invoice.due_date is None
        assert invoice.total_gross == Decimal("119.00")
        assert invoice.line_items[0].quantity == Decimal("2.5")
