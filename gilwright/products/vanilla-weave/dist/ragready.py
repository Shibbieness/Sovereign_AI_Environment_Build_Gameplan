#!/usr/bin/env python3
"""
ragready — RAG-readiness validator for markdown documents

Copyright (c) 2026 Shibbieness · M MAOU LLC
SPDX-License-Identifier: AGPL-3.0-or-later

Free to use, modify and redistribute under AGPL-3.0-or-later. If you
distribute a modified version, or run it as a network service others interact
with, your complete corresponding source must be available under the same
licence. A commercial licence waiving that condition is intended to be
available — see LICENSE-COMMERCIAL.md.

ragready.py — Validate that a markdown document (or directory) is
structured well enough to chunk and embed for RAG (retrieval-augmented
generation) use.

Usage:
  python ragready.py PATH [--json] [--verbose] [--strict]

Exit codes:
  0  all docs passed
  1  one or more docs failed validation
  2  hard error (path not found, parse error, etc.)
"""

from __future__ import annotations

import sys
import argparse
from pathlib import Path

# Make local import work when run from any directory
sys.path.insert(0, str(Path(__file__).parent))

from ragready_common import (
    parse_frontmatter,
    extract_sections,
    walk_markdown,
    find_profile,
    load_profile,
    has_back_reference,
    DEFAULT_BLOCK_TYPES,
    ValidationReport,
)


REQUIRED_FRONTMATTER_FIELDS = ["ragready_version", "doc_id", "title"]
RECOMMENDED_FRONTMATTER_FIELDS = ["doc_anchor", "summary", "domain", "tags", "authority"]


