---
ragready_version: 1
doc_id: example-001
title: Example RAG-Ready Document
doc_anchor: example-001
summary: A minimal document that passes every ragready check, for reference.
domain: docs
tags: [example, demo]
authority: internal
---

# Example RAG-Ready Document {#doc-root}

[block: concept]
[source: internal authoring guide]

This document exists to show the shape a markdown file needs for `ragready.py`
to pass it cleanly: YAML frontmatter with the required fields, headers with
explicit anchors, and a `[block: ...]` tag per section.

## What "RAG-ready" means here {#what-it-means}

[block: concept]
[source: internal authoring guide]

A RAG-ready document is one that chunks cleanly: each section stands on its
own without leaning on text the reader saw a page earlier, each section
declares what kind of content it is, and each section can be traced back to
where it came from. Together this keeps retrieved chunks self-contained
enough that an embedding model, and a human skimming search results, can
make sense of a section without the rest of the document.

## How to check a document {#how-to-check}

[block: procedure]
[source: internal authoring guide]

Run the validator against a single file or a directory:

```
python ragready.py mydoc.md
python ragready.py docs/ --json
```

A passing run exits 0. A directory scan prints one report per file plus a
summary line.
