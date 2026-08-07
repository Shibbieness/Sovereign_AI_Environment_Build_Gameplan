#!/usr/bin/env python3
"""
bloom_validate.py — Validate that a corpus is BLOOM-runnable per LATTICE
Stage 12 contract. Performs the full 12-check sweep across a directory of
WEAVE-validated docs.

Usage:
  python bloom_validate.py PATH [--json] [--verbose] [--allow-unweaved]

Exit codes:
  0  corpus is runnable
  1  corpus has validation failures
  2  hard error

Author: Shibbieness · M MAOU LLC
Forged: 2026-04-26 · v1u0p0
"""

from __future__ import annotations

import re
import sys
import argparse
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from lattice_common import (
    parse_frontmatter,
    extract_sections,
    walk_markdown,
    find_profile,
    load_profile,
    ValidationReport,
)
from weave_validate import validate_doc as weave_validate_doc


_SLM_BLOCK_RE = re.compile(r"⟨SLM\s*\n(.*?)\n⟩", re.DOTALL)
_CORPUS_BLOCK_RE = re.compile(r"⟨CORPUS\s*\n(.*?)\n⟩", re.DOTALL)
_DAEMON_BLOCK_RE = re.compile(r"⟨DAEMON\s*\n(.*?)\n⟩", re.DOTALL)
_EMBED_BLOCK_RE = re.compile(r"⟨EMBED\s*\n(.*?)\n⟩", re.DOTALL)


def parse_block_body(text: str) -> dict:
    """Parse the body of a Runic-token block (key: value lines)."""
    out: dict = {}
    current_list_key: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("- "):
            if current_list_key:
                out.setdefault(current_list_key, []).append(line[2:].strip())
            continue
        if ":" in line:
            k, _, v = line.partition(":")
            k = k.strip()
            v = v.strip()
            if not v:
                current_list_key = k
                out[k] = []
            else:
                out[k] = v
                current_list_key = None
    return out


def extract_blocks(body: str, regex: re.Pattern) -> list[dict]:
    return [parse_block_body(m.group(1)) for m in regex.finditer(body)]


