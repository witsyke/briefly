# briefly

Get an at-a-glance overview of the literature you're tracking for a
project: a sortable HTML table of every paper, one row each, down to
whatever fields matter to your project (priority, setting, technique,
...). Click through to a brief — much less than the paper, much more than
an abstract — to actually decide what's worth reading and what to read
first, before committing to the full text underneath.

Turns a directory of PDF papers into extracted Markdown (with figures),
config-driven briefs, and a small browsable HTML site linking both — using
`claude` as the extraction/briefing backend.

## Requirements

- [`claude`](https://claude.com/product/claude-code) CLI installed and authenticated.
- [`uv`](https://docs.astral.sh/uv/).

## Install

```
uv tool install git+https://github.com/witsyke/briefly@v0.1.0   # pinned (recommended)
uv tool install git+https://github.com/witsyke/briefly          # tracks main
```

This installs a `briefly` command on your `PATH`. No need to clone the
repo — run it from any directory of your own. The pinned form installs a
tagged release; the untagged form always installs whatever `main` happens
to be at that moment, and later `uv tool install --reinstall briefly` (or
`uv tool upgrade briefly`) will silently pick up wherever `main` has moved
to since.

To uninstall:

```
uv tool uninstall briefly
```

## Usage

```
mkdir my-project && cd my-project
mkdir literature   # put PDFs here
briefly
```

`literature/` (or whatever `--literature-dir` points at) is where
`briefly` looks for input: every `.pdf` file directly inside it is picked
up as one paper to process. It isn't created for you — make it and drop
your PDFs in before running.

Re-running `briefly` in the same directory only processes PDFs that are
new or previously failed — progress is tracked in a local sqlite file.

The first time you opt into brief creation, if no briefing config exists
yet, `briefly` will ask you a couple of questions (project name and
description) and write a starter one for you, then use it immediately.
Edit it later to change what fields future briefs cover — see
[Briefing config](#briefing-config) below.

## Options

| Flag | Default | |
|---|---|---|
| `--literature-dir` | `literature` | directory of input PDFs |
| `--extraction-dir` | `extractions` | directory for extracted Markdown + images |
| `--briefing-dir` | `briefs` | directory for generated briefs |
| `--site-dir` | `web` | directory for the generated HTML site |
| `--briefing-config` | `brief.yaml` | YAML config driving brief creation (see below) |
| `--database` | `briefly.sqlite3` | sqlite file tracking progress; re-running only processes new/failed PDFs |

## Briefing config

A brief's frontmatter and body sections are defined by you, not hardcoded
— `brief.yaml` (or whatever `--briefing-config` points at) describes them:

```yaml
project:
  name: My Project
  description: |
      A couple of sentences describing what you're working on, so the
      model can judge relevance/priority against it.

frontmatter:
  - field: tags
    description: 3-5 short topical tags for this paper, comma-separated
  - field: priority
    values: ["ignore", "low", "medium", "high"]
    description: priority to read this work given the project description

sections:
  - field: summary
    description: 4-5 sentence summary of the paper's core contribution
  - field: takeaways
    description: bullet list of most actionable takeaways for this project
```

`frontmatter` fields become the brief's YAML frontmatter (and a column in
the generated site's index table); `sections` fields each become a `##`
heading with the model's answer underneath. A field with `values` is
constrained to that exact list — anything else is rejected, not silently
accepted as free text.

This repo's own [`brief.yaml`](brief.yaml) is committed as a real,
fuller example — an orientation to copy and adapt for your own project,
not a schema to match exactly.
