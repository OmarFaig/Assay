# Assay

## Setup

Requires Python 3.12.

```bash
python3 -m venv venv
source venv/bin/activate
```

Dependencies are not pinned yet. Once they are, install them with:

```bash
pip install -r requirements.txt
```

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
