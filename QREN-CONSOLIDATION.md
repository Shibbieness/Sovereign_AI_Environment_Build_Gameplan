# QRen consolidation — what differs, and what to overlay

> **DONE. The consolidation described below has been executed.** One QRen now
> exists, in `qren-code-build-1`. This file is kept as the record of how the
> decision was reached, not as outstanding work — `QREN.md` describes the
> resulting state.
>
> The merge did not follow step 1, for the reason in the amendment immediately
> below. It also did not follow "take the copy with more tests": the
> standalone held `test_a_zero_valued_enum_is_selectable`, which the vendored
> copy lacked, covering a defect present in both. Carrying tests across in
> both directions is what the merge actually required.
>
> A third defect surfaced during the merge itself and was fixed in both copies
> before either was retired: the classifier's runic rule was a byte class
> written as though it were a codepoint range, so `café`, `Grüße`, `ΑΒΓ` and
> Japanese text all classified as RUNIC at 0.85 confidence with
> `uncertain=False`.
>
> Merged suites: 21 + 31 + 50 = **102 tests**, from 32 and 51 separately.

> **AMENDED 2026-08-11 after measuring instead of reading.** Two claims below
> were wrong and are corrected here rather than edited away, because the
> reasoning that produced them is the useful part.
>
> **1. The direction is inverted.** "Recommended overlay" step 1 says to keep
> the standalone repo's QRCF because it is "the frozen canonical format". It
> is not. Only the *vendored* copy carries
> `STATUS: PHASE 1 FROZEN. Wire format locked. 15/15 tests verified.`, and an
> AST-level comparison of every constant, function, class and member shows the
> vendored core is a **strict superset**: nothing is removed anywhere, every
> Tier-1 code and normalization mapping is identical, and it adds six block
> types, `compute_growth_space()`, `BlockHeaderFlags` and `encode(flags=)`.
> The decoder has **zero** structural difference — all 240 diff lines are
> formatting. Following step 1 would have kept the smaller copy and re-added
> the Tier-2 types by hand.
>
> The standalone's one unique asset is `vanilla_flavor.py` + 13 adapter tests
> + CI, which is what its G3 rests on. That must be carried across; the
> vendored copy has no adapter at all.
>
> **2. "The two are wire-compatible" is true only one way.** Verified by
> cross-decoding real archives in memory. Standalone→vendored and vendored
> Tier-1→standalone both round-trip byte-exact. But a vendored **Tier-2**
> archive read by the standalone decoder returned
> `valid: True, blocks: 0, data: None` — silent total data loss reported as
> success. The defect was in **both** copies (the vendored one simply knows
> six more codes, so it fired at 0x0E instead of 0x08) and is now fixed in
> both, with regression tests verified against the pre-fix code.
>
> Step 5 ("retire `qren/`") would have deleted one of the two witnesses to
> that bug before it was found.


Two QRen copies exist. This records exactly what each has, so the merge is a
decision rather than a guess.

## The two copies

| | `QRen-Code-Build-1` (standalone repo) | `qren/` (this branch, vendored) |
|---|---|---|
| QRCF format core | yes, 15/15 tests | yes, 15/15 tests, header marks it **"PHASE 1 FROZEN … canonical"** |
| Extra format modules | — | `qrcf_circle_rules.py` (845 lines), `qrcf_types_phase2.py` (946 lines) |
| Semantic/type layer | — | `block_types.py`, `wire_format.py`, `tokens.py`, `crystal_slime.py`, `magic_circle.py`, `classifier.py`, `cli.py` |
| Block types | **8** (7 + CUSTOM) | **15** (14 + CUSTOM) |
| Vanilla Core flavor | yes (`vanilla_flavor.py`, 13 tests) | — |
| Total extra lines | — | ~2,900 |

Both QRCF cores pass their suites. The ~780 differing lines between them are
docstrings, provenance headers, and import style (the vendored copy uses
package-relative imports; the standalone uses flat). **No functional
divergence was found in the format core** — this is a packaging difference,
not two competing implementations.

## Block types: the real gap

The standalone repo's `BlockType` has 7 canonical types plus CUSTOM. The
vendored `block_types.py` has two tiers:

**Tier 1** (same 7, matching codes — so this is additive, not conflicting):
`TREE` 0x01, `ICE` 0x02, `FLAME` 0x03, `LIGHTNING` 0x04, `FRACTAL` 0x05,
`GEOMETRIC` 0x06, `AMORPHOUS` 0x07