def validate_doc(path: Path, profile: dict | None, strict: bool = False) -> ValidationReport:
    """Run the full document structure check suite on a single doc."""
    rpt = ValidationReport(target=str(path))
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        rpt.fail("read", f"could not read file: {e}")
        return rpt

    fm, body = parse_frontmatter(text)

    # Stage 1 / 3 — Frontmatter
    if not fm:
        rpt.fail("stage-3-frontmatter", "no frontmatter block found")
        return rpt
    rpt.pass_("stage-3-frontmatter", "frontmatter parsed")
    for f in REQUIRED_FRONTMATTER_FIELDS:
        if f not in fm:
            rpt.fail("stage-3-frontmatter", f"required field missing: {f}")
        else:
            rpt.pass_("stage-3-frontmatter", f"required field present: {f}")
    for f in RECOMMENDED_FRONTMATTER_FIELDS:
        if f not in fm:
            rpt.warn("stage-3-frontmatter", f"recommended field missing: {f}")

    # Stage 1 — Scaffold (basic shape)
    sections = extract_sections(body)
    if not sections:
        rpt.fail("stage-1-scaffold", "no sections found in body")
        return rpt
    rpt.pass_("stage-1-scaffold", f"{len(sections)} sections found")

    # Stage 4 — Anchor system
    seen_anchors: dict[str, int] = {}
    for s in sections:
        if not s.anchor:
            rpt.fail("stage-4-anchors", f"section has no anchor: '{s.title}'", f"line {s.start_line}")
        else:
            if s.anchor in seen_anchors:
                rpt.fail("stage-4-anchors", f"duplicate anchor: {s.anchor}", f"line {s.start_line}")
            seen_anchors[s.anchor] = s.start_line
            rpt.pass_("stage-4-anchors", f"anchor present and unique: {s.anchor}")

    # Stage 2 — Atomicity (heuristic — back-reference detection)
    for s in sections:
        has_ref, snippet = has_back_reference(s.body)
        if has_ref:
            sev = "fail" if strict else "warn"
            getattr(rpt, sev)(
                "stage-2-atomicity",
                f"possible back-reference: '{snippet}' in '{s.title}'",
                f"line {s.start_line}",
            )

    # Stage 5 — Cross-references resolve
    declared_anchors = set(seen_anchors.keys())
    composes_with = set(fm.get("composes_with", []) or [])
    for s in sections:
        for ref in s.anchor_refs:
            if ref in declared_anchors:
                continue
            if any(ref.startswith(c) for c in composes_with):
                continue
            rpt.warn(
                "stage-5-crossref",
                f"unresolved anchor reference: ⟨ANCHOR {ref}⟩",
                f"line {s.start_line}",
            )

    # Stage 6 — Block types
    valid_block_types = DEFAULT_BLOCK_TYPES.copy()
    if profile:
        for bt in profile.get("block_types", []) or []:
            if isinstance(bt, dict) and "id" in bt:
                valid_block_types.add(bt["id"])
    for s in sections:
        if s.block_type is None:
            rpt.warn("stage-6-block-type", f"no block-type declared: '{s.title}'", f"line {s.start_line}")
        elif s.block_type not in valid_block_types:
            rpt.fail(
                "stage-6-block-type",
                f"unknown block-type: '{s.block_type}' (not in profile)",
                f"line {s.start_line}",
            )
        else:
            rpt.pass_("stage-6-block-type", f"valid block-type: {s.block_type}")

    # Stage 7 — Density
    for s in sections:
        n_lines = s.body.count("\n")
        n_words = len(s.body.split())
        if n_words < 30 and s.level <= 3:
            rpt.warn(
                "stage-7-density",
                f"section may be too sparse ({n_words} words): '{s.title}'",
                f"line {s.start_line}",
            )
        elif n_lines > 80:
            rpt.warn(
                "stage-7-density",
                f"section may be too dense ({n_lines} lines): '{s.title}'",
                f"line {s.start_line}",
            )

    # Stage 8 — Provenance
    for s in sections:
        if not s.source and s.level <= 3:
            rpt.warn(
                "stage-8-provenance",
                f"no [source: ...] declared: '{s.title}'",
                f"line {s.start_line}",
            )

    # Stage 9 — Composability
    for s in sections:
        for fz in s.fuses_with:
            if fz not in composes_with:
                rpt.warn(
                    "stage-9-composability",
                    f"section fuses-with '{fz}' but not declared in frontmatter composes_with",
                    f"line {s.start_line}",
                )

    # Stage 10 — Document-level checks (heuristic)
    if "<!--" in body and "-->" not in body[body.find("<!--"):]:
        rpt.fail("stage-10-validate", "unclosed HTML comment in body")
    if body.count("```") % 2 != 0:
        rpt.fail("stage-10-validate", "unclosed code fence in body")
    if not rpt.findings or all(f.severity == "pass" for f in rpt.findings):
        rpt.pass_("stage-10-validate", "document-level checks passed")

    return rpt


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate document structure and RAG-readiness for a doc or directory")
    ap.add_argument("path", help="Path to .md file or directory of .md files")
    ap.add_argument("--json", action="store_true", help="emit JSON report")
    ap.add_argument("--verbose", "-v", action="store_true", help="show passing checks too")
    ap.add_argument("--strict", action="store_true", help="treat back-reference warnings as failures")
    args = ap.parse_args(argv)

    target = Path(args.path)
    if not target.exists():
        print(f"error: path not found: {target}", file=sys.stderr)
        return 2

    profile_path = find_profile(target)
    profile = load_profile(profile_path) if profile_path else None
    if profile_path and not args.json:
        print(f"# Using profile: {profile_path}")
    elif not profile_path and not args.json:
        print("# No profile found — using built-in defaults")

    docs = walk_markdown(target)
    if not docs:
        print(f"error: no .md files under {target}", file=sys.stderr)
        return 2

    reports = [validate_doc(d, profile, strict=args.strict) for d in docs]

    if args.json:
        import json as _json
        print(_json.dumps({
            "tool": "ragready",
            "version": "1.0.0",
            "profile": str(profile_path) if profile_path else None,
            "reports": [
                {
                    "target": r.target,
                    "passed": r.passed,
                    "findings": [
                        {"severity": f.severity, "check": f.check, "message": f.message, "location": f.location}
                        for f in r.findings
                    ],
                }
                for r in reports
            ],
        }, indent=2))
    else:
        for r in reports:
            print(r.to_text(verbose=args.verbose))
            print()

    failed = sum(1 for r in reports if not r.passed)
    if not args.json:
        print(f"=== Summary: {len(reports) - failed}/{len(reports)} docs passed ===")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
