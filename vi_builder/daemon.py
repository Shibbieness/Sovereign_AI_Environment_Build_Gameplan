"""
L1 — Filesystem Daemon.

"The system's sensory surface. It manages source connections, watches for
changes, and feeds artifact events to the Ingestion Layer. The only layer
that directly touches the host filesystem." (spec Section 3.1)

Stdlib-only by design (mirrors the "zero external dependency" property the
spec assigns to local-path connections): watching is done by polling +
snapshot diffing rather than binding to a native inotify/watchdog library.
L1 does not extract content (L2), classify tiers (L2), or manage processes
(L3/L4) — it only produces ArtifactEvent records.
"""

import hashlib
import os
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Callable, Dict, List, Optional

# Connection types (spec Section 3.2). DEFAULT = always available, never
# needs opt-in. OPTIONAL = never connected automatically, must be explicit.
DEFAULT_CONN_TYPES = {'local_path', 'fuse_mount', 'removable'}
OPTIONAL_CONN_TYPES = {'ssh', 'smb_nfs'}
ALL_CONN_TYPES = DEFAULT_CONN_TYPES | OPTIONAL_CONN_TYPES

# Directories/patterns never watched or ingested regardless of source.
IGNORE_DIR_NAMES = {'__pycache__', '.git', 'node_modules', '.venv', 'venv', 'chroma_db', 'sandbox', 'data'}
IGNORE_SUFFIXES = {'.pyc', '.pyo'}

FINGERPRINT_SAMPLE_SIZE = 20  # "first N files" for sample content hash


@dataclass
class ArtifactEvent:
    event_type: str    # FILE_CREATED | FILE_MODIFIED | FILE_DELETED | FILE_MOVED | FS_CONNECTED | FS_DISCONNECTED
    source_id: str
    path: str
    from_path: Optional[str] = None   # populated for FILE_MOVED
    timestamp: float = 0.0


def label_for_conn_type(conn_type: str) -> str:
    if conn_type not in ALL_CONN_TYPES:
        raise ValueError(f"Unknown connection type: {conn_type!r}. Valid: {sorted(ALL_CONN_TYPES)}")
    return 'DEFAULT' if conn_type in DEFAULT_CONN_TYPES else 'OPTIONAL'


def _should_ignore(path: Path) -> bool:
    if any(part in IGNORE_DIR_NAMES for part in path.parts):
        return True
    if path.suffix in IGNORE_SUFFIXES:
        return True
    return False


def walk_source(root: Path) -> List[Path]:
    """All non-ignored files under root, relative-sorted for determinism."""
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIR_NAMES]
        for name in filenames:
            p = Path(dirpath) / name
            if not _should_ignore(p):
                files.append(p)
    return sorted(files)


def file_hash(path: Path, chunk_size: int = 65536) -> str:
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
    except (OSError, PermissionError):
        return ''
    return h.hexdigest()


def compute_fingerprint(root: Path, sample_size: int = FINGERPRINT_SAMPLE_SIZE) -> Dict:
    """
    Signature profile of a source (spec Section 3.4): total file count,
    directory structure hash, file extension distribution, median file
    size, sample content hash from first N files.
    """
    files = walk_source(root)
    extensions: Dict[str, int] = {}
    sizes = []
    for f in files:
        ext = f.suffix or '(none)'
        extensions[ext] = extensions.get(ext, 0) + 1
        try:
            sizes.append(f.stat().st_size)
        except OSError:
            pass

    dir_structure = '\n'.join(str(f.relative_to(root)) for f in files)
    dir_structure_hash = hashlib.sha256(dir_structure.encode('utf-8')).hexdigest()

    sample_hasher = hashlib.sha256()
    for f in files[:sample_size]:
        sample_hasher.update(file_hash(f).encode('utf-8'))

    return {
        'file_count': len(files),
        'directory_structure_hash': dir_structure_hash,
        'extension_distribution': extensions,
        'median_file_size': median(sizes) if sizes else 0,
        'sample_content_hash': sample_hasher.hexdigest(),
    }


def compare_fingerprints(old: Dict, new: Dict) -> str:
    """
    'match' -> recognized source, delta ingest only.
    'diverge' -> significant divergence; caller decides same/new/fork.
    """
    if old.get('directory_structure_hash') == new.get('directory_structure_hash'):
        return 'match'
    # Partial overlap heuristic: same sample hash but different structure
    # still counts as a real divergence per spec — structure hash is the
    # primary signal.
    return 'diverge'


class FilesystemSource:
    """A connected source: what L1 watches, and the snapshot it diffs against."""

    def __init__(self, source_id: str, root: Path):
        self.source_id = source_id
        self.root = root
        self._snapshot: Dict[str, str] = {}  # relative path -> content hash

    def snapshot(self) -> Dict[str, str]:
        """Full-hash snapshot of every file under root."""
        result = {}
        for f in walk_source(self.root):
            rel = str(f.relative_to(self.root))
            result[rel] = file_hash(f)
        return result

    def diff_since_last_scan(self) -> List[ArtifactEvent]:
        """
        One-shot scan producing CREATE/MODIFY/DELETE events relative to the
        last recorded snapshot. Used both for the initial FS_CONNECTED
        ingest and for subsequent re-scans.
        """
        current = self.snapshot()
        events: List[ArtifactEvent] = []
        now = time.time()

        for rel, content_hash in current.items():
            if rel not in self._snapshot:
                events.append(ArtifactEvent('FILE_CREATED', self.source_id, rel, timestamp=now))
            elif self._snapshot[rel] != content_hash:
                events.append(ArtifactEvent('FILE_MODIFIED', self.source_id, rel, timestamp=now))

        for rel in self._snapshot:
            if rel not in current:
                events.append(ArtifactEvent('FILE_DELETED', self.source_id, rel, timestamp=now))

        self._snapshot = current
        return events


class Watcher:
    """
    Debounced polling watcher (spec Section 3.3). Optional continuous
    operation on top of FilesystemSource's one-shot diffing — Phase 1's CLI
    gate only requires connect+ingest+query, so this is exercised via the
    `vi-builder watch` command rather than being load-bearing for `ingest`.
    """

    def __init__(self, source: FilesystemSource, debounce_seconds: float = 2.0):
        self.source = source
        self.debounce_seconds = debounce_seconds

    def run(self, on_events: Callable[[List[ArtifactEvent]], None], poll_interval: float = 1.0, max_iterations: int = None):
        """Blocking loop. max_iterations is for tests; None = run forever."""
        iterations = 0
        pending: List[ArtifactEvent] = []
        last_change = None

        while max_iterations is None or iterations < max_iterations:
            events = self.source.diff_since_last_scan()
            if events:
                pending.extend(events)
                last_change = time.time()

            if pending and last_change and (time.time() - last_change) >= self.debounce_seconds:
                on_events(pending)
                pending = []
                last_change = None

            iterations += 1
            if max_iterations is None or iterations < max_iterations:
                time.sleep(poll_interval)

        if pending:
            on_events(pending)
