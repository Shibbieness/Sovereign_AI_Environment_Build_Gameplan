"""
VI Builder configuration — data directory resolution.

Addresses OQ-06 (Registry Storage Location): non-blocking for the Phase 1
CLI, but "must be configurable." Resolution order, highest priority first:

  1. VI_BUILDER_DATA_DIR environment variable
  2. --data-dir CLI flag (passed through by cli.py)
  3. Default: ~/.local/share/vi-builder/  (the spec's own recommendation)
"""

import os
from pathlib import Path

DEFAULT_DATA_DIR = Path.home() / '.local' / 'share' / 'vi-builder'

# Debounce window for L1 watch events, per spec Section 3.3 ("configurable,
# default 2 seconds").
DEFAULT_DEBOUNCE_SECONDS = 2.0


def resolve_data_dir(override: str = None) -> Path:
    """Resolve the VI Builder data directory per the priority order above."""
    if override:
        data_dir = Path(override).expanduser()
    else:
        env_override = os.environ.get('VI_BUILDER_DATA_DIR')
        data_dir = Path(env_override).expanduser() if env_override else DEFAULT_DATA_DIR

    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / 'content').mkdir(exist_ok=True)
    for tier in ('tier-0', 'tier-1', 'tier-2', 'tier-3', 'tier-4', 'tier-5'):
        (data_dir / 'content' / tier).mkdir(exist_ok=True)
    return data_dir


def db_path(data_dir: Path) -> Path:
    return data_dir / 'registry.sqlite3'
