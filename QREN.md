# QRen lives in `qren-code-build-1`

The `qren/` package that used to sit here is gone. Not dropped — merged. One
copy now exists, in the **QRen-Code-Build-1** repository, on branch
`claude/fullstack-skills-architecture-f573p5`.

## Why there were two

Two repositories each held a QRen, and each had drifted somewhere the other
had not:

| | standalone repo | `qren/` (here) |
|---|---|---|
| QRCF core | 8 block types | **14** — six Tier-2 types plus LIGHT |
| Phase 2 | absent | type headers, validators, circle rules |
| Flavor adapter | **yes**, 13 tests | none |
| Falsy-enum regression test | **yes** | no |

A line-by-line and AST-level comparison settled which core was authoritative
without a judgement call: this copy was a strict superset — nothing removed at
any level, every Tier-1 code and normalization mapping identical, the decoder
structurally unchanged. So the core here became the base.

But "take the bigger copy" would still have lost real coverage. The standalone
held the only adapter, and one test this copy lacked:
`test_a_zero_valued_enum_is_selectable`, covering a falsy-enum defect that
existed in *both* and was fixed in both — with only one copy holding a test to
keep the fix in place. Twenty tests beats nineteen right up until you ask
which nineteen.

## What the split cost

Two defects were found only because two copies existed to compare:

1. **Silent total data loss.** An archive carrying a block type the decoder
   did not know decoded as `valid: True, blocks: 0, data: None`. Found by
   cross-decoding real archives between the copies — this one defined six
   Tier-2 types the other did not, so the bug had somewhere to show itself.
   Present in both; fixed in both before either was retired.

2. **A byte class mistaken for a codepoint range.** The classifier's runic
   rule matched `café`, `Grüße`, `ΑΒΓ` and Japanese text as RUNIC at 0.85
   confidence with `uncertain=False`.

Both fixes landed in both copies *before* consolidation, so retiring this one
retires a duplicate rather than a witness.

## Merged state

| suite | tests |
|---|---|
| `python -m qren.qrcf.test_phase1` | 21 |
| `python -m qren.qrcf.test_phase2` | 31 |
| `python -m unittest test_flavor` | 50 |
| **total** | **102** |

Up from 32 and 51 in the two copies separately. The flavor declares nine
capabilities: `encode`, `decode`, `verify`, `block-types`, `self-test` for the
container format, and `classify`, `slime-phase`, `tokens`, `circle` for the
semantic layer.

## Re-vendoring

The package sits in a `qren/` subdirectory of that repository specifically so
this is a directory copy with no import rewriting. Nothing in this repository
imported it (verified: zero references outside documentation), so nothing here
broke when it left.

If it is ever vendored back, copy the directory — do not fork it. Two copies
is what this file exists to explain.
