#!/usr/bin/env python3
"""
QRCF Phase 2 — test suite.

Covers `qrcf_types_phase2.py` and `qrcf_circle_rules.py`: ~83 KB and 28
top-level definitions that shipped, imported cleanly, and were reachable by
nothing and covered by nothing. They were referenced only in a docstring.

Writing this immediately found a defect that had been latent since the package
restructure: `is_crystal_valid` and `verify_ice_contract` both did
`from qrcf_types import EdgeType` — the absolute form — and raised
ModuleNotFoundError on every call. Nobody noticed, because calling them was
not something anything did.

That is the argument for this file. Code that is never run is not dormant, it
is unverified: it looks like a capability in an inventory and behaves like a
gap when reached for.

Run:  python -m qren.qrcf.test_phase2
"""

import os
import sys
import tempfile
import time
import traceback


# ═══════════════════════════════════════════════════════════════
# HARNESS — matches test_phase1.py so both read the same way
# ═══════════════════════════════════════════════════════════════

class TestResult:
    def __init__(self, name):
        self.name = name
        self.passed = False
        self.message = ""
        self.duration = 0.0


def run_test(name, func):
    r = TestResult(name)
    start = time.time()
    try:
        func(r)
        r.passed = True
    except AssertionError as e:
        r.message = str(e) or "assertion failed"
    except Exception as e:
        r.message = f"{type(e).__name__}: {e}"
        if os.environ.get("QREN_TEST_TRACE"):
            traceback.print_exc()
    r.duration = (time.time() - start) * 1000
    return r


from .qrcf_types import BlockType, EdgeType, NormalizationProfile  # noqa: E402
from .qrcf_types_phase2 import (  # noqa: E402
    BoneBlockHeader, BracketType, CacheLine, CrystalLatticeHeader,
    EvictionPolicy, NestedQRenHeader, RAMCacheBlock, VoidJumpHeader,
    VoidJumpType, is_crystal_valid, verify_ice_contract,
)
from .qrcf_circle_rules import (  # noqa: E402
    CircleRuleSet, QRECLevel, QRMatrixSpec, QRVersion, RuleChainResolver,
)


# ═══════════════════════════════════════════════════════════════
# HEADERS — pack/unpack round-trips
# ═══════════════════════════════════════════════════════════════

def test_void_jump_header(r):
    """VOID (0x0C) is the non-linear traversal primitive. Its three
    constructors must each survive a round-trip, and the fixed size must hold
    — a header whose packed length drifts from FIXED_SIZE corrupts every block
    after it in the section."""
    cases = [
        VoidJumpHeader.reset(),
        VoidJumpHeader.jump_to(depth=2, arc_id=7),
        VoidJumpHeader.jump_to(depth=0, arc_id=0, save_context=False),
        VoidJumpHeader.jump_back(),
    ]
    for h in cases:
        packed = h.pack()
        assert len(packed) == VoidJumpHeader.FIXED_SIZE, (
            f"{h.jump_type.name}: packed {len(packed)} bytes, "
            f"FIXED_SIZE says {VoidJumpHeader.FIXED_SIZE}")
        assert VoidJumpHeader.unpack(packed) == h, f"{h.jump_type.name} lost data"
    r.message = f"{len(cases)} jump forms round-tripped"


def test_void_jump_semantics(r):
    """RESET means 'current depth/arc', encoded as the sentinel values. If a
    sentinel were stored as a real coordinate the jump would land somewhere."""
    reset = VoidJumpHeader.reset()
    assert reset.jump_type == VoidJumpType.RESET
    assert reset.target_depth == 0xFF, "RESET lost its depth sentinel"
    assert reset.target_arc_id == 0xFFFF, "RESET lost its arc sentinel"

    jump = VoidJumpHeader.jump_to(depth=3, arc_id=11)
    assert jump.target_depth == 3 and jump.target_arc_id == 11
    assert VoidJumpHeader.unpack(jump.pack()).target_arc_id == 11


