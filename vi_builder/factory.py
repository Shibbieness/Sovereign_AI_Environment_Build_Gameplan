"""
L3 — ML Process Factory.

"Takes structured extraction output from L2 and produces discrete,
tier-typed ML processes. Each process is a self-contained cognitive or
operational unit: it knows what it is, where it came from, what it
contains, what tier it belongs to, and how to be used." (spec Section 5.1)

Phase 1 scope: Tier 4a (Prompt Capsule) + Tier 4b (RAG Package) only —
"Tier 4 in Phase 1 (inference first — immediately useful)" per spec
Section 4.4. L3 builds; it does not watch (L1), extract (L2), route (L5),
or manage Castle assignments (L6).
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from vi_builder.ingestion import ExtractionResult

CHUNK_SIZE = 800       # characters
CHUNK_OVERLAP = 100    # characters


@dataclass
class ProcessContent:
    """What gets JSON-serialized and stored as a process's flat-file content."""
    format_type: str
    payload: Dict[str, Any]

    def to_json_text(self) -> str:
        import json
        return json.dumps({'format_type': self.format_type, **self.payload}, indent=2, ensure_ascii=False)


def slugify(path: Path, root: Path) -> str:
    try:
        rel = str(path.relative_to(root))
    except ValueError:
        rel = path.name
    return re.sub(r'[^a-zA-Z0-9_.-]', '_', rel)


def build_prompt_capsule(result: ExtractionResult, root: Path) -> ProcessContent:
    """
    Tier 4a. "Structured system prompt + context package. Built from source
    artifacts. Fed directly to a local LLM at runtime." (spec Section 4.4)
    """
    slug = slugify(result.path, root)
    unit_summaries = [
        {'type': u.unit_type, 'label': u.label, 'text': u.text[:2000]}
        for u in result.units
    ]

    # A structured "system prompt" framing this artifact for an LLM consumer.
    context_lines = [f"Source: {slug}", f"Artifact type: {result.artifact_type}"]
    if result.metadata:
        context_lines.append(f"Metadata: {result.metadata}")
    for u in result.units[:10]:
        context_lines.append(f"[{u.unit_type}:{u.label}] {u.text[:300]}")
    context = '\n'.join(context_lines)

    return ProcessContent(
        format_type='Prompt Capsule',
        payload={
            'source_path': slug,
            'artifact_type': result.artifact_type,
            'extraction_approach': result.extraction_approach,
            'metadata': result.metadata,
            'units': unit_summaries,
            'context': context,
        },
    )


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def build_rag_package(results: List[ExtractionResult], root: Path, source_name: str) -> ProcessContent:
    """
    Tier 4b. "Source content chunked with metadata for retrieval. Query ->
    retrieve relevant chunks -> feed to LLM... Backed by SQLite FTS or
    embedding index." (spec Section 4.4) Built once per full ingest run,
    aggregating every eligible file's text — SQLite FTS backing comes from
    the Registry's shared processes_fts table (spec Section 6.2).
    """
    chunks = []
    for result in results:
        if not result.full_text.strip():
            continue
        slug = slugify(result.path, root)
        for i, chunk_text in enumerate(_chunk_text(result.full_text)):
            chunks.append({
                'chunk_id': f"{slug}#{i}",
                'source_path': slug,
                'artifact_type': result.artifact_type,
                'chunk_index': i,
                'text': chunk_text,
            })

    return ProcessContent(
        format_type='RAG Package',
        payload={
            'source_name': source_name,
            'chunk_count': len(chunks),
            'files_covered': sorted({c['source_path'] for c in chunks}),
            'chunks': chunks,
        },
    )
