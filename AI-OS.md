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
| ML Filesystem (`sovereign_py/`) | **G3 partial** | Ported, 13 adapter tests. 5 of 8 capabilities declared; 3 blocked upstream — see below |
| Eidoa | G0 | Licensed. Code exists, untested here |
| QRen (vendored, `qren/`) | G1 | Fuller than the standalone repo: 15/15 tests, plus block types, magic circles, Crystal Slime, phase-2 types. **Not the version that was ported** |
| VI Builder (`vi_builder/`) | G0 | 7 modules, untested here |
| Helix / MenuCode (`helix/`) | G0 | 3 modules, untested here |
| Lattice (`lattice/`) | G0 | WEAVE/BLOOM validators, untested here |
| Gilwright (`gilwright/`) | G0 | Ships its own SQLite ledger and a vanilla-weave product |
| ASSAY, CRUCIBLE | — | Described in skills; no repo in scope yet |
| CALS / CASL / Cal's Castle | — | Framework, not yet code in scope |
| Runic, Helix, Lattice, SPIRE, ACI, Book of Cities | — | Same |

Everything below G3 is a plan, not a component. Ten subsystems at G0 is not
one tenth of an OS — it is zero of an OS with ten candidates.

## ML Filesystem: what the port found

Three integration defects, all fixed: a SQLAlchemy reserved-name collision
that broke `models_v1` on import, a missing bridge alias that broke
`part2_agent_system`, and a stale database singleton in the adapter's own
bootstrap. With the first two fixed, the documented 17-table schema builds
and all 20 bridge aliases resolve.

One defect is **not** fixed, on purpose. `fs_engine/filesystem.py` queries
`File.is_directory` and `File.parent_id`; the `models` alias resolves to
`core.database`, whose `File` has neither. `core/models_v1.py` does have
them. The two model generations register on separate declarative Bases, so
no alias change reconciles them — deciding which is canonical changes the
database schema, and that is an owner's call.

Consequence: `fs-write`, `fs-read`, `fs-list` are implemented but not
declared in the manifest. They raise an explanation rather than an opaque
ORM error. This is why the gate reads **G3 partial** rather than G3: the
filesystem's write path does not work, and a status table that hid that
would be worthless.

## The two QRen versions

`qren/` on this branch is a **fuller** QRen than the standalone
`QRen-Code-Build-1` repository that was ported: same 15/15-passing QRCF
core, plus a whole outer layer (`block_types.py`, `magic_circle.py`,
`crystal_slime.py`, `classifier.py`, `wire_format.py`, `tokens.py`,
`cli.py`) and two extra format modules (`qrcf_circle_rules.py`,
`qrcf_types_phase2.py`) — roughly 2,900 additional lines. Its own header
marks the QRCF core "PHASE 1 FROZEN … canonical."

The port targeted the standalone repo, which means **the thinner copy is the
one wearing the flavor.** This needs resolving before more work lands on
either: two divergent copies of the same system is the condition the whole
vanilla/flavor split exists to prevent. Recommended: make the vendored
version canonical, move it into the QRen repository, and re-point the
adapter at it.

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

## Immediate next step

Port ML Filesystem to G3. Then, with two real flavors and a real dependency
between them, design the composite runner against what they actually need.