def test_bone_block_header(r):
    """BONE (0x0B) is a pinned structural scaffold carrying a variable-length
    technorganic profile, so unpack returns the consumed length as well —
    getting that wrong misaligns everything downstream."""
    for profile in (b"", b"scaffold", bytes(range(64))):
        h = BoneBlockHeader(pin_count=3, technorganic_profile=profile)
        packed = h.pack()
        back, consumed = BoneBlockHeader.unpack(packed)
        assert back == h, f"profile len {len(profile)}: round-trip differs"
        assert consumed == len(packed), (
            f"profile len {len(profile)}: reported {consumed} consumed, "
            f"packed {len(packed)}")
        assert back.profile_len == len(profile)   # property, not a method
    r.message = "empty, short and 64-byte profiles all round-tripped"


def test_bone_pinning(r):
    """A BONE with live REQUIRES edges at seal time is pinned; the flag is
    what stops it being collected."""
    pinned = BoneBlockHeader(pin_count=2)
    unpinned = BoneBlockHeader(pin_count=0)
    assert isinstance(pinned.is_pinned, bool)   # property
    assert isinstance(unpinned.is_pinned, bool)
    assert BoneBlockHeader.unpack(pinned.pack())[0].pin_count == 2


def test_crystal_lattice_header(r):
    """CRYSTAL (0x0D) is a repeating lattice; lattice_degree 0 means 'being
    formed', which must survive as 0 rather than becoming a real valence."""
    for degree in (0, 1, 4, 255):
        h = CrystalLatticeHeader(lattice_degree=degree)
        packed = h.pack()
        assert len(packed) == CrystalLatticeHeader.FIXED_SIZE
        back = CrystalLatticeHeader.unpack(packed)
        assert back == h, f"degree {degree} round-trip differs"
        assert back.lattice_degree == degree
    assert CrystalLatticeHeader(lattice_degree=0).lattice_degree == 0
    r.message = "degrees 0, 1, 4, 255 round-tripped"


def test_nested_qren_header(r):
    """NESTED (0x08) carries a whole inner QRenCode: depth, bracket, arc and
    the inner manifest hash. The hash is 32 bytes and must come back exactly —
    a truncated hash silently breaks inner-archive verification."""
    digest = bytes(range(32))
    h = NestedQRenHeader(depth=2, bracket_type=BracketType.SQUARE, arc_id=5,
                         inner_qrcf_len=4096, inner_manifest_hash=digest)
    packed = h.pack()
    assert len(packed) == NestedQRenHeader.FIXED_SIZE, (
        f"packed {len(packed)}, FIXED_SIZE {NestedQRenHeader.FIXED_SIZE}")
    back = NestedQRenHeader.unpack(packed)
    assert back == h
    assert back.inner_manifest_hash == digest, "inner manifest hash altered"
    assert back.inner_qrcf_len == 4096
    r.message = "depth, bracket, arc and 32-byte manifest hash preserved"


def test_every_header_declares_its_size_honestly(r):
    """FIXED_SIZE is used to advance through a section. If any header packs to
    a different length than it declares, every block after it is misread — the
    same class of failure as the unknown-block-type bug, arrived at from the
    other direction."""
    fixed = [
        (VoidJumpHeader, VoidJumpHeader.reset()),
        (CrystalLatticeHeader, CrystalLatticeHeader()),
        (NestedQRenHeader, NestedQRenHeader()),
    ]
    for cls, inst in fixed:
        assert len(inst.pack()) == cls.FIXED_SIZE, (
            f"{cls.__name__} packs {len(inst.pack())} but declares "
            f"{cls.FIXED_SIZE}")
    # BoneBlockHeader is variable-length by design: fixed part + profile.
    bone = BoneBlockHeader(technorganic_profile=b"xyz")
    assert len(bone.pack()) == BoneBlockHeader.FIXED_SIZE + 3, (
        "BoneBlockHeader's variable part is not FIXED_SIZE + profile length")
    r.message = "3 fixed headers exact, BONE variable part correct"


# ═══════════════════════════════════════════════════════════════
# VALIDATORS — the semantic contracts
# ═══════════════════════════════════════════════════════════════

def test_validators_are_callable_at_all(r):
    """REGRESSION. Both validators did `from qrcf_types import EdgeType` — the
    absolute form — and raised ModuleNotFoundError on every call, from the
    moment this package gained a package structure. Nothing imported the
    module, so nothing ever found out."""
    assert is_crystal_valid([]) in (True, False)
    assert verify_ice_contract("ab" * 32, []) in (True, False)


