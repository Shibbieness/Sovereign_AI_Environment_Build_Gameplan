# HANDS.md — ship-time actions for vanilla-weave ("ragready")
[block: ice] v0u1p0

Click-level actions only. No judgment calls beyond what's marked. Mirrors
hands_queue rows in gilwright.db (product: vanilla-weave) — that table is
the source of truth; this file is the human-readable copy.

1. ~~Decide the byline.~~ **DONE 2026-08-11 — "Shibbieness".** Mark's
   decision, executed: `dist/` now carries
   `Copyright (c) 2026 Shibbieness · M MAOU LLC` in NOTICE.md and in both
   source headers.

   The licence changed with it. `dist/LICENSE` was MIT, which let anyone
   take the tool closed-source — directly against the stack rule that what
   is built on it stays free. It is now **AGPL-3.0-or-later with a
   commercial option**, the same model as the rest of the stack, per Mark's
   decision. `dist/LICENSE-COMMERCIAL.md` added.
2. Pick a distribution channel (gumroad / itch.io / GitHub release / other).
3. Create or reuse the storefront listing for that channel.
4. Upload the contents of `dist/` as the downloadable package (zip
   `ragready.py`, `ragready_common.py`, `example.md`, `README.md`,
   `LICENSE` together, or point to a repo release — either is fine, dist/
   is self-contained either way).
5. Set price (Scout's queue estimate: free-or-pay-what-you-want tool, or a
   few dollars — a two-file stdlib script is not a $20 product; Mark's
   call).
6. Paste `README.md`'s content (or a trimmed version of it) into the
   listing description.
7. Publish.
8. Report back the channel + listing URL so Clerk can log a `revenue`/
   `channel_fee` ledger row once there's real signal, and so the product's
   `channel` column in `products` can be set.

Nothing above requires touching src/, FLAVOR.md, or anything outside
dist/ — dist/ is exactly what gets uploaded, unmodified except for step 1.