**Tier 2** (present only in the vendored copy):
`NESTED` 0x08, `RUNIC` 0x09, `MYCELIUM` 0x0A, `BONE` 0x0B, `VOID` 0x0C,
`CRYSTAL` 0x0D, `LIGHT` 0x0E, and `CUSTOM` 0xFF

Tier 2 codes occupy `0x08`–`0x0E`, which the standalone copy leaves free.
**The two are wire-compatible**: any archive written by the standalone
encoder decodes under the vendored taxonomy unchanged, because the codes it
uses mean the same things. The reverse is not true — a Tier 2 archive is
unintelligible to the standalone copy.

The vendored types also carry semantics the standalone has no field for:
`executable`, `pinned`, and `crystal_slime` phase (A/B/C, mapping
`AMORPHOUS → ICE → CRYSTAL`).

## Two wire formats, deliberately

Worth flagging before anyone "unifies" them: `qren/wire_format.py` (SAIP
magic) is **not** a competitor to QRCF. The vendored package's own header
says the two layers are "deliberately kept separate rather than forced into
one artificial wire format" — `wire_format.py` is a minimal illustrative
format for the semantic layer, while `qrcf/` is the real container format.
Merging them would destroy a distinction the author made on purpose.

## Recommended overlay

Additive, in dependency order. Nothing here rewrites the frozen core.

1. **Keep the standalone repo's QRCF as-is.** It is the frozen canonical
   format and already carries the working Vanilla Core flavor. Do not touch
   it in this operation.
2. **Copy the semantic layer in** as a subpackage of the QRen repo —
   `block_types.py`, `tokens.py`, `crystal_slime.py`, `magic_circle.py`,
   `classifier.py`, `wire_format.py`. These have no dependency on the QRCF
   modules; they import cleanly on their own (verified).
3. **Copy the two extra format modules** (`qrcf_circle_rules.py`,
   `qrcf_types_phase2.py`) alongside QRCF, but do **not** wire them into the
   frozen encoder/decoder path yet. They are phase-2 work and deserve their
   own gate.
4. **Extend the flavor** with capabilities for the new layer:
   `classify` (block-type classifier), `slime-phase` (lifecycle position),
   `tokens` (the TB/EA/IF Runic tokens), `circle` (magic-circle inference).
   Each needs adapter tests before being declared, same rule as before.
5. **Retire `qren/` from this branch** once 2–4 land, so one copy remains.
   — *Done. Steps 3 and 4 landed first (phase-2 modules wired and tested; all
   four semantic capabilities declared with adapter tests). `qren/` is gone
   from this repository; `QREN.md` replaces it.*

## What breaks this

- **Doing step 5 first.** Deleting the vendored copy before the overlay
  lands loses ~2,900 lines that exist nowhere else.
- **Renumbering block-type codes.** Tier 1 codes are identical across
  copies and appear in already-encoded archives. Changing them silently
  breaks every existing file.
- **Merging the two wire formats.** See above — the separation is
  intentional.
- **Declaring the new capabilities before testing them.** The manifest is a
  promise; the ML Filesystem port already showed what it costs to make one
  the code cannot keep.

## Status

Analysis superseded by measurement; see the amendment at the top. Work
completed since:

- **Stage 1 — done.** Silent data loss on unknown block types fixed in both
  copies, before any merge, so the fix could be verified against both.
  Regression tests confirmed failing against the pre-fix decoders.
- **Stage 2 — done.** `test_all_block_types` derives its list from the enum
  instead of naming seven literals, so all 13 wire types round-trip. The
  `flags` encoder parameter is covered. ("7 Tier-2 block types" was an
  inventory claim with nothing behind it, and the count was 6.)
- **Stage 3 — done.** Three block-type definitions collapsed to one.
  `qrcf_types_phase2`'s duplicate enum is now an import; `LIGHT (0x0E)` added
  to the wire enum so it is encodable rather than classifiable-and-lost; a
  cross-layer agreement test keeps them together.
- **Stage 4 — half done.** The orphaned phase-2 code is now tested (21 tests)
  and three real bugs in it are fixed: validators that raised on every call,
  `CircleRuleSet.pack()` failing its own size assertion, and `SEALED` never
  firing. **Still to do: wiring the four Tier-2 headers into the encode/decode
  path and `encode_with_rules` as an entry point.**
- **Stage 5 — not started.** Consolidate onto the vendored core, carrying the
  flavor adapter across.

Full plan and measurements: the session plan file, and the amendment above.
