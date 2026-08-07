# Standards scope

A living checklist, not a finished audit. Each row is either enforced today
(by code, in this repo) or planned — flagged honestly rather than claimed.
Grows as real flavors get ported in and reveal what's actually needed,
rather than being fully speculated up front (see `ARCHITECTURE.md`).

## Coding

| Area | Standard / reference | Status |
|---|---|---|
| Versioning | SemVer 2.0.0 for `vanilla_core` itself; `flavor.version` is free-form per flavor | Enforced (policy) |
| Change tracking | Keep a Changelog format, one entry per release | Enforced (`CHANGELOG.md`) |
| Test coverage floor | Every public function in `src/vanilla_core/` has at least one passing/failing test case | Enforced (`tests/`) |
| CI gate | Tests + floor check run on every push/PR | Enforced (`.github/workflows/ci.yml`) |
| Dependency footprint | Zero runtime dependencies (stdlib only), consistent with the rest of the M MAOU stack (ASSAY, sovereign-py) | Enforced (`pyproject.toml`) |
| Static typing | Type hints throughout; no `mypy`/`pyright` gate wired into CI yet | Partial |
| Style/lint gate | No linter (ruff/black) wired into CI yet | Planned |
| Reproducible builds | `pyproject.toml` + `setuptools`, no pinned lockfile since there are no deps to pin | Enforced |

## Security

| Area | Standard / reference | Status |
|---|---|---|
| Untrusted-input floor | `check_floor` refuses to import/run a flavor with a malformed manifest before any flavor code executes | Enforced |
| Attribution/leak floor | `check_floor` rejects vendor emails and session links in manifest fields | Enforced |
| Secrets scanning | No secret-scanning CI step yet | Planned |
| Dependency/supply-chain scanning (SBOM) | N/A while zero runtime deps; revisit if that changes | N/A for now |
| Least privilege | `load_flavor` only adds the flavor's own directory to `sys.path`, and only for the duration of the import | Enforced |
| OWASP mapping | No network/web surface yet in core itself — revisit against ASVS once a flavor exposes one | Deferred to flavor layer |

## Safety (CASL-floor alignment)

| Area | Standard / reference | Status |
|---|---|---|
| Refuse-by-default on floor violation | `load_flavor` raises rather than silently degrading | Enforced |
| Human-witness gate for destructive/irreversible ops | Not applicable inside `vanilla_core` itself (it has none); applies at the operator level when running this against real infra — see the top-level Claude/agent operating rules, not this repo | N/A in-repo |
| Emergent/ambiguous-state handling (Nada-Protocol-style) | Not built — v0.1 has no persistent state to protect | Planned, once a flavor needs it |

## Legal

| Area | Standard / reference | Status |
|---|---|---|
| License | AGPL-3.0-or-later, dual-licensable commercially | Enforced (`LICENSE`, `LICENSE-COMMERCIAL.md`) — **not attorney-reviewed** |
| Non-affiliation notice | Explicit statement this project has no Anthropic/vendor affiliation | Enforced (`NOTICE.md`) |
| Attribution/provenance in commits | No AI-vendor co-author trailers or session links in commit history going forward | Policy (see `CONTRIBUTING.md`); not currently machine-enforced against commit messages/history — that would need a repo-level CI or pre-receive hook, not yet built |
| Per-flavor license declaration | `flavor.license` required and validated against a known set | Enforced |
| Data handling / privacy | N/A — `vanilla_core` processes no personal data | N/A for now |
| Export/compliance flags | Not evaluated | Deferred until a flavor needs it |

## Business / product

| Area | Standard / reference | Status |
|---|---|---|
| Stability tiers | v0.x = no stability guarantee on the manifest schema beyond "documented in `ARCHITECTURE.md`"; a 1.0.0 tag is the point that changes | Policy |
| Deprecation policy | None needed yet at v0.1 | Deferred |
| Commercial path | Placeholder terms exist (`LICENSE-COMMERCIAL.md`) for when/if paid licensing becomes real | Placeholder |

## Documentation / onboarding

| Area | Standard / reference | Status |
|---|---|---|
| Quickstart | `README.md` | Enforced |
| Architecture decision record | `ARCHITECTURE.md` (single living doc for now; split into dated ADRs if it outgrows one file) | Enforced |
| Contribution guide | `CONTRIBUTING.md` | Enforced |

## Interoperability (the actual "runs everything, ports everywhere" requirement)

| Area | Standard / reference | Status |
|---|---|---|
| Manifest format is engine-agnostic (plain TOML + stdlib import) | See `ARCHITECTURE.md` "Porting a flavor in, or out" | Enforced |
| At least one real (non-example) flavor ported and passing floor+tests | None ported yet — `examples/hello_flavor` is illustrative only | Planned — next real milestone |

## How this file grows

Every time a real flavor gets ported in (Eidoa, ML Filesystem, QRen Coder,
the Sovereign AI Environment gameplan, or anything else), whatever gap it
exposes in this table gets a row and a status, honestly marked. Don't
pre-fill rows for standards nothing here has needed yet — that's how a
standards doc rots out of sync with the code it's supposed to describe.
