"""Second pass on the probe: diagnose the rebuild mismatch and settle pre/post-mask."""

from __future__ import annotations

import json
import math
import os

from openai import OpenAI

from assay.schema import invoice_json_schema

FIXTURE = "notebooks/probe_response.json"

if os.path.exists(FIXTURE):
    raw = json.load(open(FIXTURE))
else:
    from probe_logprobs import DOC, PROMPT  # noqa: F401  (re-uses the same prompt)

    client = OpenAI(base_url="http://localhost:8000/v1", api_key="EMPTY")
    resp = client.chat.completions.create(
        model="Qwen/Qwen2.5-VL-7B-Instruct",
        messages=[{"role": "user", "content": PROMPT}],
        temperature=0,
        max_tokens=1024,
        logprobs=True,
        top_logprobs=5,
        extra_body={"structured_outputs": {"json": invoice_json_schema()}},
    )
    raw = resp.model_dump()
    json.dump(raw, open(FIXTURE, "w"), indent=1)

choice = raw["choices"][0]
content = choice["message"]["content"]
toks = choice["logprobs"]["content"]
rebuilt = "".join(t["token"] for t in toks)

print("### 1. rebuild mismatch")
print(f"content len={len(content)}  rebuilt len={len(rebuilt)}  equal={content == rebuilt}")
for i, (a, b) in enumerate(zip(content, rebuilt)):
    if a != b:
        print(f"first divergence at char {i}: content={a!r} rebuilt={b!r}")
        print(f"  content[{i - 20}:{i + 20}] = {content[max(0, i - 20) : i + 20]!r}")
        print(f"  rebuilt[{i - 20}:{i + 20}] = {rebuilt[max(0, i - 20) : i + 20]!r}")
        break
else:
    short, long_ = sorted((content, rebuilt), key=len)
    print(f"common prefix identical; extra tail = {long_[len(short) :]!r}")

print()
print("### 2. are any alternatives -inf (i.e. grammar-masked)?")
all_alts = [a["logprob"] for t in toks for a in t.get("top_logprobs", [])]
finite = [x for x in all_alts if math.isfinite(x)]
print(
    f"alternatives total={len(all_alts)}  finite={len(finite)}  -inf={len(all_alts) - len(finite)}"
)
print(f"min finite alternative logprob = {min(finite):.3f}  (=p {math.exp(min(finite)):.3e})")

print()
print("### 3. illegal-token check at grammar-forced positions")
print("Inside a key name only one continuation is legal. If illegal tokens appear")
print("with finite logprobs, we are seeing the model's pre-mask distribution.\n")
for i in (3, 4, 27, 30):
    t = toks[i]
    alts = " ".join(f"{a['token']!r}={a['logprob']:.2f}" for a in t["top_logprobs"])
    print(f"  tok {i:>3} chose {t['token']!r:<10} -> {alts}")

print()
print("### 4. the abstention decision points (null vs opening quote)")
for i, t in enumerate(toks):
    names = {a["token"].strip() for a in t.get("top_logprobs", [])}
    if {'"', "null"} <= names or ("null" in names and '"' in names):
        alts = " ".join(
            f"{a['token']!r}={math.exp(a['logprob']):.4f}" for a in t["top_logprobs"][:3]
        )
        print(f"  tok {i:>3} chose {t['token']!r:<8} p={math.exp(t['logprob']):.4f}  {alts}")
