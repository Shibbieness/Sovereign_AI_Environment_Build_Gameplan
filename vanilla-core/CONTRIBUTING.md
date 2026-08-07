# Contributing

Vanilla Core is small on purpose. Before adding to it, ask which of these
you're actually doing:

1. **Fixing or hardening the core** (`src/vanilla_core/`) — the manifest
   format, the floor check, the registry/CLI. This should stay generic:
   nothing in `src/vanilla_core/` should reference a specific flavor
   (Eidoa, ML Filesystem, QRen Coder, the Sovereign AI Environment
   gameplan, or anything else) by name or assume its internals.
2. **Building a flavor.** Flavors live outside this repo (or under
   `examples/` if they're purely illustrative) and consume Vanilla Core
   through `flavor.toml` + an entrypoint — they don't need to touch
   `src/vanilla_core/` at all. If you find yourself editing core files to
   make a flavor work, that's a signal the contract is missing something
   generic — raise it as a core change, not a special case.
3. **Something that only two, or only one, flavor will ever need.** That
   almost certainly does not belong in this repo. See `ARCHITECTURE.md`
   "What does and doesn't belong in core."

## Checklist for any change

- `python -m unittest discover -s tests -v` passes.
- Every `flavor.toml` under `examples/` still passes
  `vanilla-core check <path>`.
- No new file introduces a vendor email address, vendor co-author trailer,
  or a link to a private chat session (see `NOTICE.md`). This is checked in
  CI for flavor manifests, not (yet) for arbitrary file content — self-check
  before you commit.
- If you're changing the manifest schema or the floor check, update
  `ARCHITECTURE.md` and bump `CHANGELOG.md` in the same change.

## Commit hygiene

Plain, descriptive commit messages. No AI-vendor attribution trailers, no
session links — see `NOTICE.md` for why.