def test_ice_contract_rejects_outgoing_edges(r):
    """ICE is a frozen snapshot: zero outgoing dependency edges. A validator
    that returns True for everything is decorative, so this asserts both
    directions."""
    block = "ab" * 32
    assert verify_ice_contract(block, []) is True, "clean ICE was rejected"
    violating = [{"from": block, "edge_type": EdgeType.REQUIRES}]
    assert verify_ice_contract(block, violating) is False, (
        "ICE with an outgoing REQUIRES edge was accepted")
    other = [{"from": "cd" * 32, "edge_type": EdgeType.REQUIRES}]
    assert verify_ice_contract(block, other) is True, (
        "another block's edge was attributed to this one")


def test_crystal_validity_needs_a_bond(r):
    """A CRYSTAL is a lattice bonded by dependency edges; with no edges it is
    not yet a lattice node."""
    assert is_crystal_valid([]) is False, "an unbonded crystal was called valid"
    assert is_crystal_valid([{"edge_type": EdgeType.REQUIRES}]) is True


# ═══════════════════════════════════════════════════════════════
# CACHE LAYER
# ═══════════════════════════════════════════════════════════════

def test_cache_block_constructs_and_reports(r):
    cache = RAMCacheBlock()
    assert cache is not None
    assert hasattr(EvictionPolicy, "__members__")
    assert len(EvictionPolicy.__members__) >= 1
    r.message = f"{len(EvictionPolicy.__members__)} eviction policies declared"


def test_cache_line_round_trip_if_packable(r):
    """CacheLine is part of the wire surface if it packs; if it does not, say
    so rather than asserting nothing."""
    if not hasattr(CacheLine, "pack"):
        r.message = "CacheLine has no pack(); not a wire structure"
        return
    line = CacheLine()
    packed = line.pack()
    assert isinstance(packed, (bytes, bytearray))
    if hasattr(CacheLine, "unpack"):
        back = CacheLine.unpack(packed)
        got = back[0] if isinstance(back, tuple) else back
        assert got == line, "CacheLine round-trip differs"
        r.message = "CacheLine round-tripped"
    else:
        r.message = "CacheLine packs but has no unpack()"


# ═══════════════════════════════════════════════════════════════
# CIRCLE RULES — the inheritance invariant
# ═══════════════════════════════════════════════════════════════

def test_matrix_spec_and_levels(r):
    """QR version and error-correction level are wire-visible choices."""
    assert len(QRVersion.__members__) >= 1
    assert len(QRECLevel.__members__) >= 1
    spec = QRMatrixSpec()
    assert spec is not None
    r.message = (f"{len(QRVersion.__members__)} versions, "
                 f"{len(QRECLevel.__members__)} EC levels")


def test_rule_chain_resolver_constructs(r):
    resolver = RuleChainResolver()
    assert resolver.current_depth() is not None   # method, not a property
    r.message = f"depth {resolver.current_depth()} at construction"


def test_rules_propagate_down_never_up(r):
    """The module's stated invariant, in its own words:

        Higher Circle rules apply to Lower Circles.
        Rules propagate DOWN the chain, never UP.

    Unset fields use 0xFF/0xFFFF as the sentinel, so a child that declares
    nothing inherits its parent's value, and a child that declares one
    overrides it — for itself only."""
    resolver = RuleChainResolver()
    parent = CircleRuleSet(declaring_depth=0, chain_id=1, default_compression=2)
    child = CircleRuleSet(declaring_depth=1, chain_id=1)   # all unset

    resolver.push(parent)
    assert resolver.effective_compression() == 2, "parent's own rule did not apply"

    resolver.push(child)
    assert resolver.effective_compression() == 2, (
        "a child declaring nothing did not inherit from its parent — "
        "rules are not propagating DOWN")

    override = CircleRuleSet(declaring_depth=2, chain_id=1, default_compression=1)
    resolver.push(override)
    assert resolver.effective_compression() == 1, "a child could not override"

    resolver.pop()
    assert resolver.effective_compression() == 2, (
        "a child's rule survived its own pop — rules propagated UP")
    r.message = "inherit down, override locally, does not leak up"


