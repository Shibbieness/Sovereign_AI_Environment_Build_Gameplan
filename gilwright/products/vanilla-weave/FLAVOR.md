# FLAVOR.md — vanilla-weave (ships as "ragready")
[block: ice] v0u1p0 · M MAOU LLC · Shibbieness

Overlay mapping vanilla dist/ back to its flavored source. Additive and
removable per S4/vup-attribution-port.md — the vanilla product never depends
on this file, and this file is not part of dist/.

## Vanilla → flavored name map

| Vanilla (dist/)        | Flavored (src/, = lattice/cli/)     |
|-------------------------|--------------------------------------|
| `ragready.py`           | `weave_validate.py`                  |
| `ragready_common.py`    | `lattice_common.py`                  |
| `ragready_version` (frontmatter field) | `lattice_version`      |
| `ragready.profile.yaml` (config name)  | `lattice.profile.yaml`|
| "ragready" (JSON `tool` field, brand)  | "WEAVE" / "LATTICE"    |

## Stack lineage

Sourced from LATTICE (Sovereign_AI_Environment_Build_Gameplan/lattice/),
specifically the WEAVE half of the WEAVE/BLOOM pair — the 10-stage
document-level validation contract. BLOOM (12-stage corpus validation, which
composes WEAVE across a directory) was not brought into this product; only
the single-document checks shipped. A `vanilla-bloom` product sourced the
same way is a plausible future ICE candidate if there's signal for it.

VUP lineage at time of scrub: `lattice/cli/lattice_common.py` and
`weave_validate.py` were both at `v1u0p0` (forged 2026-04-26).

## What changed in the scrub (S7: behavior identical)

Only naming and meta-commentary were touched — every regex, dataclass,
check ordering, and severity rule is byte-for-byte the same logic as the
flavored source. Specifically:

- Module docstrings: dropped "per LATTICE Stage 10 contract" / "WEAVE-
  compliant" framing, byline, and VUP string; kept the functional
  description.
- Import: `from lattice_common import (...)` → `from ragready_common import (...)`.
- `REQUIRED_FRONTMATTER_FIELDS`: `"lattice_version"` → `"ragready_version"`.
- `find_profile()`: looks for `ragready.profile.yaml` instead of
  `lattice.profile.yaml`; same walk-up-directories logic.
- Comment "CASL floor — heuristic" → "heuristic" (dropped the CALS-namespace
  reference; the check itself — unclosed comment/fence detection — is
  unchanged).
- argparse `description=` and the "no profile found" print message reworded
  to drop "WEAVE"/"LATTICE".
- JSON output: `"tool": "weave_validate"` → `"tool": "ragready"`,
  `"version": "1u0p0"` (VUP) → `"version": "1.0.0"` (semver, per S2/
  vup-attribution-port.md: vanilla dist/ uses plain semver).

Untouched (legitimate tool functionality, not M MAOU vocabulary — a stranger
can read "looks for `[block: TYPE]` tags" without knowing what LATTICE is):
`_FRONTMATTER_RE`, `_coerce_scalar`, `parse_frontmatter`, all section-header/
block-type/source/fuses-with/anchor-ref/token regexes, the `Section`
dataclass, `extract_sections`, `load_profile`, `DEFAULT_BLOCK_TYPES`,
`Finding`/`ValidationReport`, `walk_markdown`, `PRONOUN_REFERENCE_PATTERNS`,
`has_back_reference`, and all ten validation stages in `validate_doc`
(frontmatter, scaffold, anchors, atomicity, cross-references, block types,
density, provenance, composability, document-level checks) including the
`⟨ANCHOR name⟩` reference syntax the tool parses — that bracket/glyph
convention is the product's actual feature, not internal jargon.

## Open item

S6 byline is unresolved — see hands_queue. `LICENSE` in dist/ carries a
placeholder pending Mark's choice (real name / Shibbieness / M MAOU LLC).
