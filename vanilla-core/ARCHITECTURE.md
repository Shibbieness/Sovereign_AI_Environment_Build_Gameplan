# Architecture

## What Vanilla Core is

A small, stdlib-only Python engine (Python 3.11+, no runtime dependencies)
that discovers, floor-checks, and runs **flavors** — self-contained pieces of
functionality declared by a `flavor.toml` manifest and one entrypoint
function. It's the shared machine, not any one flavor's logic.

```
flavor.toml  →  FlavorManifest.load()  →  check_floor()  →  load_flavor()  →  flavor.run(**kwargs)
```

## The manifest contract (v1)

```toml
[flavor]
name = "some-flavor"
version = "0.1.0"
license = "AGPL-3.0-or-later"   # or MIT / Commercial / AGPL-3.0-only
entrypoint = "plugin:run"        # "module:callable", resolved from the
                                  # manifest's own directory
capabilities = ["thing-it-can-do"]
```

`vanilla_core.registry.load_flavor` adds the manifest's directory to
`sys.path`, imports `module`, and returns `callable` unexecuted — the caller
decides when and how to invoke it (`flavor.run(capability=...)` by
convention; the exact call signature is the flavor's own business).

This is intentionally the entire contract. It does not currently version
itself (there is only v1); when it needs to change in a breaking way, add a
`schema = N` field with a default of 1, branch on it in `manifest.py`, and
document both versions here rather than break existing flavors silently.

## The floor (`vanilla_core.floor.check_floor`)

The floor is not a code-quality gate, a security audit, or a safety
review — it's the small set of things Vanilla Core refuses to run without,
full stop:

- `name`, `version`, and a recognized `license` are present.
- `entrypoint` is a resolvable `module:callable` string.
- No disallowed marker (`anthropic.com`, a `claude.ai/code` session link, a
  `Co-Authored-By: Claude` trailer) appears anywhere in the manifest's own
  fields.

`load_flavor()` enforces this by default (`enforce_floor=True`) and raises
`FloorViolationError` rather than importing untrusted/incomplete code. This
is the mechanism, not the whole standards story — see `STANDARDS.md` for
everything the floor does *not* yet cover and where that work should live
(most of it belongs in per-flavor CI, not in this generic core).

## What does and doesn't belong in core

**Belongs in `src/vanilla_core/`:** anything at least two independent
flavors need identically — the manifest format, the floor mechanism, the
discovery/load/run machinery, versioning policy for the contract itself.

**Does not belong in core:** anything that reflects one flavor's domain
vocabulary or internal data model (CALS namespaces, QRen block types, Eidoa
cognition modules, ML Filesystem tiers, etc.). Those stay in the flavor's
own repo and are reached only through `entrypoint`. If a concept from one
stack repo starts looking like it should live in core, the test is: does a
second, unrelated flavor need the *same* mechanism, not just something that
rhymes with it? If not, it stays out.

## Porting a flavor in, or out

**In:** write a `flavor.toml` + entrypoint module next to the existing
code (no restructuring required), run `vanilla-core check` against it,
fix whatever the floor flags, then `vanilla-core run`.

**Out:** because the contract is just a TOML file plus one Python callable,
a flavor built against Vanilla Core has no import-time dependency on this
package beyond `tomllib` (stdlib) — it can be lifted into a different host
engine, or run standalone, by anything willing to read `flavor.toml` and
call the entrypoint the same way. Portability is a property of keeping the
contract this small, not a separate feature to build.

## Composite / "Mad Scientist" runs

Nothing here currently orchestrates *multiple* flavors composed together —
v0.1 runs one flavor at a time by design, so the composition contract stays
minimal while real ports are still happening. A composite runner (loading
several flavors and combining their `run()` outputs, per repo, per stack) is
the natural v0.2 once there are at least two real (non-example) flavors
ported in to design the composition contract against real usage rather than
speculatively.
