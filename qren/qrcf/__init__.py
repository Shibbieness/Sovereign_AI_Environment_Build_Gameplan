"""
QRCF — QRenCode Container Format v1. Vendored from the qren-coder skill's
modules/qren_coder/ package, which describes it as "NOT CodexOmega... a
standalone format + runtime system." Phase 1 wire format FROZEN, 15/15
tests passing in the original build session (verified again in this repo
by test_phase1.py — see qren/README or the commit that added this).

Distinct from the rest of qren/ (block_types.py, wire_format.py, tokens.py,
magic_circle.py): those implement the *ml-filesystem-monolith* sub-skill C
magic-circle spec's own minimal illustrative wire format, appropriate to
that document's scope. This package is the real, separately-developed,
separately-tested QRenCode format that qren-coder ships. The two were
never meant to be the same artifact — see qren/__init__.py for the full
relationship.

Package contents:
  qrcf_types.py         — Phase 1 FROZEN wire format
  qrcf_encoder.py        — Phase 1 encoder (Circle 0/1/2/3 builders)
  qrcf_decoder.py         — Phase 1 decoder (Profile A/B/C, integrity verification)
  test_phase1.py           — Phase 1 test suite (round-trip verified)
  qrcf_types_phase2.py       — Phase 2 type extensions (predates the LIGHT/0x0E
                                 block type added later in ml-filesystem-monolith
                                 sub-skill C v1u0p1 — BlockType here stops at
                                 CRYSTAL/0x0D + CUSTOM/0xFF, left as vendored)
  qrcf_circle_rules.py         — Circle rule inheritance (CircleRuleSet, RuleChainResolver)
"""

from .qrcf_types import (
    BlockType,
    CompressionTier,
    NormalizationProfile,
    EdgeType,
    QRenError,
    QRenFormatError,
    QRenIntegrityError,
    QRenCompressionError,
    QRenBlockError,
    content_address,
    merkle_root,
    auto_detect_block_type,
    BLOCK_NORMALIZATION,
)
from .qrcf_encoder import QRenEncoder
from .qrcf_decoder import QRenDecoder, decode_file

__version__ = "1.0.0"
__all__ = [
    'QRenEncoder', 'QRenDecoder', 'decode_file',
    'BlockType', 'CompressionTier', 'NormalizationProfile', 'EdgeType',
    'QRenError', 'QRenFormatError', 'QRenIntegrityError',
    'QRenCompressionError', 'QRenBlockError',
    'content_address', 'merkle_root', 'auto_detect_block_type',
]
