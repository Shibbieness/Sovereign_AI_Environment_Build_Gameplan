# FORGE.md — GILWRIGHT standing mission (FLAVORED instance)
[block: ice] v0u1p0 · M MAOU LLC · Shibbieness

## Mission
Convert spare usage into shipped, sellable vanilla assets. Build unattended;
Mark ships (~20 min/product). The ledger stays honest or the factory stops.

## Roles (CALS namespace, closed)
Scout scores candidates · Wright builds · Scrubber vanilla-izes · Clerk closes
every session (CASL floor) · Witness = Mark: ships, kills, and is the only
entity that touches accounts or money.

## Constraints C1-C5
C1 agent builds, Witness ships · C2 honest append-only ledger · C3 cold-resumable
via STATUS.md · C4 products ship vanilla, factory runs flavored · C5 one product
in ICE at a time.

## Product lifecycle
AMORPHOUS (idea) → ICE (spec frozen, being built) → CRYSTAL (shipped) or VOID
(killed after two zero-signal review cycles). Ledger and shipped dist/ are
NADA_PROTECTED. Ghost BONE rules on VOID with dependents.

## Session loop
read STATUS.md → one task → build to clean boundary → Clerk pass → stop.
Cut off mid-task? continue-skill-port.md: verify state before producing anything.

## Task wire format (entries arriving from the forge side)
TITLE / SPEC (≤1 page) / ACCEPTANCE / BLOCK TYPE. Append to db + product task
list verbatim. No reinterpretation.

## Appendix A — Scrub checklist
S1 zero canonical-term hits in dist/ (term list: Appendix B) · S2 no [block:],
[qren:], runic glyphs, or VUP strings · S3 stranger-readable README · S4 no
internal paths · S5 license present · S6 byline per product (ask via hands_queue
if unset) · S7 behavior identical to flavored source.

## Appendix B — Canonical term list (grep targets for the scrub)
M MAOU, Shibbieness, PseudoSkill, CALS, CASL, Runic, QRen, QRCF, LMAOU, Materia,
dRAM, AiDEA, ODIIS, LEXIS, AUDIT, VI Builder, Cal's Castle, Unscheduled Echo,
EExpand, Helix, LATTICE, WEAVE, BLOOM, Crystal Slime, NADA_PROTECTED, Ghost BONE,
CRUCIBLE, GILWRIGHT, VUP, AiCircle, admathCircle, ArGlyph, Eid, Eidos.
(Extend when leaks are found. A leak found post-ship = patch version.)

## Appendix C — db quick reference
Tables: products, sessions, tasks, artifacts, hands_queue, ledger (append-only,
triggers enforce). View: ledger_summary. Clerk inserts sessions + usage_estimate
every session, no exceptions.

—Shibbieness
—Claude
