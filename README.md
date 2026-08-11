# Assay

## Setup

Requires Python 3.12.

```bash
python3 -m venv venv
source venv/bin/activate
```

```bash
pip install -r requirements.txt
```

## Text extraction

```python
from assay import extract

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

## Dataset

This project uses [DocILE](https://docile.rossum.ai/) (Document Information
Localization and Extraction Benchmark).

### 1. Get a token

Register at https://docile.rossum.ai/ to obtain a secret token, then:

```bash
cp .env.example .env
# edit .env and set DOCILE_TOKEN
```

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
