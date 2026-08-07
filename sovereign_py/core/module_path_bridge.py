"""
Module path bridge for ML Filesystem v1.8+.

The source tree was reorganized (ml -> ml_runtime, api -> server,
coding/vm -> features, filesystem -> fs_engine) but the code itself still
imports under the old names (`from ml.local_backend import ...`,
`from api.api_manager import ...`, etc). Rather than rewrite every import
statement across the codebase, this installs sys.modules aliases so the old
names resolve to the real packages.

This is a sys.modules alias layer, NOT a Runic construct — it borrows the
"translate at the boundary, not throughout" philosophy from the Runic
boundary (runic/runic_translation.py) but operates on Python module
namespaces, not on data crossing an execution boundary.

Import order matters: several real modules import their own sibling
submodules under the OLD names internally (e.g. ml_runtime/local_backend.py
does `from ml.model_manager import MLModelManager`), so leaf modules must be
aliased before the modules that depend on them, or the dependent import
fails at alias-install time. install() below encodes that dependency order
directly rather than trying to infer it generically.

Call install() once, before any other project import — entry/app_v18.py
does this as its very first import.
"""

import sys
import importlib

# (legacy_name, real_name) pairs, in safe install order.
# Bare (no-dot) package aliases go first: they let any submodule of the
# real package resolve automatically through the package's own __path__,
# for names not explicitly listed below.
_ALIASES = [
    # --- bare top-level package aliases ---
    ("filesystem", "fs_engine"),
    ("ml", "ml_runtime"),
    ("api", "server"),
    ("coding", "features"),

    # --- ml.* submodules, in dependency order (each only depends on ones above it) ---
    ("ml.model_manager", "ml_runtime.model_manager"),
    ("ml.local_backend", "ml_runtime.local_backend"),
    ("ml.training_blocks", "ml_runtime.training_blocks"),
    ("ml.enhanced_agents", "ml_runtime.enhanced_agents"),
    # Real file is a GHOST_BONE-suffixed deprecated-but-preserved ancestor.
    ("ml.hybrid_agent", "ml_runtime.hybrid_agent_GHOST_BONE"),
    ("ml.enhancements", "enhancements.enhancements"),

    # --- api.* / coding.* / vm.* submodules ---
    ("api.api_manager", "server.api_manager"),
    ("coding.ide_manager", "features.ide_manager"),
    ("vm.vm_manager", "features.vm_manager"),
    # enhanced_routes imports from api.api_manager / coding.ide_manager / vm.vm_manager,
    # so it must be aliased after those three.
    ("api.enhanced_routes", "server.enhanced_routes"),
    ("api.internal_api", "server.internal_api"),

    # --- filesystem.* submodules (depend on ml.local_backend) ---
    ("filesystem.operations", "fs_engine.operations"),
    ("filesystem.filechain", "fs_engine.filechain"),

    # --- legacy flat "models" module ---
    ("models", "core.database"),

    # --- legacy flat "extended" modules ---
    # part2_agent_system does `import part1_foundation` with no package
    # prefix, so the bare name has to resolve or part2 fails to import.
    ("part1_foundation", "extended.part1_foundation"),
    ("part2_agent_system", "extended.part2_agent_system"),
]


def install():
    """Install all aliases in dependency order. Idempotent."""
    for legacy, real in _ALIASES:
        if legacy in sys.modules:
            continue
        module = importlib.import_module(real)
        sys.modules[legacy] = module


def installed_aliases():
    """Return the list of (legacy, real) pairs this bridge knows about."""
    return list(_ALIASES)


install()
