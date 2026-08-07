"""
QRen — everything the skill stack's various QRen-named skills describe,
pulled into one place. Self-contained: no import dependency on
sovereign_py/ or vi_builder/; those systems could adopt QRen encoding, but
QRen doesn't require either to exist.

This package now has two layers, deliberately kept separate rather than
forced into one artificial wire format:

  qren/ (this level)     — block_types.py, wire_format.py, tokens.py,
                            crystal_slime.py, magic_circle.py, classifier.py.
                            Implements ml-filesystem-monolith sub-skill C's
                            own magic-circle spec: the 14(+CUSTOM)-type
                            taxonomy, a minimal illustrative wire format
                            (SAIP magic), the TB/EA/IF tokens, Crystal
                            Slime, and the three-mode I/O boundary.

  qren/qrcf/              — vendored verbatim (import-path fixes only) from
                            the qren-coder skill's modules/qren_coder/
                            package: the real, separately-tested QRenCode
                            Container Format (QREN/XQPE magic, PNG+trailer
                            container, Circle 0-3 structure, Merkle
                            integrity, circle-rule inheritance). qren-coder
                            describes this explicitly as "NOT CodexOmega...
                            a standalone format + runtime system" — it was
                            never meant to be the same artifact as the
                            magic-circle demo above, so it isn't force-fit
                            into one.

  classifier.py            — vendored from qren-type-system's Skill #1
                            (block-type-classifier-v1 + Skill #16's
                            auto-detection-ruleset): a deterministic,
                            CASL-floor-tested classifier that reads a
                            file's content/extension and returns a block
                            type with a confidence score. Shares this
                            package's block_types.py registry rather than
                            duplicating it.

Both wire formats independently encode/decode the same conceptual block
type taxonomy; they intentionally do not share bytes on the wire. Bridging
them (translating one container format into the other) is future work if
it's ever actually needed, not assumed here.
"""
