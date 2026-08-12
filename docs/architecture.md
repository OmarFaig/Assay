# Architecture

Notes on why the pipeline is shaped the way it is. Written as the foundation
went in; stages below the schema are not built yet.

## The premise

An extraction model that is right 95% of the time is not usable unsupervised
for invoices, because the 5% is indistinguishable from the 95% at the point of
use. Someone still reads every document to find the bad ones, and the model has
saved nothing.

What makes it usable is a reliable ordering: if the pipeline can rank its own
output by how likely it is to be wrong, a threshold turns one accuracy number
into two useful populations — a high-confidence slice that can post without
review, and a remainder that goes to a human. The product question stops being
"how accurate is the model" and becomes "how much of the volume clears the bar
at an acceptable error rate". Calibration matters more than raw accuracy.

Everything below follows from needing that ordering to be trustworthy.

## Stages

```
ingest  ->  extract  ->  validate  ->  confidence  ->  review
```

**ingest** turns a document into words with page-normalized coordinates,
reading the PDF text layer where there is one and falling back to DocILE's
pre-computed OCR for the ~31% of the corpus that is scans. Both paths produce
identical `Word` records so nothing downstream branches on the source. OCR
words carry a per-word confidence; text-layer words do not, because those
characters are exact rather than predicted — a distinction the confidence stage
will need.

**extract** assembles the prompt and calls vLLM with `guided_json`, getting
back something that parses as an `Invoice` by construction. Constrained
decoding is what makes per-field confidence tractable: the grammar pins down
where each field's tokens start and end, so a logprob can be attributed to a
specific field rather than to the response as a whole.

**validate** applies checks that need no model: does `total_net + total_vat`
equal `total_gross`, do the line items sum to the net, is the IBAN checksum
valid, is the due date after the issue date. These are independent evidence
about correctness, and cheap. A field can be high-logprob and still fail
arithmetic — those cases are the interesting ones.

**confidence** combines the model's token probabilities with the validation
results into a per-field score, then applies the gate. Two signals with
different failure modes: logprobs catch the model being unsure, arithmetic
catches it being confidently wrong in a way that contradicts the rest of the
document.

**review** is where gated fields go, with the source document, the bounding
boxes the value came from, and the reason it was held back. Corrections here
are the eval set growing.

## Why every schema field is nullable

The single most important design decision, and the easiest to undo by accident.

A constrained decoder can only emit what the grammar permits. If `due_date` is
required and non-nullable, then for an invoice with no due date the model has
no legal path to say so — the grammar forces a date-shaped token sequence, and
it produces one. That is not a model failure, it is the schema removing the
correct answer from the option set.

The cost lands specifically on the confidence gate. A fabricated value produced
under grammar pressure does not look uncertain: the tokens are constrained to a
narrow set, so their probabilities are high. The gate sees a confident field,
passes it, and the error goes out unreviewed — the exact failure mode the
pipeline exists to prevent. An abstention converted into a confident error is
strictly worse than an abstention.

So: every field optional, defaulting to None, and `null` reachable in the
exported JSON Schema.

## Why every key is required anyway

The exported schema marks all properties required while keeping their types
nullable. This looks like a contradiction and is not.

Optional-and-omittable and optional-and-explicitly-null differ in one way that
matters here: an omitted key generates no tokens. No tokens, nothing to score,
and the gate cannot distinguish "the model considered this field and found
nothing" from "the field never came up". Forcing the key means the model
reaches a decision point for every field and commits, with a logprob attached
to the commitment. `"due_date": null` is a measurement; a missing `due_date` is
an absence of one.

The Pydantic model stays permissive — nothing is required there — so partial
records from other sources (a half-finished review, an older run) still parse.
Only the generation-time schema is strict.

## Open questions

- How to aggregate per-token logprobs into one per-field score. Mean, min, and
  product all behave differently for multi-token values, and long strings like
  `vendor_address` will need normalizing against short ones like `currency`.
- Whether line items need their own gate. A table is right or wrong as a unit
  more often than cell by cell, and row-level confidence may be the better
  granularity.
- Whether the two confidence signals combine as a learned model or a hand-set
  rule. A rule is explainable to whoever runs the review queue, which has
  value beyond accuracy.
- Where the threshold goes. It is a business decision (cost of a missed error
  vs. cost of a review) and should be calibrated on held-out data, not picked.
