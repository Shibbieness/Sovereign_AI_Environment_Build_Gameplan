"""
Runic Boundary — the Python/Runic execution boundary.

Every piece of Python code that crosses into Runic execution goes through
this module. Every Runic result that re-enters Python comes back through it.
Distinct from core/module_path_bridge.py (which aliases import *names*, not
data) and from runic/pyrunic_translator.py (which produces Runic *notation
text*, not execution).

Architecture:

    Python caller
        |
    AiCircle opens              RunicBoundary.__enter__()
        |
    Ingress                     Python -> Rune atoms (RuneTranslator.to_rune)
        |
    @ingress_ready fires
        |
    Process                     Runic execution (RunicEidouron.execute_circle)
        |
    [QRVM_TARGET sections]      Native ArCircle when QRVM exists (OQ-E-002)
        |
    Egress                      Rune atoms -> Python (RuneTranslator.from_rune)
        |
    AiCircle closes             RunicBoundary.__exit__()
        |
    Python result

Scroll point (grammar-level bindings this boundary carries):

    circle_id       = 'runic_boundary_v1'
    circle_type     = AiCircle (ᚨ○ ... ᚨ○0)
    ingress_accepts = Python: any, QRCF: bytes
    egress_produces = Python: any, QRCF: bytes
    timing_slots    = @ingress_ready, @process_complete, @egress_ready,
                       @api_window, @embed_ready
    grammar_version = ArCircle grammar, January 2026
    runic_tokens    = TB, EA, IF
    qrvm_required   = False (Python DSL active)
    qrvm_target     = True ([QRVM_TARGET] sections await OQ-E-002)

Futhark ring (from the magic circle spec):
    Outer (AiCircle):    Ansuz/Anchor, Othala/Knowledge, Mannaz/Mirror, Dagaz/Domain
    Inner (admathCircle): Raidho/Root, Gebo/Gate, Kenaz/Cache, Berkano/Birth
"""

from contextlib import ContextDecorator
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from runic.runic_native_subsystem import Rune, RuneTranslator, RunicEidouron

SCROLL = {
    'circle_id': 'runic_boundary_v1',
    'circle_type': 'AiCircle',
    'ingress_accepts': {'python': 'any', 'qrcf': 'bytes'},
    'egress_produces': {'python': 'any', 'qrcf': 'bytes'},
    'timing_slots': ['@ingress_ready', '@process_complete', '@egress_ready',
                      '@api_window', '@embed_ready'],
    'grammar_version': 'ArCircle grammar, January 2026',
    'runic_tokens': ['TB', 'EA', 'IF'],
    'qrvm_required': False,
    'qrvm_target': True,
}

# QRCF wire format leads with a SAIP magic byte sequence; used to detect
# Mode 2 (native QRCF bytes) vs Mode 1 (plain Python values) at ingress.
_SAIP_MAGIC = b'SAIP'


class IOMode(Enum):
    """Which direction(s) of the boundary a call is actually crossing."""
    MODE_1 = 'python_to_python'     # Natural language / plain values both ways
    MODE_2 = 'qrcf_to_qrcf'         # Native QRCF bytes, detected by SAIP magic
    MODE_3A = 'python_to_qrcf'      # Python in, QRCF bytes out
    MODE_3B = 'qrcf_to_python'      # QRCF bytes in, Python out


@dataclass
class TimingSlot:
    """A single named point in the boundary lifecycle."""
    name: str
    fired: bool = False
    callbacks: List[Callable] = field(default_factory=list)

    def register(self, callback: Callable):
        self.callbacks.append(callback)

    def fire(self, *args, **kwargs):
        self.fired = True
        for callback in self.callbacks:
            callback(*args, **kwargs)


class TimingTable:
    """Registry of the 5 boundary timing slots and their callbacks."""

    SLOT_NAMES = ['@ingress_ready', '@process_complete', '@egress_ready',
                  '@api_window', '@embed_ready']

    def __init__(self):
        self.slots: Dict[str, TimingSlot] = {
            name: TimingSlot(name) for name in self.SLOT_NAMES
        }

    def at(self, slot_name: str):
        """Decorator: register a function as a callback for a timing slot."""
        if slot_name not in self.slots:
            raise ValueError(f"Unknown timing slot: {slot_name!r}. Valid: {self.SLOT_NAMES}")

        def decorator(fn):
            self.slots[slot_name].register(fn)
            return fn
        return decorator

    def fire(self, slot_name: str, *args, **kwargs):
        if slot_name in self.slots:
            self.slots[slot_name].fire(*args, **kwargs)

    def status(self) -> Dict[str, bool]:
        return {name: slot.fired for name, slot in self.slots.items()}


