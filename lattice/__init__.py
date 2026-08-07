"""
LATTICE — vendored from the lattice skill's cli/ directory (852 lines,
pure stdlib, never previously vendored into a runnable repo).

WEAVE (10-stage) validates that a markdown document is RAG-friendly
substrate: frontmatter, atomicity (no back-references), anchor system,
cross-references, block types, density, provenance, composability, and a
document-level CASL floor sweep.

BLOOM (12-stage) validates that a *corpus* of WEAVE-compliant docs is
runnable as an SLM/daemon pipeline: parses ⟨SLM⟩ ⟨CORPUS⟩ ⟨DAEMON⟩
⟨EMBED⟩ Runic-token blocks (a different token namespace from QRen's
⟨TB⟩⟨EA⟩⟨IF⟩ — LATTICE and QRen each define their own), checks SLM id
uniqueness, Castle-residency principle/floor requirements, dRAM bindings,
fusion-graph referents, corpus size, and CALS route conflicts.

lattice/cli/*.py preserve their original direct-script import style
(sys.path.insert of their own directory) rather than being rewritten to
package-relative imports — that's how they're designed to run standalone,
and rewriting them wasn't necessary to make them work.
"""
