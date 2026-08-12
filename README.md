# Assay

Confidence-gated invoice extraction. A model reads an invoice into a structured
record, every field carries a confidence score, and anything the model is not
sure about routes to a human instead of being accepted silently.

## Setup

Requires Python 3.12, [uv](https://docs.astral.sh/uv/), and Docker.

```bash
make dev    # venv, dependencies, .env with generated secrets, pre-commit hooks
make up     # postgres, redis, langfuse
make test
```

`make` on its own lists every target.

`make dev` writes `.env` if it is missing and tops it up if it already exists,
generating any secret that is still empty. It never overwrites a value you
already set — `.env` holds the DocILE token, which is not regenerable.
`DOCILE_TOKEN` is the one thing it cannot fill for you.

## Services

`make up` brings up six containers. Two are the application's:

| Service | Port | For |
|---|---|---|
| postgres 16 | 5432 | extraction results, review queue |
| redis 7 | 6379 | job queue (db 1) |
| langfuse | 3000 | trace and eval UI |

The other three — ClickHouse, MinIO, and a second Langfuse container — exist
only because Langfuse v4 needs them: it keeps traces in ClickHouse, event
payloads in S3 (MinIO standing in locally), and hands ingestion from its web
tier to a worker over Redis. `make up-core` skips all four Langfuse containers
and starts just Postgres and Redis, which is enough for everything except
tracing.

Langfuse provisions its org, project, API keys, and login from `.env` on first
boot, so tracing works immediately — log in at http://localhost:3000 with
`LANGFUSE_INIT_USER_EMAIL` and `LANGFUSE_INIT_USER_PASSWORD`.

Everything binds to localhost only, apart from the Langfuse UI.

## The schema

`assay.schema.invoice` defines the extraction target.

```python
from assay.schema import Invoice, invoice_json_schema

invoice_json_schema()   # -> dict, ready for vLLM's guided_json
```

**Every field is optional and defaults to None.** That is the load-bearing
property of the whole design. A constrained decoder can only emit what the
grammar allows, so a required non-nullable field leaves the model no way to say
"this invoice has no due date" — it must invent one. That turns an abstention
into a confident error, and a confident error is precisely what a
confidence-gated pipeline cannot catch: the fabricated value arrives with the
same high logprob as a correctly read one.

`invoice_json_schema()` is not just `model_json_schema()`. Four things differ,
each because the raw Pydantic output does not survive constrained decoding:

- **No regex lookahead.** Pydantic types `Decimal` with the pattern
  `^(?!^[-+.]*$)[+-]?0*\d*\.?\d*$`. vLLM's backends (xgrammar, outlines)
  compile patterns to finite automata, which cannot express lookahead, so the
  pattern fails to compile or is silently dropped.
- **Money is a string, not a number.** A JSON number reaches `Decimal` through
  a float, and floats do not round-trip decimal cents — a VAT total of 19.19
  comes back as `Decimal('19.190000000000001')`.
- **Dates carry a pattern, not `format: date`.** `format` is advisory; backends
  may ignore it, leaving an unconstrained string. The grammar enforces the
  shape and Pydantic rejects impossible dates like `2026-13-45`.
- **Every key is required, and every type still admits null.** The model must
  emit `"due_date": null` rather than omitting the key. An omitted key produces
  no tokens, and no tokens means nothing to score — so a silent omission would
  be invisible to the gate. Forcing the key gives every field a decision point
  with a logprob on it.

## Text extraction

```python
from assay.ingest import extract

doc = extract("00134dd365a24343b35b78c6")
doc.source            # "pdf" or "ocr"
doc.words[0].text     # "TELETIME"
doc.words[0].bbox     # (x0, y0, x1, y1), normalized to [0, 1], top-left origin
doc.text              # words joined in reading order
```

**About 31% of DocILE PDFs are scans with no text layer.** PyMuPDF returns
nothing for those, silently, so `extract()` reads the embedded text layer when
there is one and falls back to DocILE's pre-computed OCR when there is not.
Both paths emit the same `Word` records, so callers do not need to branch on
the source; `doc.source` reports which was used, and `Word.confidence` is
`None` for text-layer words since those characters are exact rather than
predicted.

Measured over the full `trainval` split (5,680 documents, 1.79M words): 69.2%
read from the text layer, 30.8% from OCR, no failures, ~14s single-threaded.

One PyMuPDF subtlety worth knowing if you touch the geometry: word boxes come
back in unrotated cropbox space while `page.rect` is rotation-adjusted, so on
`/Rotate 90` pages the two disagree and dividing by `page.rect` overflows
`[0, 1]`. `_pdf_words` maps boxes through `page.rotation_matrix` first.

## Layout

```
src/assay/
    ingest/       documents in, words out (PDF text layer, OCR fallback)
    extract/      words in, a candidate Invoice out (constrained decoding)
    validate/     arithmetic, format, and cross-field checks
    confidence/   per-field scores, and the gate that routes low-confidence work
    review/       human-in-the-loop correction of what the gate held back
    api/          HTTP surface
    schema/       the extraction target
eval/             accuracy and calibration harness
tests/            `make test` skips anything needing the dataset
notebooks/        exploration
docs/             design notes
```

`assay.extract` is the extraction *stage*. Reading words off a page is
ingestion, and lives in `assay.ingest`.

## Dataset

This project uses [DocILE](https://docile.rossum.ai/) (Document Information
Localization and Extraction Benchmark).

### 1. Get a token

Register at https://docile.rossum.ai/ to obtain a secret token, then set
`DOCILE_TOKEN` in `.env`.

`.env` is gitignored. Do not commit the token — the download script
interpolates it straight into the S3 URL path, so it is a live credential.

### 2. Download

```bash
set -a && source .env && set +a
./scripts/download_dataset.sh "$DOCILE_TOKEN" annotated-trainval data/docile --unzip
```

Data lands in `data/`, which is gitignored — it is far too large for git.

Sizes, as reported by the S3 bucket:

| Split | Size |
|---|---|
| `annotated-trainval` | 1.06 GB |
| `synthetic` | 3.19 GB |
| `unlabeled-annotations` | 0.30 GB |
| `unlabeled` | 94 chunks, very large |

**The script's `--help` is wrong about the first split.** It advertises
`labeled-trainval`, but no such object exists in the bucket — that name 404s.
The real key is `annotated-trainval`, matching the upstream README. The script
does not validate split names (it just interpolates them into the object name),
so passing the correct name works fine.

Run `./scripts/download_dataset.sh --help` for chunked downloads of the large
splits, and `--without-pdfs` to fetch pre-computed OCR only for `unlabeled`.

`scripts/download_dataset.sh` is vendored verbatim from
[rossumai/docile](https://github.com/rossumai/docile).