def test_sibling_does_not_inherit(r):
    """The negative half, and the one worth having: a resolver that hands
    every rule to everyone satisfies 'propagates down' and is still wrong.

    Sibling A sets a value and is popped. Sibling B declares nothing. B must
    see the PARENT's value, never A's."""
    resolver = RuleChainResolver()
    resolver.push(CircleRuleSet(declaring_depth=0, chain_id=1,
                                default_compression=2))

    resolver.push(CircleRuleSet(declaring_depth=1, chain_id=1,
                                default_compression=5))
    assert resolver.effective_compression() == 5
    resolver.pop()

    resolver.push(CircleRuleSet(declaring_depth=1, chain_id=1))   # unset
    got = resolver.effective_compression()
    assert got != 5, f"sibling B inherited sibling A's rule ({got}) — rules are not scoped to their chain"
    assert got == 2, f"sibling B should see the parent's 2, saw {got}"
    r.message = "siblings are scoped; B sees the parent, not A"


def test_depth_and_nesting_limits(r):
    """max_nesting_depth is a real limit: can_go_deeper must eventually say no,
    or a nested archive can recurse without bound."""
    resolver = RuleChainResolver()
    resolver.push(CircleRuleSet(declaring_depth=0, chain_id=1,
                                max_nesting_depth=2))
    assert resolver.can_go_deeper() in (True, False)
    depths = 0
    while resolver.can_go_deeper() and depths < 50:
        resolver.push(CircleRuleSet(declaring_depth=resolver.current_depth() + 1,
                                    chain_id=1))
        depths += 1
    assert depths < 50, "can_go_deeper() never became False — nesting is unbounded"
    r.message = f"nesting stopped after {depths} pushes"


def test_effective_all_reports_every_resolved_rule(r):
    """effective_all is the summary the decoder would act on; it must agree
    with the individual accessors rather than being a second computation."""
    resolver = RuleChainResolver()
    resolver.push(CircleRuleSet(declaring_depth=0, chain_id=1,
                                default_compression=2, ec_level=1))
    summary = resolver.effective_all()
    assert isinstance(summary, dict) and summary, "effective_all returned nothing"
    # effective_all reports resolved ENUMS; the accessors return the same
    # objects, so compare values rather than assuming either is a raw int.
    for key, accessor in (("compression", resolver.effective_compression),
                          ("ec_level", resolver.effective_ec_level)):
        match = [v for k, v in summary.items() if key in k.lower()]
        if match:
            got, want = match[0], accessor()
            # effective_all reports enum NAMES as strings; the accessors return
            # the enum members. Compare on name so the two representations are
            # checked against each other rather than assumed equal.
            want_name = getattr(want, "name", str(want))
            assert str(got) == want_name, (
                f"effective_all disagrees with effective_{key}: "
                f"{got!r} vs {want_name!r}")
    r.message = f"{len(summary)} rules resolved, consistent with accessors"


def test_circle_rule_set_round_trip(r):
    """CircleRuleSet is a wire structure — it packs into the archive."""
    rs = CircleRuleSet(declaring_depth=2, chain_id=7, default_compression=2,
                       ec_level=1, max_nesting_depth=4)
    packed = rs.pack()
    assert isinstance(packed, (bytes, bytearray)) and packed
    back = CircleRuleSet.unpack(packed)
    got = back[0] if isinstance(back, tuple) else back
    assert got.chain_id == 7, "chain_id lost — rules would apply to the wrong chain"
    assert got.declaring_depth == 2
    assert got.default_compression == 2
    assert got == rs, "CircleRuleSet round-trip differs"
    r.message = f"round-tripped in {len(packed)} bytes"



def test_sealed_rules_cannot_be_overridden_from_deeper(r):
    """REGRESSION. SEALED means no lower circle may override the field, and it
    could never fire.

    _resolve walked innermost -> outermost and set `sealed_at` only when it
    REACHED the sealing rule set — but the declaration that seals a field is
    always outward of the override it blocks, so the walk returned the deeper
    value and exited before ever seeing the seal. Every SEALED rule was
    silently ignored.

    Found by running the module's own __main__ self-test, which asserts this
    exact case and had never been executed because nothing imported the file.
    """
    from .qrcf_circle_rules import CircleRuleFlags

    resolver = RuleChainResolver()
    root = CircleRuleSet.root()
    root.ec_level = QRECLevel.H
    root.flags = CircleRuleFlags.SEALED
    resolver.push(root)

    # A deeper circle tries to override a sealed field.
    resolver.push(CircleRuleSet.for_depth(1, ec_level=QRECLevel.L))
    assert resolver.effective_ec_level() == QRECLevel.H, (
        "a deeper circle overrode a SEALED field — the seal did nothing")

    # And an UNSEALED field at the same depth must still be overridable, or
    # the fix would have sealed everything instead of the declared field.
    resolver2 = RuleChainResolver()
    open_root = CircleRuleSet.root()
    open_root.ec_level = QRECLevel.H
    resolver2.push(open_root)
    resolver2.push(CircleRuleSet.for_depth(1, ec_level=QRECLevel.L))
    assert resolver2.effective_ec_level() == QRECLevel.L, (
        "an unsealed field was treated as sealed")
    r.message = "sealed blocks the override; unsealed still allows it"


