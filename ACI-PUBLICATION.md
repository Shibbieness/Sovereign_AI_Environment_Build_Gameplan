# ACI: why a public split is a scrub, not a gitignore

Decision record. ACI was **not** published this session. This says why, and
what publishing it would actually require.

## What was asked

Put ACI on a public repository with the private material gitignored, so it
"works the same" while nothing sensitive is exposed.

## Why that does not work as stated

**1. A gitignore cannot un-publish history.** The private ACI repository has
one commit containing `sources/`, `db/aci.db` and `docs/`. Pushing that
repository to a public remote publishes all of it; `.gitignore` governs only
future untracked files. A public ACI needs a **fresh history**, never the
private one with rules added.

**2. The database leaks the specification on its own.** Gitignoring
`sources/` is not enough. `db/aci.db` was inspected directly and returns
capability-node names, invariant text verbatim, conflict titles, and the
audience-world list. So does `db/extracted.json`. Excluding the raw corpus
while shipping the database would publish nearly all of the substance.

**3. The engine is entangled with the content.** A file-name split fails on
inspection. Reading the "engine" files found:

| File | What it actually contains |
|---|---|
| `db/decisions.py` | The decision substrate itself — 49 conflict titles, 8 invariants verbatim, cluster descriptions, as Python literals |
| `tools/distribution_model.py` | Owner-distribution reasoning and reserve-position logic |
| `tools/gen_glossary.py` | 37 hand-written term definitions |
| `tools/check_policy.py` | Autonomous-spending category rules |
| `db/build_db.py` | Duplicate-pair data from the registries |

Genuinely generic, by content: `tools/verify_hashes.py`,
`tools/sync_docs.py`, `db/extract.py`, `vanilla_flavor.py`, `test_flavor.py`.

**4. Stripped of its corpus, it does not run.** `verify_hashes.py` would
report `34 missing — CORPUS INTEGRITY FAILURE`, exit 2. `validate` fails,
`self-test` fails, CI fails, and most capabilities return nothing. That is
the exact defect fixed this session, deliberately recreated.

## What publishing it would actually require

This is the GILWRIGHT scrub (FORGE.md S1–S7) applied to ACI, and it is a
real unit of work rather than a configuration change:

1. **Fresh repository, fresh history.** Never a filtered clone of the
   private one.
2. **Separate the engine from the data.** `decisions.py` becomes a loader
   that reads a decision file; the data moves out. Same for the glossary
   terms, the policy categories, and the distribution model's thresholds.
3. **Ship a synthetic corpus** — a handful of invented documents with real
   hashes — so the integrity gate passes, `validate` runs, CI is green, and
   a stranger can actually use it. Without this the public artifact is a
   broken engine, not a product.
4. **Run the guard before every push** (`tools/leakguard.py`), with the
   denylist extended to ACI's own vocabulary.
5. **Have a human read the diff.** The guard catches known patterns. It
   cannot catch a paraphrase.

The result is a generic corpus-adjudication substrate: append-only ruling
ledger, human-witness trigger, integrity gate, conformance runner. That is
a genuinely useful public artifact, and it is *not* ACI — which is the
point of Vanilla/Flavor.

## What was built instead

`tools/leakguard.py` — a content-based publication guard, because the real
defect is that `.gitignore` was being used as a security control and is not
one. It matches contents rather than paths, flags binaries instead of
skipping them, reports `file:line`, and exits non-zero.

Its exemption list is exact paths only, never globs, with a test enforcing
that. The reason is on the record: GILWRIGHT's scrub reported "zero
canonical-term hits" while the shipped product contained the pattern it
forbade, because the checklist had no way to record a legitimate exception
and so the claim was simply false. An exemption written down keeps the
claim true.

12 canary tests plant each forbidden pattern and require the guard to
scream. A guard only ever observed passing is indistinguishable from one
that cannot fail.
