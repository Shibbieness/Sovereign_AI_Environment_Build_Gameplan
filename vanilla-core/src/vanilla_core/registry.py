from __future__ import annotations

import importlib
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .floor import FloorViolation, check_floor
from .manifest import FlavorManifest


class FloorViolationError(Exception):
    def __init__(self, violations: list[FloorViolation]):
        self.violations = violations
        super().__init__("; ".join(f"{v.check}: {v.detail}" for v in violations))


class UnknownCapabilityError(Exception):
    """Asked for a capability the flavor does not declare."""


@contextmanager
def _flavor_on_path(directory: str | None):
    """Put a flavor's own directory on sys.path for the duration of a block.

    Flavors are imported from their own directory, so anything they import by
    bare name resolves only while that directory is on the path. This must
    wrap *calls* as well as the initial import: a flavor that defers heavy
    imports until first use (a common and reasonable pattern) would otherwise
    fail at call time with the directory long since removed.

    The directory is removed again afterwards so two flavors that happen to
    contain same-named modules cannot shadow one another.
    """
    if directory is None or directory in sys.path:
        yield
        return
    sys.path.insert(0, directory)
    try:
        yield
    finally:
        try:
            sys.path.remove(directory)
        except ValueError:  # someone else already cleaned it up
            pass


@dataclass
class LoadedFlavor:
    manifest: FlavorManifest
    run: Callable[..., Any]

    def invoke(self, capability: str | None = None, params: dict | None = None) -> Any:
        """Call the flavor's entrypoint through the standard contract.

        The entrypoint receives `capability` (which of its declared
        capabilities to exercise) and `params` (a plain dict of arguments).
        Keeping the shape this narrow is what lets a flavor be lifted out of
        Vanilla Core and driven by something else — see ARCHITECTURE.md.
        """
        declared = self.manifest.capabilities
        if capability is not None and declared and capability not in declared:
            raise UnknownCapabilityError(
                f"{self.manifest.name} declares {sorted(declared)}, not {capability!r}"
            )
        with _flavor_on_path(str(self.manifest.path) if self.manifest.path else None):
            return self.run(capability=capability, params=params or {})


def discover(root: Path) -> list[Path]:
    """Find every flavor.toml under root, sorted for stable output."""
    return sorted(Path(root).rglob("flavor.toml"))


def load_flavor(manifest_path: Path, *, enforce_floor: bool = True) -> LoadedFlavor:
    manifest = FlavorManifest.load(manifest_path)
    if enforce_floor:
        violations = check_floor(manifest)
        if violations:
            raise FloorViolationError(violations)

    module_name, _, callable_name = manifest.entrypoint.partition(":")
    with _flavor_on_path(str(manifest.path) if manifest.path else None):
        module = importlib.import_module(module_name)

    run = getattr(module, callable_name)
    return LoadedFlavor(manifest=manifest, run=run)
