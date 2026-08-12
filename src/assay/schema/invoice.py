"""The invoice target schema.

Every field is Optional and defaults to None. This is deliberate and it is the
single most important property of this module: the model must always have a
legal token path to express "not present". A required field with no nullable
branch leaves the constrained decoder no way to abstain, so when a value is
genuinely absent from the document the grammar forces it to invent one — which
converts an abstention into a confident error. Confident errors are exactly
what a confidence-gated pipeline cannot detect, because the fabricated value
gets the same high logprob as a correctly read one. Keep every field nullable.

Dates are `datetime.date`, money and quantities are `Decimal`. Decimal rather
than float because invoice arithmetic is checked for consistency downstream
(line items summing to totals, net + VAT == gross), and binary floats do not
round-trip decimal cents.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema

# Both grammar-safe overrides below exist because what Pydantic emits by
# default does not survive a constrained decoder.
#
# Pydantic types `Decimal` as `number | string`, where the string branch
# carries the pattern `^(?!^[-+.]*$)[+-]?0*\d*\.?\d*$`. That leading `(?!...)`
# is a negative lookahead, and vLLM's guided-decoding backends (xgrammar,
# outlines) compile patterns into finite automata, which have no lookahead —
# so the pattern either fails to compile or is silently dropped.
#
# Dropping the `number` branch as well is the deliberate part. A JSON number
# reaching Decimal through `json.loads` becomes a float first, and floats do
# not round-trip decimal cents: a VAT total of 19.19 comes back as
# Decimal('19.190000000000001'). Emitting money as a string keeps the digits
# the model actually chose all the way into Decimal, exactly. This constrains
# generation only — in Python `Invoice(total_net=12.5)` still works, since the
# annotation is a plain Decimal.
_DECIMAL_JSON_SCHEMA = {"type": "string", "pattern": r"^-?\d{1,12}(\.\d{1,6})?$"}

# `datetime.date` emits `{"type": "string", "format": "date"}`, and `format` is
# an annotation rather than a constraint — backends are free to ignore it, and
# a plain unconstrained string is what the grammar then allows. The pattern
# says the same thing in a way an automaton can enforce. It admits impossible
# dates like 2026-13-45; Pydantic rejects those on parse, which is the right
# division of labour (the grammar keeps the shape, the validator keeps the
# semantics).
_DATE_JSON_SCHEMA = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"}

DecimalValue = Annotated[Decimal, WithJsonSchema(_DECIMAL_JSON_SCHEMA)]
DateValue = Annotated[datetime.date, WithJsonSchema(_DATE_JSON_SCHEMA)]


class LineItem(BaseModel):
    """A single billed row.

    Line items are the noisiest part of an invoice: tables wrap across pages,
    columns get merged, and a row may carry only a description with no price.
    Each field stays independently nullable so a partially-read row degrades
    into a partially-populated item rather than a fabricated one.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    description: str | None = Field(
        default=None, description="Free-text description of the goods or service billed."
    )
    quantity: DecimalValue | None = Field(
        default=None, description="Number of units billed. May be fractional (e.g. hours)."
    )
    unit_price: DecimalValue | None = Field(
        default=None, description="Price of one unit, excluding VAT."
    )
    line_net: DecimalValue | None = Field(
        default=None, description="Line total excluding VAT, normally quantity * unit_price."
    )
    vat_rate: DecimalValue | None = Field(
        default=None,
        description="VAT rate applied to this line, as a percentage (e.g. 19 for 19%).",
    )


