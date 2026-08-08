# AI OS — readiness spire and assembly plan

Status: **planning document.** Nothing in the "OS" exists yet beyond Vanilla
Core (v0.2.0) and one ported flavor (QRen Coder). This file records the
shape and the sequencing so they survive between sessions, because the
decisions matter more than the enthusiasm that produced them.

## The core claim

An AI OS is not one program that contains everything. It is the same four
layers every operating system has, and the stack already maps onto them:

| OS layer | Conventional | Here |
|---|---|---|
| Hardware / substrate | CPU, memory, disk | Linux — do not reinvent |
| Kernel | process model, scheduling, isolation | **Vanilla Core** — load, floor-check, run |
| Drivers | one per device, uniform interface | **Flavors** — one per subsystem, one contract |
| Scheduler / IPC | who runs, who talks to whom | **Composite runner** (v0.3, not built) |
| Userland | shells, tools, services | The stack's actual capabilities |

The useful consequence: "build an AI OS" decomposes into "port each
subsystem to a flavor, then write one router." Both are finite. Neither
requires a grand fusion step.

## Use Linux for what Linux already does

Do not rebuild process isolation, scheduling, filesystems, IPC, service
supervision, or package management. Every one of those is a decade-scale
problem already solved by free software this project can simply consume:

- **Isolation / resource limits**: namespaces + cgroups v2. A misbehaving
  flavor should be constrained by the kernel, not by Python politeness.
- **Service supervision**: systemd units (or s6/runit) for long-lived flavors.
- **Packaging / distribution**: OCI images. A flavor that declares a
  container image is portable to any host, which is the same portability
  argument the `flavor.toml` contract makes at the code level.
- **Storage / state**: SQLite. Already the stack's default (ASSAY, SPIRE,
  ACI) and correct here — single-file, transactional, zero-server.
- **IPC**: Unix sockets and pipes before anything clever.

The custom part is the **cognitive routing layer** — which capability
handles which request, under what floor. That is the part worth building.
Everything below it is plumbing that already exists and is better than
what a rewrite would produce.

## The Spire — readiness gates

A subsystem does not join the OS because it is interesting. It joins when it
passes gates, in order. This is a readiness certification, not a credential:
passing G5 means the piece composes, not that it is finished.

| Gate | Requirement | Verified by |
|---|---|---|
| **G0** | Source exists and is licensed | `LICENSE` present, floor-checkable |
| **G1** | Runs standalone; its own tests pass | its test suite, green |
| **G2** | Has `flavor.toml` that passes the floor | `vanilla-core check` |
| **G3** | Adapter exists; capabilities dispatch; adapter tests pass | `vanilla-core run`, adapter suite |
| **G4** | Composes with ≥1 other flavor through the runner | composite integration test |
| **G5** | Declared capability surface matches actual dispatch | contract test |

**Rule: no subsystem advances a gate it has not actually passed.** The
status table below is the real one, and it is mostly empty on purpose.

## Current status — honest

| Subsystem | Gate | Notes |
|---|---|---|
| Vanilla Core | — | The kernel; v0.2.0, 11 tests |
| QRen Coder | **G3** | Ported. 15 format tests + 13 adapter tests |
| ML Filesystem (`sovereign_py/`) | **G3** | Ported. 19 adapter tests, 9/9 capabilities working, no known gaps. Master DB routes two model Bases to two stores (27 tables) |
| Eidoa | G0 | Licensed. Code exists, untested here |
| QRen (vendored, `qren/`) | G1 | 15/15 tests; adds 7 Tier-2 block types, Crystal Slime, magic circle, classifier. Overlay plan in QREN-CONSOLIDATION.md |
| VI Builder (`vi_builder/`) | **G1** | Verified: ingested `sovereign_py/` → 49 Prompt Capsules (4a) + RAG Package (4b, 934 chunks). Run as `python -m vi_builder.cli` |
| Helix / MenuCode (`helix/`) | **G1** | Verified: 8/8 conventions pass on its reference file, and correctly *fails* an unrelated file — it discriminates |
| Lattice (`lattice/`) | **G1** | Verified: WEAVE (10-stage doc) and BLOOM (12-stage corpus) both produce real reports |
| Gilwright (`gilwright/`) | **G1** | Verified: `ragready` runs clean (12 pass/0 fail). Factory bridge + seeded append-only ledger |
| ASSAY, CRUCIBLE | — | Described in skills; no repo in scope yet |
| CALS / CASL / Cal's Castle | — | Framework, not yet code in scope |
| Runic, Helix, Lattice, SPIRE, ACI, Book of Cities | — | Same |

