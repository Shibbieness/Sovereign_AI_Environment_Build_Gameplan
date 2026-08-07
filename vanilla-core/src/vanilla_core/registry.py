from __future__ import annotations

import importlib
import sys
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
    flavor_dir = str(manifest.path)
    added = flavor_dir not in sys.path
    if added:
        sys.path.insert(0, flavor_dir)
    try:
        module = importlib.import_module(module_name)
    finally:
        if added:
            sys.path.remove(flavor_dir)

    run = getattr(module, callable_name)
    return LoadedFlavor(manifest=manifest, run=run)
