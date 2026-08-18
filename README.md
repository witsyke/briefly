# briefly

Extracts text and figures from PDF papers into Markdown, using `claude` as
the extraction backend.

## Requirements

- [`claude`](https://claude.com/product/claude-code) CLI installed and authenticated.
- [`uv`](https://docs.astral.sh/uv/).

## Usage

```
uv run briefly --literature-dir <pdf-dir> --output-dir <output-dir>
```

Put PDFs in `<pdf-dir>`, run the command, get one `.md` file per PDF (with
extracted images) in `<output-dir>`.

## Options

| Flag | Default | |
|---|---|---|
| `--literature-dir` | `literature` | directory of input PDFs |
| `--output-dir` | `extractions` | directory for output Markdown + images |
| `--database` | `briefly.sqlite3` | sqlite file tracking progress; re-running only processes new/failed PDFs |