Everything below G3 is a plan, not a component. But the G0 count is now much
smaller than it looked: a sibling session had already built and run four of
these, and re-verification here confirmed it. Four subsystems sitting at G1
are each only a manifest and an adapter away from G3, which changes the
sequencing — see below.

**All six vendored packages are genuinely decoupled** (verified: zero
cross-package imports). That matters more than it sounds: each can become a
flavor independently, in any order, without a dependency untangling step
first.

## What the sibling session already built

A parallel session (`claude/installed-skills-access-aco5uy`) built these and
left handoff notes in the repo rather than only in chat. Its claims were
re-verified here rather than taken on assertion, and they held:

- **`vi_builder/`** — VI Builder Phase 1, L1 daemon through L4. Ingest of
  `sovereign_py/` produced 49 Prompt Capsule processes and a 934-chunk RAG
  Package. Note it runs as a package (`python -m vi_builder.cli`), not as a
  script.
- **`helix/`** — MenuCode's 8 formatting conventions, validating *Python*
  files (not markdown).
- **`lattice/`** — WEAVE and BLOOM validators, both functional.
- **`gilwright/`** — a factory bridge with an append-only SQLite ledger, and
  its first shipped product.

### GILWRIGHT has a product waiting on a human decision

`gilwright/products/vanilla-weave/dist/` ships as **ragready**, a
dependency-free RAG-readiness checker scrubbed out of Lattice's WEAVE
validator. It runs clean. It has been at lifecycle **ICE** since 2026-07-26,
sitting in an 8-step `hands_queue` that only the Witness (Mark) can action,
because the factory's constraint C1 is that agents build and never ship.

**Step 1 blocks the other seven:** `dist/LICENSE` still reads
`Copyright (c) 2026 [BYLINE PENDING]`. The licensing work in this session
settled that question — `Shibbieness / M MAOU LLC` — so this is now a
one-line edit rather than an open decision.

Two inconsistencies worth recording:

1. **The scrub claim is not literally true.** `STATUS.md` reports S1–S7
   passed with "zero canonical-term/VUP/internal-path hits in dist/", but
   `[block:` appears in `ragready_common.py`, `README.md`, and `example.md`,
   and S2 forbids it. It is arguably a false positive — validating
   `[block: type]` tags is the tool's entire function, so it must contain
   the pattern — but the checklist needs an explicit exemption rather than a
   pass that does not hold on inspection.
2. **License divergence.** ragready ships MIT while this session moved the
   repositories to AGPL precisely because MIT does not keep derivatives
   free. For a two-file stdlib utility MIT is defensible, but the
   inconsistency is a decision, not an oversight to leave implicit.

## ML Filesystem: what the port found

Five defects found and fixed: a SQLAlchemy reserved-name collision that
broke `models_v1` on import, a missing bridge alias that broke
`part2_agent_system`, a stale database singleton, a missing root-directory
record that made `list_directory('/')` fail on every fresh install, and two
capabilities returning ORM objects bound to already-closed sessions.

The blocking defect — two divergent `File` models — is resolved by
**routing, not merging**. Six table names collide between the two
declarative Bases with different columns on each side, so one database was
never possible. `core/master_db.py` owns one engine per store:

- **hierarchy** (`models_v1`): the filesystem tree — `is_directory`,
  `parent_id`, `storage_path`. 10 tables.
- **enhanced** (`core.database` + `enhanced_models`): chains, training
  blocks, agents, embeddings, VM/IDE/API. 17 tables.

Neither is canonical. Different stores for different jobs.

**Open limitation:** both stores have a `files` table and they are not
synchronized. Nothing crosses that boundary today, but any feature joining a
chain to a file on disk must reconcile identity across stores explicitly.
That is the next real design task in this subsystem.

## The two QRen versions

Analysed in full in `QREN-CONSOLIDATION.md`. Summary: the format cores are
functionally identical (both 15/15; the ~780 differing lines are docstrings
and import style). The vendored copy adds ~2,900 lines of semantic layer —
7 additional Tier-2 block types on free codes, Crystal Slime lifecycle,
magic circle, classifier, Runic tokens.

The two are **wire-compatible in one direction**: Tier 1 codes are identical,
so standalone archives decode under the vendored taxonomy, but not the
reverse. The overlay is therefore additive and does not touch the frozen
core. Plan and failure modes are in `QREN-CONSOLIDATION.md`.

## Why ML Filesystem was next, specifically

Not because it is the most interesting — because it is the only candidate
that would **consume QRen's output** rather than sit beside it. A composition
contract has to survive a real data dependency between two flavors, and you
cannot design one against a single example. The first port already proved
this in miniature: `params` only entered the contract because a real flavor
needed it, after speculation had missed it.

Two flavors with a genuine dependency is the minimum honest input to
designing the router. That is the whole gate on v0.3.

## What breaks this

