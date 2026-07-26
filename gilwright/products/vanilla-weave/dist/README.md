# ragready

A small, dependency-free Python tool that checks whether a markdown document
is structured well enough to chunk and embed cleanly for retrieval-augmented
generation (RAG). Point it at a file or a directory of `.md` files and it
tells you, section by section, what's missing.

## Why

RAG pipelines split documents into chunks and embed each chunk separately.
A chunk that assumes the reader just read the previous paragraph ("as
discussed above...") retrieves badly on its own. A section with no stable
anchor is hard to cite. A document with no declared source is hard to trust.
`ragready` catches these problems before you embed anything, instead of
after your retrieval quality quietly degrades.

## Install

No install step — it's two files with no external dependencies (Python 3.10+,
standard library only).

```
python ragready.py --help
```

## Usage

```
python ragready.py mydoc.md
python ragready.py docs/ --json
python ragready.py docs/ --verbose      # show passing checks too
python ragready.py docs/ --strict       # back-reference warnings become failures
```

Exit codes: `0` everything passed, `1` at least one document failed, `2` a
hard error (bad path, unreadable file).

## What it checks

Each document needs YAML frontmatter with `ragready_version`, `doc_id`, and
`title` (recommended: `doc_anchor`, `summary`, `domain`, `tags`, `authority`).
Within the body, `ragready` checks, per section:

- **Frontmatter** — required and recommended fields present
- **Scaffold** — the document actually has headers/sections
- **Anchors** — every header has a unique `{#anchor}` id
- **Atomicity** — flags likely back-references ("as discussed above", "see
  earlier") that make a chunk depend on reading order
- **Cross-references** — `⟨ANCHOR name⟩` references resolve to a real anchor
  (or a declared external composition target)
- **Block type** — each section declares `[block: type]` from a known set
  (`concept`, `procedure`, `spec`, `code`, `slm`, `daemon`, `corpus`, `note`,
  `glyph` — extendable via a profile file)
- **Density** — flags sections that look too thin (<30 words) or too long
  (>80 lines) to make a good chunk
- **Provenance** — flags sections with no `[source: ...]` tag
- **Composability** — checks `[fuses-with: ...]` tags against a frontmatter
  `composes_with` list
- **Document-level** — unclosed HTML comments, unclosed code fences

See `example.md` in this directory for a document that passes cleanly, and
read its frontmatter/tags to see the expected shape.

## Optional: a profile file

Drop a `ragready.profile.yaml` next to your docs (or in a parent directory)
to add project-specific block types:

```yaml
block_types:
  - id: faq
  - id: changelog
```

`ragready` walks up from the target path looking for this file automatically.

## License

MIT — see `LICENSE`.