class Invoice(BaseModel):
    """A single invoice document.

    Field order is meaningful: constrained decoding emits object keys in schema
    order, so header identifiers come first, then parties, then money, and the
    line-item table last — the model reads the document roughly in that order
    and each earlier field conditions the ones after it.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    invoice_id: str | None = Field(
        default=None, description="The invoice number as printed on the document."
    )
    issue_date: DateValue | None = Field(
        default=None, description="Date the invoice was issued, as ISO 8601 (YYYY-MM-DD)."
    )
    due_date: DateValue | None = Field(
        default=None, description="Payment due date, as ISO 8601 (YYYY-MM-DD)."
    )

    vendor_name: str | None = Field(
        default=None, description="Legal name of the party issuing the invoice."
    )
    vendor_address: str | None = Field(
        default=None, description="Postal address of the issuing party, as a single string."
    )
    vendor_vat_id: str | None = Field(
        default=None, description="VAT/tax identifier of the issuing party."
    )

    customer_name: str | None = Field(
        default=None, description="Legal name of the party being billed."
    )
    customer_vat_id: str | None = Field(
        default=None, description="VAT/tax identifier of the party being billed."
    )

    currency: str | None = Field(
        default=None, description="ISO 4217 currency code, e.g. EUR, USD, CZK."
    )
    total_net: DecimalValue | None = Field(default=None, description="Total excluding VAT.")
    total_vat: DecimalValue | None = Field(default=None, description="Total VAT charged.")
    total_gross: DecimalValue | None = Field(
        default=None, description="Total including VAT — the amount payable."
    )

    payment_iban: str | None = Field(
        default=None, description="IBAN the payment should be sent to."
    )

    # Defaults to empty rather than None: "no line items were read" and "this
    # invoice has no line items" are the same downstream, and an empty list
    # keeps every consumer's iteration unconditional.
    line_items: list[LineItem] = Field(
        default_factory=list, description="Billed rows, in the order they appear on the document."
    )


def invoice_json_schema(*, require_all_keys: bool = True) -> dict[str, Any]:
    """The `Invoice` schema in the form vLLM's `guided_json` expects.

    vLLM takes a plain JSON Schema dict, which is what Pydantic emits, with
    three adjustments made here (a fourth, replacing the lookahead-bearing
    Decimal pattern and the unenforceable date `format`, happens at the field
    level — see `_DECIMAL_JSON_SCHEMA` and `_DATE_JSON_SCHEMA` above):

    `additionalProperties: false` everywhere, so the grammar cannot spend
    tokens on invented keys. Pydantic emits this for the models themselves
    (both set `extra="forbid"`), but this walks the whole document so nested
    and generated subschemas are covered too.

    `require_all_keys` marks every property required. This reads backwards
    against a schema whose entire point is that nothing is mandatory, so to be
    precise about what differs: the *type* of every field still admits null, so
    the abstention path stays open. What changes is that the model must emit
    the key and then choose a value — `"due_date": null` instead of omitting
    `due_date` entirely. That distinction matters here because the pipeline
    gates on per-field confidence, and an omitted key produces no tokens to
    score, so a silent omission is indistinguishable from a field that was
    never in the schema. Forcing the key gives every field a decision point
    with a logprob attached, and "the model explicitly chose null" is a signal
    worth having. Pass False for the plain Pydantic-shaped schema.

    `title` and `default` are stripped. Both are ignored by the grammar, and
    the titles are just field names with the underscores swapped for spaces,
    so they are pure weight in a schema that often gets pasted into the prompt
    alongside the request. `default` in particular would be actively
    misleading once every key is required.
    """
    schema = Invoice.model_json_schema(mode="validation")
    _harden(schema, require_all_keys=require_all_keys)
    return schema


def _harden(node: Any, *, require_all_keys: bool) -> None:
    """Recursively apply the guided-decoding adjustments in place."""
    if isinstance(node, list):
        for item in node:
            _harden(item, require_all_keys=require_all_keys)
        return

    if not isinstance(node, dict):
        return

    node.pop("title", None)
    node.pop("default", None)

    properties = node.get("properties")
    if isinstance(properties, dict):
        node.setdefault("additionalProperties", False)
        if require_all_keys:
            node["required"] = list(properties)

    for value in node.values():
        _harden(value, require_all_keys=require_all_keys)
