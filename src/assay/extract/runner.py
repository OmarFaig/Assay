"""Prompt assembly and the constrained-decoding call.

The client is a parameter rather than a module-level singleton so the attribution
path — the part with real bugs in it — can be tested against a recorded response
without a GPU in the loop.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

from assay.extract.evidence import Extraction, attribute, tokens_from_response
from assay.schema import Invoice, invoice_json_schema

# The schema is sent in the prompt as well as enforced by the grammar, because
# the two do different jobs. The grammar constrains shape; it will happily let
# the model put the gross total in `total_net`. Only the field descriptions say
# what each name means, and they are inert unless the model reads them.
INSTRUCTIONS = (
    "You are extracting structured data from an invoice.\n"
    "Read the document and fill in the schema below.\n\n"
    "Use null for any field the document does not state. Do not guess, do not "
    "infer a value from a related one, and do not carry a value over from a "
    "similar field. A field that is genuinely absent must be null.\n\n"
    "Copy values exactly as printed, without reformatting, except dates, which "
    "must be written as YYYY-MM-DD."
)


class ChatClient(Protocol):
    """The slice of the OpenAI client this module uses."""

    @property
    def chat(self) -> Any: ...


def client_from_env() -> ChatClient:
    """An OpenAI client pointed at the local vLLM server.

    Nothing leaves the machine: vLLM speaks the OpenAI wire format, so the
    official client library works against it unchanged. `api_key` is a required
    argument that vLLM ignores.
    """
    from openai import OpenAI

    return OpenAI(
        base_url=os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1"),
        api_key=os.environ.get("VLLM_API_KEY", "EMPTY"),
    )


def build_prompt(document_text: str, schema: dict[str, Any] | None = None) -> str:
    schema = invoice_json_schema() if schema is None else schema
    return (
        f"{INSTRUCTIONS}\n\n"
        f"<schema>\n{json.dumps(schema)}\n</schema>\n\n"
        f"<document>\n{document_text}\n</document>"
    )


def extract_invoice(
    document_text: str,
    *,
    client: ChatClient,
    model: str | None = None,
    doc_id: str = "",
    max_tokens: int = 2048,
) -> Extraction:
    """Run one document through constrained decoding and keep the evidence."""
    model = model or os.environ.get("VLLM_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct")
    schema = invoice_json_schema()

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": build_prompt(document_text, schema)}],
        # Greedy. Extraction is not a creative task, and a reproducible output is
        # what makes one eval run comparable to the last.
        temperature=0,
        max_tokens=max_tokens,
        logprobs=True,
        # The alternatives are what make a forced position detectable — the
        # chosen token's own logprob cannot distinguish "certain" from "was the
        # only option". Five is enough to see whether a second option existed.
        top_logprobs=5,
        extra_body={"structured_outputs": {"json": schema}},
    )
    return from_response(response.model_dump(), doc_id=doc_id, model=model)


def from_response(payload: dict[str, Any], *, doc_id: str = "", model: str = "") -> Extraction:
    """Build an `Extraction` from a raw response dict.

    Split out from `extract_invoice` so a recorded response replays offline.
    """
    choice = payload["choices"][0]
    content = choice["message"]["content"]

    # The grammar only guarantees valid JSON if generation ran to completion.
    # Hitting the token cap leaves a prefix that parses as nothing, which is
    # worth failing loudly on rather than burying in a parse error.
    if choice["finish_reason"] == "length":
        raise ValueError(f"generation truncated at {max_tokens_of(payload)} tokens")

    tokens = tokens_from_response(content, choice["logprobs"]["content"])
    return Extraction(
        doc_id=doc_id,
        invoice=Invoice.model_validate_json(content),
        raw_json=content,
        fields=attribute(content, tokens),
        model=model or payload.get("model", ""),
        finish_reason=choice["finish_reason"],
    )


def max_tokens_of(payload: dict[str, Any]) -> int:
    return (payload.get("usage") or {}).get("completion_tokens", -1)
