"""
Helix — the first implementation artifact from the helix-pseudoskill's
Codex. The skill itself is architecture-only (14 Codex stages, zero code
anywhere) but converges, across multiple canonical documents, on one
specific starting point: menucode_validate.py, checking the Custom Third
Set spec's 8 formatting conventions.

  menucode_third_set.py   — the canonical Vanilla reference file, pulled
                             verbatim from menucode_documentation.md
                             Section X.1 (it was already complete,
                             runnable Python sitting in the doc).
  menucode_validate.py     — validates a file against the 8 documented
                             conventions (Section XI). Real AST + regex
                             checks, not a stub.
"""
