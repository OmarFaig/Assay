# Changelog

Notable changes to Assay. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project has not cut
a release yet, so everything sits under Unreleased.

## [Unreleased]

### Added

- **`assay.extract`** — the extraction stage. `runner` assembles the prompt and
  calls vLLM with a JSON-schema-constrained grammar; `spans` maps every scalar in
  the returned JSON to its character span, keyed by path (`line_items[0].unit_price`);
  `evidence` attributes generated tokens to the field they spell, by character
  offset. The stage deliberately stops at evidence and does not compute a score.
- **`assay.confidence`** — per-field scoring over informative tokens, with `min`,
  `mean`, and geometric-mean aggregations, and `gate()` to split fields into
  accepted and held. Provisional: which aggregation is correct is settled by
  measuring calibration, not by argument.
- **`assay.review.provenance`** — locates an extracted value back on the page by
  fuzzy-matching against word boxes. Comparison is on alphanumerics only, so a
  printed `1,190.00` still matches an extracted `1190.00`.
- **`Document.layout()`** in `assay.ingest` — groups words into lines by vertical
  overlap and orders each line left to right. `Document.text` joins every word on
  a page with a single space, which flattens an invoice into one run-on line and
  destroys the table structure a text-only prompt depends on.
- `notebooks/probe_logprobs.py` and `notebooks/probe_analyse.py` — the experiment
  that established how vLLM reports logprobs under constrained decoding, with the
  response recorded to `notebooks/probe_response.json` as an offline test fixture.
- `notebooks/build_review.py` — renders an extraction review console: page image
  with confidence-tinted provenance boxes, a field ledger, per-field token strips
  distinguishing free from grammar-forced positions, and a live gate threshold.
- 27 tests covering span scanning, token attribution, line grouping, and scoring.
  All run offline against the recorded fixture; none need a GPU or the dataset.

### Changed

- Ruff no longer lints `notebooks/`. Those scripts are exploration, are not
  imported by the package, and embed HTML and CSS as string literals where a
  column limit means nothing.

### Fixed

- Trailing special tokens (`<|im_end|>`) appear in vLLM's logprobs list but are
  stripped from `message.content`. Left unhandled, every character offset after
  the response body shifts and attribution silently misaligns.

### Notes

- **vLLM reports post-mask logprobs**, using a finite `-9999.0` sentinel for a
  grammar-forbidden token rather than `-inf`. Two consequences: a position where
  the grammar allows one continuation reports p=1.0 and carries no information, so
  scoring must exclude it; and `math.isfinite` does not filter the sentinel, so any
  entropy or margin computed over alternatives must exclude it explicitly.
- **`guided_json` was removed in vLLM 0.27.1.** The replacement is
  `extra_body={"structured_outputs": {"json": schema}}`. `README.md` and
  `.env.example` still document the old spelling.
- **vLLM needs `VLLM_USE_FLASHINFER_SAMPLER=0`** on a machine without `ninja` and a
  CUDA toolkit matching torch's build. FlashInfer JIT-compiles its sampling kernels
  on first use; the fallback sampler costs nothing at `temperature=0`.

## 2026-08-12

### Added

- Project foundation: uv and `pyproject.toml`, ruff, pre-commit, a self-documenting
  `Makefile`, and pytest with a `data` marker so the suite runs on a fresh clone
  without the token-gated dataset.
- Docker stack: Postgres 16, Redis 7, and self-hosted Langfuse v4 with the
  ClickHouse, MinIO, and worker containers it requires. `scripts/init_env.sh`
  generates every secret; Langfuse provisions its org, project, and API keys on
  first boot.
- `assay.schema.invoice` — the extraction target. Every field is optional and
  nullable so a constrained decoder always has a legal path to abstain, and
  `invoice_json_schema()` hardens Pydantic's output for guided decoding: no regex
  lookahead, money as a string rather than a number, dates carrying an enforceable
  pattern instead of an advisory `format`, and every key required while every type
  still admits null.
- `docs/architecture.md` — why the pipeline is shaped the way it is.

## 2026-08-11

### Added

- `assay.ingest` — word-level text extraction reading the PDF text layer where one
  exists and falling back to DocILE's pre-computed OCR for the ~31% of the corpus
  that is scans. Both paths emit identical `Word` records with page-normalised
  coordinates. Measured over the full `trainval` split: 5,680 documents, 1.79M
  words, 69.2% text layer, 30.8% OCR, no failures.
- DocILE download tooling, vendored from
  [rossumai/docile](https://github.com/rossumai/docile), plus setup documentation.

### Fixed

- The download script's `--help` advertises a `labeled-trainval` split that does
  not exist in the bucket. The real key is `annotated-trainval`.
