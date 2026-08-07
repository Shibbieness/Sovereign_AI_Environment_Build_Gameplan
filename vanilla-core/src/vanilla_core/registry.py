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


@dataclass
class LoadedFlavor:
    manifest: FlavorManifest
    run: Callable[..., Any]


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
