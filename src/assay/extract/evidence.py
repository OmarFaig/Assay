"""Attributing generated tokens to the fields they produced.

The confidence gate scores fields, but vLLM returns a flat list of tokens. The
join between the two is character offsets: concatenating the token strings
reproduces the response exactly, so each token owns a `[start, end)` span, and a
field's tokens are those whose span overlaps the field's value span.

Nothing here collapses logprobs into a score. That is `assay.confidence`'s job,
and the choice between mean, min, and length-normalised product is still open
(`docs/architecture.md`) — it gets settled by measuring calibration, not by
picking one here. This module's contract is to preserve evidence losslessly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from assay.extract.spans import value_spans
from assay.schema import Invoice

# vLLM writes this for a token the grammar forbade, rather than -inf. It is a
# finite float, so `math.isfinite` will not filter it and an unguarded mean over
# alternatives silently becomes garbage.
MASK_SENTINEL = -9000.0


@dataclass(frozen=True, slots=True)
class Token:
    """One generated token and what else was legal at that position."""

    text: str
    logprob: float
    n_legal: int

    @property
    def informative(self) -> bool:
        """Whether the model actually made a choice here.

        Where the grammar admits exactly one continuation the reported
        probability is 1.0 by construction and says nothing about the model.
        Those positions are not only the keys and colons — the `-` separators
        inside a date pattern are forced too — so the test is on the legal set
        rather than on a list of structural characters.
        """
        return self.n_legal != 1


@dataclass(frozen=True, slots=True)
class FieldEvidence:
    """Everything the extraction stage knows about one field."""

    path: str
    value: Any
    text: str
    tokens: tuple[Token, ...]

    @property
    def informative_tokens(self) -> tuple[Token, ...]:
        return tuple(t for t in self.tokens if t.informative)


@dataclass(frozen=True, slots=True)
class Extraction:
    doc_id: str
    invoice: Invoice
    raw_json: str
    fields: dict[str, FieldEvidence]
    model: str
    finish_reason: str


def tokens_from_response(content: str, entries: list[dict[str, Any]]) -> list[Token]:
    """Parse vLLM's logprob entries, dropping anything past the visible text.

    The chat endpoint strips the end-of-turn marker from `message.content` but
    still reports it in the logprobs list, so the two disagree by one token.
    Trimming on cumulative length rather than on a hardcoded token name keeps
    this working for any special token a future chat template emits.
    """
    tokens: list[Token] = []
    position = 0
    for entry in entries:
        text = entry["token"]
        if position + len(text) > len(content):
            break
        alternatives = entry.get("top_logprobs") or []
        tokens.append(
            Token(
                text=text,
                logprob=entry["logprob"],
                # With no alternatives reported there is no way to tell a forced
                # position from a free one, so assume free — undercounting
                # forced tokens dilutes a score, miscounting free ones discards
                # real signal, and the first error is the safer one.
                n_legal=sum(a["logprob"] > MASK_SENTINEL for a in alternatives) or 2,
            )
        )
        position += len(text)

    if content[:position] != "".join(t.text for t in tokens):
        raise ValueError("token stream does not reproduce the response text")

    return tokens


def attribute(content: str, tokens: list[Token]) -> dict[str, FieldEvidence]:
    """Group tokens by the field whose value they spell."""
    parsed = json.loads(content)
    spans = value_spans(content)

    offsets: list[tuple[int, int]] = []
    position = 0
    for token in tokens:
        offsets.append((position, position + len(token.text)))
        position += len(token.text)

    fields: dict[str, FieldEvidence] = {}
    for path, (start, end) in spans.items():
        # Any character overlap claims the token. Boundary tokens such as
        # `.00",` straddle a value and the delimiter after it; assigning by
        # majority would drop the closing quote, which carries the model's
        # decision to stop reading the value.
        owned = tuple(t for t, (s, e) in zip(tokens, offsets, strict=True) if s < end and e > start)
        fields[path] = FieldEvidence(
            path=path, value=_lookup(parsed, path), text=content[start:end], tokens=owned
        )
    return fields


def _lookup(parsed: Any, path: str) -> Any:
    node = parsed
    for part in path.split("."):
        name, _, indices = part.partition("[")
        node = node[name]
        for index in indices.rstrip("]").split("][") if indices else ():
            node = node[int(index)]
    return node
