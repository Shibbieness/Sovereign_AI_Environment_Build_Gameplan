# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/); versioning follows
[SemVer](https://semver.org/) once there's a public consumer to break.

## [0.1.0] - 2026-08-07

### Added
- Initial scaffold: `vanilla_core` package (`manifest`, `floor`, `registry`,
  `cli`) — a stdlib-only flavor-plugin engine with an enforced minimum floor
  (name, version, known license, resolvable entrypoint, no vendor
  attribution markers).
- `examples/hello_flavor` — a minimal working flavor proving discover →
  floor-check → load → run end to end.
- Test suite (`tests/`, stdlib `unittest`) covering the floor check and the
  registry.
- CI workflow running the test suite and the floor check against every
  example flavor on every push/PR.
- `LICENSE` (AGPL-3.0-or-later) and `LICENSE-COMMERCIAL.md` (placeholder
  dual-license terms).
- `STANDARDS.md`, `ARCHITECTURE.md`, `NOTICE.md`, `CONTRIBUTING.md`.
- `ATTRIBUTION.md` — a small AGPL-3.0 §7(b) notice-preservation requirement
  for free use, and a larger revenue-triggered credit obligation carried by
  the commercial license instead (kept out of the AGPL side deliberately, to
  avoid badgeware and stay GPL-compatible).

### Changed
- Floor markers narrowed from blanket vendor-name matching to specific leak
  patterns (vendor contact address, private session link, shared-conversation
  link, vendor co-author trailer). A flavor that legitimately integrates a
  vendor API can now declare that without tripping the floor.
