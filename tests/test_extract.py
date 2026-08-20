"""Attribution runs entirely offline against a recorded vLLM response.

The GPU is not in the loop here on purpose: the bugs in this stage live in the
character-offset arithmetic, not in the HTTP call, and those are exactly the
bugs a fixture catches.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from assay.confidence import field_score, gate
from assay.extract import MASK_SENTINEL, from_response, tokens_from_response, value_spans

FIXTURE = Path(__file__).parent.parent / "notebooks" / "probe_response.json"


@pytest.fixture(scope="module")
def payload() -> dict:
    return json.loads(FIXTURE.read_text())


@pytest.fixture(scope="module")
def extraction(payload):
    return from_response(payload, doc_id="probe")


class TestValueSpans:
    def test_scalars_are_found_by_path(self):
        spans = value_spans('{"a": "x", "b": null, "c": 3}')
        assert set(spans) == {"a", "b", "c"}

    def test_span_includes_the_quotes(self):
        text = '{"a": "x"}'
        start, end = value_spans(text)["a"]
        assert text[start:end] == '"x"'

    def test_nested_paths_use_bracket_indices(self):
        spans = value_spans('{"items": [{"d": "one"}, {"d": "two"}]}')
        assert set(spans) == {"items[0].d", "items[1].d"}

    def test_containers_have_no_span_of_their_own(self):
        assert "items" not in value_spans('{"items": [1, 2]}')

    def test_escaped_quote_does_not_end_the_string(self):
        text = r'{"a": "x\"y", "b": 1}'
        start, end = value_spans(text)["a"]
        assert text[start:end] == r'"x\"y"'


class TestTokens:
    def test_trailing_special_token_is_dropped(self, payload):
        entries = payload["choices"][0]["logprobs"]["content"]
        content = payload["choices"][0]["message"]["content"]
        tokens = tokens_from_response(content, entries)
        # The chat endpoint strips <|im_end|> from content but still reports it.
        assert len(tokens) == len(entries) - 1
        assert "".join(t.text for t in tokens) == content

    def test_mismatched_stream_is_rejected(self):
        with pytest.raises(ValueError):
            tokens_from_response("abc", [{"token": "x", "logprob": 0.0}])

    def test_forced_position_is_not_informative(self):
        [token] = tokens_from_response(
            "-",
            [
                {
                    "token": "-",
                    "logprob": 0.0,
                    "top_logprobs": [
                        {"token": "-", "logprob": 0.0},
                        {"token": "!", "logprob": MASK_SENTINEL - 999},
                    ],
                }
            ],
        )
        assert not token.informative

    def test_free_position_is_informative(self):
        [token] = tokens_from_response(
            "5",
            [
                {
                    "token": "5",
                    "logprob": -0.1,
                    "top_logprobs": [
                        {"token": "5", "logprob": -0.1},
                        {"token": "6", "logprob": -2.3},
                    ],
                }
            ],
        )
        assert token.informative


class TestAttribution:
    def test_every_schema_field_gets_evidence(self, extraction):
        assert {"invoice_id", "due_date", "total_gross"} <= set(extraction.fields)
        assert "line_items[1].vat_rate" in extraction.fields

    def test_values_round_trip_into_the_model(self, extraction):
        assert str(extraction.invoice.total_gross) == "1884.75"
        assert extraction.invoice.due_date is None

    def test_field_text_matches_the_tokens_that_produced_it(self, extraction):
        for evidence in extraction.fields.values():
            spelled = "".join(t.text for t in evidence.tokens)
            assert evidence.text.strip('"') in spelled

    def test_date_separators_are_excluded_as_forced(self, extraction):
        issue = extraction.fields["issue_date"]
        # 2024-03-14 -> the two hyphens are pinned by the schema's date pattern.
        assert len(issue.tokens) - len(issue.informative_tokens) == 2

    def test_abstention_is_a_single_scored_token(self, extraction):
        due = extraction.fields["due_date"]
        assert due.value is None
        assert len(due.tokens) == 1
        assert due.informative_tokens


class TestConfidence:
    def test_near_coin_flip_abstention_is_held(self, extraction):
        # The document states no due date. The model chose null at p=0.56 --
        # correct, but not confidently, so the gate must not accept it.
        assert field_score(extraction.fields["due_date"]) == pytest.approx(0.5621, abs=1e-3)
        _, held = gate(extraction, threshold=0.85)
        assert "due_date" in held

    def test_confident_fields_are_accepted(self, extraction):
        accepted, _ = gate(extraction, threshold=0.85)
        assert "customer_vat_id" in accepted
        assert "issue_date" in accepted

    @pytest.mark.parametrize("method", ["min", "mean", "product"])
    def test_every_method_returns_a_probability(self, extraction, method):
        for evidence in extraction.fields.values():
            assert 0.0 <= field_score(evidence, method=method) <= 1.0

    def test_min_never_exceeds_mean(self, extraction):
        for evidence in extraction.fields.values():
            assert (
                field_score(evidence, method="min") <= field_score(evidence, method="mean") + 1e-9
            )

    def test_mask_sentinel_is_finite(self):
        # The trap: -9999 passes math.isfinite, so an -inf filter misses it.
        assert math.isfinite(MASK_SENTINEL)
