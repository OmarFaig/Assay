"""Probe: does vLLM report pre-mask or post-mask logprobs under constrained decoding?

The confidence gate scores token logprobs. If vLLM renormalizes probabilities over
only the grammar-legal tokens, then a position where the grammar permits exactly one
continuation reports p=1.0 regardless of what the model believed — and any score that
averages such positions in is biased toward "confident". This finds out which we have.

Run with the vLLM server up:  uv run python notebooks/probe_logprobs.py
"""

from __future__ import annotations

import json
import math
import os
import re

from openai import OpenAI

from assay.schema import invoice_json_schema

BASE_URL = os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1")
MODEL = os.environ.get("VLLM_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct")

# Deliberately tiny and hand-written: fast, reproducible, and wrong answers are
# obvious by eye. Note there is no due date and no customer VAT id — those are the
# fields where we want to see the model reach for `null`.
DOC = """\
TELETIME AG
Hauptstrasse 12, 8001 Zurich

INVOICE  Nr. 2024-0815
Date: 2024-03-14

Consulting services    10 h   150.00    1500.00
Licence fee             1     250.00     250.00

Net              1750.00
VAT 7.7%          134.75
Total CHF        1884.75
"""

schema = invoice_json_schema()

PROMPT = (
    "Extract the invoice into JSON matching this schema. "
    "Use null for anything not present in the document.\n\n"
    f"<schema>\n{json.dumps(schema)}\n</schema>\n\n"
    f"<document>\n{DOC}</document>"
)

client = OpenAI(base_url=BASE_URL, api_key="EMPTY")

resp = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": PROMPT}],
    temperature=0,
    max_tokens=1024,
    logprobs=True,
    top_logprobs=5,
    extra_body={"structured_outputs": {"json": schema, "disable_any_whitespace": True}},
)

choice = resp.choices[0]
content = choice.message.content
toks = choice.logprobs.content

print("=" * 78)
print(f"finish_reason : {choice.finish_reason}")
print(f"tokens        : {len(toks)}")

# Tripwire 1 (brief trap 3): offsets are only trustworthy if this holds.
rebuilt = "".join(t.token for t in toks)
print(f"rebuild == content : {rebuilt == content}")

# Tripwire 3 (brief trap 8): did the decimal pattern survive into the grammar?
parsed = json.loads(content)
money = [v for k, v in parsed.items() if k.startswith(("total_", "amount")) and v is not None]
bad = [m for m in money if not re.fullmatch(r"-?\d{1,12}(\.\d{1,6})?", str(m))]
print(f"money fields   : {money}")
print(f"pattern violations : {bad or 'none'}")
print("=" * 78)
print(content)
print("=" * 78)

# Per-token dump. `p` is the chosen token's probability; `top5` is how much of the
# probability mass the five reported alternatives account for. Under post-mask
# renormalisation a grammar-forced position concentrates all mass in top-1, so
# top5 sums to ~1.0. Pre-mask, mass is spread over the full vocab and it will not.
print(f"{'idx':>4}  {'token':<14} {'logprob':>9} {'p':>7} {'top5':>7}  alternatives")
print("-" * 78)
for i, t in enumerate(toks):
    p = math.exp(t.logprob)
    alts = t.top_logprobs or []
    top5 = sum(math.exp(a.logprob) for a in alts)
    shown = " ".join(f"{a.token!r}={math.exp(a.logprob):.3f}" for a in alts[:5])
    print(f"{i:>4}  {t.token!r:<14} {t.logprob:>9.4f} {p:>7.4f} {top5:>7.4f}  {shown}")