def validate_corpus(path: Path, profile: dict | None, allow_unweaved: bool = False) -> ValidationReport:
    rpt = ValidationReport(target=str(path))

    docs = walk_markdown(path)
    if not docs:
        rpt.fail("stage-12-validate", "no .md files found in corpus")
        return rpt

    # Stage 12.1 — Walk and parse every doc
    parsed: list[tuple[Path, dict, str]] = []
    for d in docs:
        try:
            text = d.read_text(encoding="utf-8")
        except Exception as e:
            rpt.fail("stage-12-validate", f"could not read: {d}: {e}")
            continue
        fm, body = parse_frontmatter(text)
        parsed.append((d, fm, body))
    rpt.pass_("stage-12-validate", f"parsed {len(parsed)} docs")

    # Stage 12.2 — Verify WEAVE compliance for every member doc
    weave_failures = 0
    for d, _, _ in parsed:
        sub = weave_validate_doc(d, profile)
        if not sub.passed:
            weave_failures += 1
            # BUG FIX (found by testing this repo's --allow-unweaved path): the
            # original vendored code called rpt.fail() here unconditionally, so
            # rpt.passed stayed False even with --allow-unweaved set, defeating
            # the flag's documented purpose ("warn rather than fail"). Route
            # through the same severity the flag promises.
            if allow_unweaved:
                rpt.warn("stage-12-weave-check", f"doc fails WEAVE validation: {d}")
            else:
                rpt.fail("stage-12-weave-check", f"doc fails WEAVE validation: {d}")
    if weave_failures == 0:
        rpt.pass_("stage-12-weave-check", "all docs pass WEAVE validation")
    elif allow_unweaved:
        rpt.warn("stage-12-weave-check", f"{weave_failures} docs failed WEAVE; --allow-unweaved set, continuing")

    # Stage 1 — SLM specs
    all_slms: list[tuple[Path, dict]] = []
    for d, _, body in parsed:
        for blk in extract_blocks(body, _SLM_BLOCK_RE):
            all_slms.append((d, blk))
    rpt.pass_("stage-1-slm-spec", f"found {len(all_slms)} ⟨SLM⟩ block(s)")

    # SLM uniqueness
    seen_slm_ids: dict[str, Path] = {}
    for d, slm in all_slms:
        sid = slm.get("id")
        if not sid:
            rpt.fail("stage-1-slm-spec", f"⟨SLM⟩ without id in {d}")
            continue
        if sid in seen_slm_ids:
            rpt.fail("stage-1-slm-spec", f"duplicate SLM id '{sid}' (also in {seen_slm_ids[sid]})", str(d))
        else:
            seen_slm_ids[sid] = d
        if "task" not in slm:
            rpt.warn("stage-1-slm-spec", f"SLM '{sid}' missing 'task'")
        if "base" not in slm:
            rpt.warn("stage-1-slm-spec", f"SLM '{sid}' missing 'base'")

    # Stage 2 — Corpus declarations
    all_corpora: list[tuple[Path, dict]] = []
    for d, _, body in parsed:
        for blk in extract_blocks(body, _CORPUS_BLOCK_RE):
            all_corpora.append((d, blk))
    if all_corpora:
        rpt.pass_("stage-2-corpus-decl", f"found {len(all_corpora)} ⟨CORPUS⟩ block(s)")
    else:
        rpt.warn("stage-2-corpus-decl", "no ⟨CORPUS⟩ block found — defaulting to single-corpus mode")

    # Stage 3 — Embedding profiles
    all_embeds: list[dict] = []
    for d, _, body in parsed:
        for blk in extract_blocks(body, _EMBED_BLOCK_RE):
            all_embeds.append(blk)
    rpt.pass_("stage-3-training-profile", f"found {len(all_embeds)} ⟨EMBED⟩ block(s)")

    # Stage 4 / 5 — Pipelines / Daemon specs
    all_daemons: list[dict] = []
    for d, _, body in parsed:
        for blk in extract_blocks(body, _DAEMON_BLOCK_RE):
            all_daemons.append(blk)
    rpt.pass_("stage-4-pipeline", f"found {len(all_daemons)} ⟨DAEMON⟩/pipeline block(s)")

    # Stage 6 — VIB registry hooks (declarative — check that each pipeline has a name)
    for daemon in all_daemons:
        if "pipeline" not in daemon:
            rpt.warn("stage-6-vib-registry", "⟨DAEMON⟩ block missing 'pipeline' name")

    # Stage 7 — CALS routing (look for cals/ anchors in the corpus)
    cals_routes = 0
    for d, _, body in parsed:
        secs = extract_sections(body)
        for s in secs:
            for ref in s.anchor_refs:
                if ref.startswith("cals/"):
                    cals_routes += 1
    if cals_routes > 0:
        rpt.pass_("stage-7-cals-routing", f"{cals_routes} CALS route reference(s) declared")
    else:
        rpt.warn("stage-7-cals-routing", "no cals/ anchor references found in corpus")

    # Stage 8 — Castle residency
    castle_residencies = 0
    for d, slm in all_slms:
        if str(slm.get("castle_residency", "")).lower() in ("yes", "true"):
            castle_residencies += 1
            if "principles" not in slm:
                rpt.fail(
                    "stage-8-castle-residency",
                    f"SLM '{slm.get('id')}' requests Castle residency but declares no principles",
                )
            if "floor" not in slm:
                rpt.fail(
                    "stage-8-castle-residency",
                    f"SLM '{slm.get('id')}' requests Castle residency but declares no floor",
                )
    rpt.pass_("stage-8-castle-residency", f"{castle_residencies} Castle residency request(s) found")

    # Stage 9 — dRAM bindings (look for ⟨EMBED⟩ blocks with dram fields)
    dram_keys = 0
    for emb in all_embeds:
        if "dram" in emb:
            dram_keys += 1
    if dram_keys > 0:
        rpt.pass_("stage-9-dram-bindings", f"{dram_keys} dRAM binding(s) declared")
    else:
        rpt.warn("stage-9-dram-bindings", "no dRAM bindings declared (transient state only)")

    # Stage 10 — Fusion rules
    fusion_graph: dict[str, set[str]] = defaultdict(set)
    for d, fm, _ in parsed:
        anchor = fm.get("doc_anchor")
        if anchor:
            for c in fm.get("composes_with", []) or []:
                fusion_graph[anchor].add(c)
    if fusion_graph:
        rpt.pass_("stage-10-fusion-rules", f"fusion graph has {len(fusion_graph)} node(s)")
    # Detect missing referents
    declared_anchors = {fm.get("doc_anchor") for _, fm, _ in parsed if fm.get("doc_anchor")}
    for src, dsts in fusion_graph.items():
        for dst in dsts:
            if dst not in declared_anchors:
                rpt.warn(
                    "stage-10-fusion-rules",
                    f"composes_with target not in corpus: '{dst}' (referenced by {src}) — will downgrade to 'referenced'",
                )

    # Stage 11 — Activation gates
    # Total corpus token count check (rough, by word count)
    total_words = sum(len(body.split()) for _, _, body in parsed)
    min_tokens = 1000
    if profile:
        td = profile.get("training_defaults", {}) or {}
        min_tokens = int(td.get("min_corpus_tokens", min_tokens) or 1000)
    if total_words < min_tokens:
        rpt.warn(
            "stage-11-activation",
            f"corpus is small ({total_words} words < {min_tokens}); training may be unstable",
        )
    else:
        rpt.pass_("stage-11-activation", f"corpus size sufficient ({total_words} words)")

    # Stage 11 — CALS route conflict check
    route_names: dict[str, Path] = {}
    for d, _, body in parsed:
        for s in extract_sections(body):
            if s.anchor and s.anchor.startswith("cals/"):
                if s.anchor in route_names:
                    rpt.fail(
                        "stage-11-activation",
                        f"CALS route conflict: '{s.anchor}' declared in both {route_names[s.anchor]} and {d}",
                    )
                else:
                    route_names[s.anchor] = d

    # Final
    if rpt.passed:
        rpt.pass_("stage-12-validate", "corpus is runnable")
    return rpt


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate BLOOM-runnability for a corpus")
    ap.add_argument("path", help="Path to corpus directory (or single file)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--allow-unweaved", action="store_true",
                    help="warn rather than fail when member docs do not pass WEAVE validation")
    args = ap.parse_args(argv)

    target = Path(args.path)
    if not target.exists():
        print(f"error: path not found: {target}", file=sys.stderr)
        return 2

    profile_path = find_profile(target)
    profile = load_profile(profile_path) if profile_path else None
    if not args.json:
        if profile_path:
            print(f"# Using profile: {profile_path}")
        else:
            print("# No profile found — using LATTICE defaults")

    rpt = validate_corpus(target, profile, allow_unweaved=args.allow_unweaved)

    if args.json:
        print(rpt.to_json())
    else:
        print(rpt.to_text(verbose=args.verbose))

    return 0 if rpt.passed else 1


if __name__ == "__main__":
    sys.exit(main())
