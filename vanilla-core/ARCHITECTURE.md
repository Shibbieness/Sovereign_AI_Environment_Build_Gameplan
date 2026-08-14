# Architecture

## What Vanilla Core is

A small, stdlib-only Python engine (Python 3.11+, no runtime dependencies)
that discovers, floor-checks, and runs **flavors** — self-contained pieces of
functionality declared by a `flavor.toml` manifest and one entrypoint
function. It's the shared machine, not any one flavor's logic.

```
flavor.toml  →  FlavorManifest.load()  →  check_floor()  →  load_flavor()  →  flavor.invoke(capability, params)
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
`sys.path`, imports `module`, and returns `callable` unexecuted. The caller
decides when to run it, via `LoadedFlavor.invoke(capability, params)`:

```python
def run(capability: str | None = None, params: dict | None = None) -> dict:
    ...
```

`capability` names which declared capability to exercise; `params` is a
plain dict of arguments. `invoke()` refuses a capability the manifest does
not declare, so a flavor's manifest is an honest description of its surface
rather than documentation that drifts.

The v0.1 contract was `run(capability)` with no way to pass data. Porting
the first real flavor (QRen Coder) immediately proved that insufficient —
which is the case ARCHITECTURE.md said should drive a core change, rather
than special-casing one flavor. `params` was added generically.

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
- No disallowed marker appears in the manifest's own fields: a vendor
  contact address, a private chat-session link, a shared-conversation link,
  or a vendor co-author trailer. These are matched specifically rather than
  by vendor name, so a flavor that legitimately integrates a vendor API can
  still declare that (e.g. `capabilities = ["llm-api-routing"]`).

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

Nothing here orchestrates *multiple* flavors composed together yet. v0.2
runs one flavor at a time by design, so the composition contract stays
minimal while real ports are still happening.

One real flavor (QRen Coder) is in. A composite runner — loading several
flavors and routing between them — is v0.3, gated on a **second** real
flavor existing. The reason for the gate is concrete: designing composition
against a single example produces a contract shaped like that one example.
The first port already demonstrated this in miniature, forcing `params`
into the contract that speculation had missed.

The candidate second flavor is ML Filesystem, because it is the piece that
would consume QRen output rather than merely sitting beside it — a real
data dependency between two flavors is what a composition contract has to
survive.