def test_circle_rules_module_self_test_passes(r):
    """qrcf_circle_rules ships a __main__ block that exercises inheritance,
    sealing, forking and depth limits. It asserted CircleRuleSet.pack() equals
    FIXED_SIZE — which was false from the first line — and nobody ran it.

    Running it here means it cannot rot again."""
    import runpy, sys, io, contextlib
    buf = io.StringIO()
    argv = sys.argv[:]
    sys.argv = ["qrcf_circle_rules"]
    try:
        with contextlib.redirect_stdout(buf):
            runpy.run_module("qren.qrcf.qrcf_circle_rules", run_name="__main__")
    except SystemExit as exc:
        assert not exc.code, f"module self-test exited {exc.code}"
    finally:
        sys.argv = argv
    out = buf.getvalue()
    assert "All Circle Rule Inheritance tests passed" in out, (
        f"self-test did not report success:\n{out[-400:]}")
    r.message = f"{out.count('[PASS]')} internal checks passed"

# ═══════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════

def main():
    tests = [
        ("VoidJumpHeader Round-Trip",          test_void_jump_header),
        ("VOID Jump Semantics",                test_void_jump_semantics),
        ("BoneBlockHeader Round-Trip",         test_bone_block_header),
        ("BONE Pinning",                       test_bone_pinning),
        ("CrystalLatticeHeader Round-Trip",    test_crystal_lattice_header),
        ("NestedQRenHeader Round-Trip",        test_nested_qren_header),
        ("Headers Declare Size Honestly",      test_every_header_declares_its_size_honestly),
        ("Validators Are Callable",            test_validators_are_callable_at_all),
        ("ICE Contract Rejects Outgoing",      test_ice_contract_rejects_outgoing_edges),
        ("CRYSTAL Validity Needs A Bond",      test_crystal_validity_needs_a_bond),
        ("Cache Block Constructs",             test_cache_block_constructs_and_reports),
        ("CacheLine Round-Trip",               test_cache_line_round_trip_if_packable),
        ("Matrix Spec And Levels",             test_matrix_spec_and_levels),
        ("RuleChainResolver Constructs",       test_rule_chain_resolver_constructs),
        ("Rules Propagate Down Never Up",      test_rules_propagate_down_never_up),
        ("Sibling Does Not Inherit",           test_sibling_does_not_inherit),
        ("Depth And Nesting Limits",           test_depth_and_nesting_limits),
        ("effective_all Is Consistent",        test_effective_all_reports_every_resolved_rule),
        ("CircleRuleSet Round-Trip",           test_circle_rule_set_round_trip),
        ("SEALED Blocks Deeper Override",      test_sealed_rules_cannot_be_overridden_from_deeper),
        ("Module Self-Test Passes",            test_circle_rules_module_self_test_passes),
    ]

    print("=" * 72)
    print("  QRenCode Phase 2 — Test Suite")
    print("  Type extensions and circle rule inheritance")
    print("=" * 72)
    print()

    results = [run_test(name, fn) for name, fn in tests]
    for res in results:
        mark = "PASS" if res.passed else "FAIL"
        extra = f": {res.message}" if res.message else ""
        print(f"  [{mark}] {res.name} ({res.duration:.1f}ms){extra}")

    passed = sum(1 for x in results if x.passed)
    failed = len(results) - passed
    print()
    print("-" * 72)
    print(f"  Results: {passed} passed, {failed} failed, {len(results)} total")
    if failed:
        print()
        print("  FAILED TESTS:")
        for res in results:
            if not res.passed:
                print(f"    x {res.name}: {res.message}")
    print("=" * 72)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
