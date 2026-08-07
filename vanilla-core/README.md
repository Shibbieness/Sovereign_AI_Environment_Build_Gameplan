# Vanilla Core

The shared, standardized engine behind the M MAOU stack — a small,
dependency-free machine that discovers, floor-checks, and runs **flavors**:
self-contained pieces of functionality from any of the stack's repos
(Sovereign AI Environment, Eidoa, ML Filesystem, QRen Coder, and whatever
comes next), through one stable contract.

The point of "vanilla": nothing in this repo assumes which flavor is
running. Domain vocabulary (CALS namespaces, QRen block types, Eidoa
cognition modules, ML Filesystem tiers...) lives in each flavor's own repo.
Vanilla Core only knows how to find a `flavor.toml`, check it against a
minimum floor, import its entrypoint, and run it. That's what makes it
reusable for "all kinds of stuff" instead of one more flavor with a
different name.

## Quickstart

```bash
cd vanilla-core          # this project lives in a subdirectory of the repo
pip install -e .
vanilla-core list examples/
vanilla-core check examples/hello_flavor/flavor.toml
vanilla-core run examples/hello_flavor/flavor.toml --capability greet
```

Requires Python 3.11+. No runtime dependencies.

## The contract

Every flavor is a directory with a `flavor.toml`:

```toml
[flavor]
name = "some-flavor"
version = "0.1.0"
license = "AGPL-3.0-or-later"
entrypoint = "plugin:run"
capabilities = ["thing-it-can-do"]
```

...and a Python module (`plugin.py` above) exposing the callable named in
`entrypoint`, with the signature `run(capability, params)`. Vanilla Core adds the flavor's directory to `sys.path`,
imports it, and hands back the callable — nothing more. See
`ARCHITECTURE.md` for the full contract, what belongs in core vs. what
belongs in a flavor, and how to port a flavor in or out.

## The floor

Before running anything, Vanilla Core checks a small, non-negotiable floor:
the manifest has a name, version, and recognized license; the entrypoint is
resolvable; and none of the manifest's own fields carry a vendor email
address or a link back to a private chat session. A flavor that fails this
gets refused, not silently degraded. See `vanilla_core/floor.py` and
`STANDARDS.md`.

## License

AGPL-3.0-or-later (`LICENSE`) by default: free to use, modify, and
redistribute — and if you distribute a modified version or run it as a
network service, your version has to stay open under the same terms too.
That's the mechanism behind "free, and what's built with it stays free." A
commercial license that waives that condition is intended to be available
for organizations that want it — see `LICENSE-COMMERCIAL.md` (currently
placeholder terms, not yet attorney-reviewed).

There's also a small attribution requirement: keep the line
`Built on Vanilla Core — © Shibbieness / M MAOU LLC` somewhere a user can
find it (About box, `--version`, docs, or a NOTICE file). That's the whole
obligation for free users — no splash screen, no marketing mention. Larger
commercial products carry a more visible credit; see `ATTRIBUTION.md`.

See `NOTICE.md` for authorship, the non-affiliation statement, and the
provenance note on the license text itself.

## Status

v0.2.0 — the engine runs, and the first real flavor is ported: **QRen
Coder**, driven end to end through Vanilla Core (encode, decode, verify,
block-types, self-test) with 13 adapter tests alongside QRen's own 15.

That port paid for itself immediately: it forced the `params` half of the
contract into existence, and it surfaced a real integrity bug — an adapter
that checked only for raised exceptions reported corrupted archives as
valid, because QRen also signals corruption via a returned `valid=False`.

See `STANDARDS.md` for what's enforced today versus planned. Composite
multi-flavor runs remain deferred until a second real flavor exists to
design that contract against.