1. **Fusion before readiness.** The dominant failure mode. Combining fifteen
   subsystems that have not individually reached G3 produces a specification
   that cannot run, and the effort spent on the fusion is unrecoverable
   because none of it was validated against a working piece.
   *Fix:* the gate table. Port, then compose. Never the reverse.

2. **Vocabulary bleed into the kernel.** The moment CALS namespaces, QRen
   block types, or Eidoa cognition modules appear inside `vanilla_core/`,
   it stops being reusable and becomes one more flavor wearing a kernel's
   name.
   *Fix:* the existing rule — something enters core only when two
   independent flavors need the *identical* mechanism. Enforced by review,
   and by the fact that core has no flavor imports today.

3. **Scope churn outrunning the record.** This project's direction changes
   fast and by design. Anything decided only in conversation is lost.
   *Fix:* decisions live in `ARCHITECTURE.md`, `STANDARDS.md`, and this
   file. If it is not committed, it did not happen.

4. **The OS becoming a Python monolith.** In-process `import` of every
   flavor means one bad flavor takes down everything, and the "OS" is really
   a large library.
   *Fix:* the contract is already process-agnostic (TOML + one callable). The
   runner should gain a subprocess/container execution mode before it gains
   features, so isolation is structural rather than aspirational.

5. **Unverifiable claims accumulating.** A skill capsule asserting a
   subsystem has "86 invariants" or "217 verified equations" is a design
   document until something runs. Treating documentation as evidence is how
   a stack becomes impossible to audit.
   *Fix:* the gate table separates "described" from "runs." Only G1+ counts.

6. **Licensing collision.** A flavor pulling a GPL-incompatible or
   proprietary dependency silently poisons distribution.
   *Fix:* `flavor.license` is already required and validated; extend the
   floor to check declared dependencies when flavors start having any.

7. **Single maintainer, AI-assisted drift.** Code volume can outpace review
   capacity, and unreviewed generated code is technical debt that looks
   finished.
   *Fix:* every port needs its own test suite written against observed
   behavior — as QRen's did, which is exactly how the integrity bug
   surfaced. Tests are the review that scales.

## On "expand all skills through the Mad Scientist"

Deliberately not attempted in one pass. Loading twenty-plus capsules at once
produces averaged mush — each capsule's distinctions blur into the others,
which is the opposite of the goal, and none of it would be verified against
running code.

The gate table *is* the expansion plan. Each subsystem gets its full
treatment when it is being ported — at that point the relevant skill is
loaded against real code, the port is tested, and the result is committed.
That yields genuinely different results per subsystem, because the code
differs, rather than uniformly enthusiastic prose about all of them.

## The Spire as a learning structure

The gates were built to certify subsystem readiness. They double as a
learning path, and that is worth making explicit rather than leaving
implicit.

A gate ladder is already the shape a curriculum wants: ordered, each rung
verifiable, no rung passable by assertion. Someone learning this system by
taking a subsystem from G0 to G3 has to make its tests pass, write a
manifest that does not overpromise, and produce an adapter with its own
tests. That is not a tutorial *about* the system — it is the same work a
maintainer does, at a smaller radius.

Two properties make this usable by someone who is not already an expert:

- **The gates are machine-checked.** `vanilla-core check` and a test suite
  say pass or fail. A learner does not need a mentor to know where they are.
- **Failure is informative here.** Every port so far surfaced real defects —
  a reserved attribute name, a wrong module alias, a session-lifetime bug.
  Those are the actual skills, and they cannot be learned from prose.

What is **not** built: any of it. There is no lesson content, no progress
tracking, no ordering hints for a newcomer, no way to attempt a gate against
a scratch copy without touching the real repo. The SPIRE skill describes
machinery for exactly this (tiered re-entry, capability floor, held-out
splits); wiring that to these gates is a real project, and it should not
start until more subsystems are actually at G3 — a curriculum built from two
examples teaches those two examples.

Recorded as direction, not as work in progress.

## Immediate next step

Two flavors are at G3 and four more subsystems are at G1 — verified running,
just without manifests. That is a better position than the earlier status
implied, and it reorders the work:

1. **QRen overlay** (`QREN-CONSOLIDATION.md`). Still first: two divergent
   copies of one subsystem is the exact condition the vanilla/flavor split
   exists to prevent, and it worsens while both are edited.
2. **G1 → G3 for the four verified packages.** Each needs only a
   `flavor.toml` and an adapter with tests. They are decoupled, so this can
   happen in any order, and none of it blocks on the others.
3. **The composite runner**, designed against the QRen → ML Filesystem
   dependency now that both ends actually run.

Not on this list: anything requiring a human to ship. `ragready` waits on
the Witness, and no agent-side work should touch it.
