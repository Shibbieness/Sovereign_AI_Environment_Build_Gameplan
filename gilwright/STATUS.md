# STATUS — GILWRIGHT factory
[block: flame] Updated: 2026-07-26 (Phase 1 — first product built)

## HANDS QUEUE (Mark — do these, in order)
Product: vanilla-weave (ships as "ragready"). Mirrors hands_queue table,
product_id=1 in gilwright.db.
1. Decide byline (real name / Shibbieness / M MAOU LLC); edit
   `products/vanilla-weave/dist/LICENSE` placeholder.
2. Pick a distribution channel (gumroad / itch.io / GitHub release / other).
3. Create or reuse the storefront listing.
4. Upload `products/vanilla-weave/dist/` contents as the package.
5. Set price.
6. Paste `dist/README.md` content into the listing description.
7. Publish.
8. Report channel + listing URL back so Clerk can log revenue/channel_fee rows.
Full detail: `products/vanilla-weave/HANDS.md`.

## Active product
**vanilla-weave** ("ragready") — lifecycle: ICE (built, awaiting ship).
Source: lattice/cli/weave_validate.py + lattice_common.py. A dependency-free
Python tool that checks whether a markdown doc is structured well enough to
chunk/embed for RAG. src/ has the flavored source; dist/ has the scrubbed,
verified-standalone product (ragready.py, ragready_common.py, README.md,
LICENSE, example.md). FLAVOR.md documents the scrub mapping. This is the
only product in ICE — per C5, no new product starts until this one reaches
CRYSTAL (shipped) or VOID.

Next action: this product is done from the Wright/Scrubber side. It is
sitting in hands_queue waiting on Mark (Witness) to ship per HANDS.md. No
further agent-side build work on vanilla-weave until Mark reports back
(step 8) or asks for a revision.

## Last session
2026-07-26 · product: vanilla-weave · clean_boundary=1 (session ended clean,
no continue-skill needed) · commit_hash: pending (see git log after this
Clerk pass commits). Summary: scrubbed WEAVE→ragready (S1-S7 checklist run
and passed — zero canonical-term/VUP/internal-path hits in dist/, functional
diff confirmed identical to flavored source via a passing fixture and a
correctly-failing fixture), wrote FLAVOR.md + HANDS.md, seeded db (products,
tasks, artifacts, hands_queue, sessions, ledger rows — ledger append-only
trigger re-verified intact).

## Open questions for Mark (non-blocking)
- S6 byline choice for vanilla-weave (hands_queue item 1) — no product ships
  without this.
- Whether to follow up with a `vanilla-bloom` product (BLOOM's 12-stage
  corpus check, composes WEAVE across a directory) once vanilla-weave has
  shipped and there's a read on demand — noted in FLAVOR.md, not started.

## Resume protocol
Read this file top to bottom. If "Last session" says clean_boundary=0, apply
skill-ports/continue-skill-port.md before building anything.
