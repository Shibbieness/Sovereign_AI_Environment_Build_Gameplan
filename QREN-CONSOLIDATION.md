# QRen consolidation — what differs, and what to overlay

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

Analysis only. No files moved yet — this is the decision record, and the
overlay is the next unit of work on QRen.