@dataclass
class BoundaryResult:
    """What a RunicBoundary pass produces."""
    value: Any
    io_mode: IOMode
    ingress_rune: Optional[Rune] = None
    egress_rune: Optional[Rune] = None
    timing_status: Dict[str, bool] = field(default_factory=dict)


def _detect_io_mode(value: Any, want_qrcf_out: bool) -> IOMode:
    is_qrcf_in = isinstance(value, (bytes, bytearray)) and bytes(value[:4]) == _SAIP_MAGIC
    if is_qrcf_in and want_qrcf_out:
        return IOMode.MODE_2
    if is_qrcf_in and not want_qrcf_out:
        return IOMode.MODE_3B
    if not is_qrcf_in and want_qrcf_out:
        return IOMode.MODE_3A
    return IOMode.MODE_1


class RunicBoundary(ContextDecorator):
    """
    Context manager (and decorator) for crossing the Python/Runic boundary.

    Usage as a context manager:
        with RunicBoundary() as boundary:
            result = boundary.cross(value, operation=my_runic_op)

    Usage as a decorator:
        @RunicBoundary()
        def my_function(x):
            ...
    """

    def __init__(self, eidouron: Optional[RunicEidouron] = None, want_qrcf_out: bool = False):
        self.eidouron = eidouron or RunicEidouron()
        self.timing = TimingTable()
        self.want_qrcf_out = want_qrcf_out
        self._open = False

    def __enter__(self):
        self._open = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._open = False
        return False  # never swallow exceptions

    def cross(self, value: Any, operation: Optional[Callable] = None) -> BoundaryResult:
        """
        Run one full ingress -> process -> egress pass over `value`.

        `operation` is a Callable[[Rune], Rune] applied inside the Runic
        Circle. If omitted, the value passes through untransformed (pure
        translation round-trip).
        """
        if not self._open:
            raise RuntimeError("RunicBoundary.cross() called outside an open boundary")

        io_mode = _detect_io_mode(value, self.want_qrcf_out)

        # Ingress: Python -> Rune atoms
        ingress_rune = RuneTranslator.to_rune(value)
        self.timing.fire('@ingress_ready', ingress_rune)

        # Process: Runic execution
        if operation is None:
            egress_rune = ingress_rune
        else:
            egress_rune = self.eidouron.execute_circle(operation, [ingress_rune])
        self.timing.fire('@process_complete', egress_rune)

        # Egress: Rune atoms -> Python
        result_value = RuneTranslator.from_rune(egress_rune)
        self.timing.fire('@egress_ready', result_value)

        return BoundaryResult(
            value=result_value,
            io_mode=io_mode,
            ingress_rune=ingress_rune,
            egress_rune=egress_rune,
            timing_status=self.timing.status(),
        )

    def __call__(self, fn):
        """Allow use as @RunicBoundary() decorating a plain function."""
        @wraps(fn)
        def wrapper(*args, **kwargs):
            with self:
                result = fn(*args, **kwargs)
                return self.cross(result).value
        return wrapper


def runic_boundary(fn: Callable) -> Callable:
    """Decorator form with default settings: @runic_boundary."""
    return RunicBoundary()(fn)


def cross_boundary(value: Any, operation: Optional[Callable] = None) -> Any:
    """
    Single-call convenience wrapper: opens a boundary, crosses once, closes
    it, and returns the plain Python result value (not the full
    BoundaryResult). For call sites that don't need timing/mode detail.
    """
    with RunicBoundary() as boundary:
        return boundary.cross(value, operation=operation).value


# --- Token helpers (TB / EA / IF) -------------------------------------------
# Runic compression tokens carried across the boundary. Each helper returns
# the block-type metadata a caller needs to tag a value correctly.

def boundary_training_block(name: str, content: Any) -> Rune:
    """TB token: Training Block. Wire block type TREE/FRUIT (0x01), NADA_PROTECTED, symbol xi."""
    return RuneTranslator.to_rune(
        {'name': name, 'content': content},
        symbol='ξ',  # xi
    )


def boundary_enhanced_agent(agent_id: int, state: Dict[str, Any]) -> Rune:
    """EA token: Enhanced Agent. Wire block type FLAME (0x03), EMBER-state aware, symbol alpha."""
    return RuneTranslator.to_rune(
        {'agent_id': agent_id, **state},
        symbol='α',  # alpha
    )


def boundary_integration_failure(fix_id: str, detail: Dict[str, Any]) -> Rune:
    """IF token: Integration Failure. Wire block type VOID (0x0C) resolving to LIGHTNING, symbol ⧧."""
    return RuneTranslator.to_rune(
        {'fix_id': fix_id, **detail},
        symbol='⧧',  # ⧧
    )
