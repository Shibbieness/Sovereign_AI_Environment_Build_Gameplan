# PORT: Continue Skill (cutoff recovery) — one page
Source capsule: continue-skill (M MAOU). Distilled for Claude Code.

When resuming after a cutoff or on any cold start:
1. CHECK — inspect actual state (files, db, git log) before producing anything.
   Never trust memory or STATUS.md alone if clean_boundary=0; verify on disk.
2. EDIT — reconcile: mark what is actually done, correct STATUS.md/db to match
   reality. Only then plan.
3. PRINT — produce ONLY what is missing (gap-fill discipline). Never regenerate
   completed work; regeneration is the expensive failure.
4. Work in small increments that each end at a valid state, so the same cutoff
   cannot orphan large work (incremental append).
5. If the primary continuation path fails twice, branch: choose an alternative
   route to the same acceptance criterion and note the branch in STATUS.md.
