"""
L4 — Process Registry.

"The system's memory. Stores every ML process ever built, tracks state,
provides retrieval and search, manages lifecycle. Source of truth for what
processes exist and what state they are in." (spec Section 6.1)

Storage: SQLite for process metadata + state + full-text search. Process
content stored as flat files under content/tier-N/, mirroring the tier
hierarchy (spec Section 6.2). Registry does not run processes — it is
memory, not cognition.
"""

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    source_id       TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    conn_type       TEXT NOT NULL,          -- local_path | fuse_mount | removable | ssh | smb_nfs
    label           TEXT NOT NULL,          -- DEFAULT | OPTIONAL
    path            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'connected',  -- connected | disconnected
    fingerprint_json TEXT,
    connected_at    TEXT NOT NULL,
    last_ingest_at  TEXT
);

CREATE TABLE IF NOT EXISTS processes (
    process_id           TEXT PRIMARY KEY,
    slug                 TEXT NOT NULL,
    tier                 TEXT NOT NULL,      -- '4a', '4b', ...
    format_type          TEXT NOT NULL,
    source_id            TEXT NOT NULL,
    source_path          TEXT NOT NULL,
    source_hash          TEXT,
    ingest_timestamp     TEXT,
    build_timestamp      TEXT NOT NULL,
    staleness_state      TEXT NOT NULL DEFAULT 'FRESH',  -- BUILDING|FRESH|STALE|GHOST|CONFLICT|ARCHIVED
    content_path         TEXT NOT NULL,
    composition_parents  TEXT NOT NULL DEFAULT '[]',
    composition_children TEXT NOT NULL DEFAULT '[]',
    tags                 TEXT NOT NULL DEFAULT '[]',
    castle_assignments   TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);

CREATE TABLE IF NOT EXISTS usage_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    process_id  TEXT NOT NULL,
    invoked_at  TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS processes_fts USING fts5(
    process_id UNINDEXED, content, tags, tokenize='porter'
);
"""


@dataclass
class ProcessRecord:
    process_id: str
    slug: str
    tier: str
    format_type: str
    source_id: str
    source_path: str
    source_hash: Optional[str]
    ingest_timestamp: Optional[str]
    build_timestamp: str
    staleness_state: str
    content_path: str
    composition_parents: List[str] = field(default_factory=list)
    composition_children: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    castle_assignments: List[str] = field(default_factory=list)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'ProcessRecord':
        return cls(
            process_id=row['process_id'],
            slug=row['slug'],
            tier=row['tier'],
            format_type=row['format_type'],
            source_id=row['source_id'],
            source_path=row['source_path'],
            source_hash=row['source_hash'],
            ingest_timestamp=row['ingest_timestamp'],
            build_timestamp=row['build_timestamp'],
            staleness_state=row['staleness_state'],
            content_path=row['content_path'],
            composition_parents=json.loads(row['composition_parents']),
            composition_children=json.loads(row['composition_children']),
            tags=json.loads(row['tags']),
            castle_assignments=json.loads(row['castle_assignments']),
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Registry:
    """L4 Process Registry — the sole owner of registry.sqlite3 and content/."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.db_path = data_dir / 'registry.sqlite3'
        self.content_dir = data_dir / 'content'
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self):
        self._conn.close()

    # ---------------------------------------------------------------
    # Sources (L1 registration lands here; L1 itself has no storage)
    # ---------------------------------------------------------------

    def connect_source(self, name: str, path: str, conn_type: str, label: str) -> str:
        source_id = f"src-{uuid.uuid4().hex[:12]}"
        self._conn.execute(
            "INSERT INTO sources (source_id, name, conn_type, label, path, status, connected_at) "
            "VALUES (?, ?, ?, ?, ?, 'connected', ?)",
            (source_id, name, conn_type, label, path, _now()),
        )
        self._conn.commit()
        return source_id

    def set_fingerprint(self, source_id: str, fingerprint: Dict[str, Any]):
        self._conn.execute(
            "UPDATE sources SET fingerprint_json = ? WHERE source_id = ?",
            (json.dumps(fingerprint), source_id),
        )
        self._conn.commit()

    def mark_ingested(self, source_id: str):
        self._conn.execute(
            "UPDATE sources SET last_ingest_at = ? WHERE source_id = ?",
            (_now(), source_id),
        )
        self._conn.commit()

    def disconnect_source(self, source_id: str):
        self._conn.execute("UPDATE sources SET status = 'disconnected' WHERE source_id = ?", (source_id,))
        # FS_DISCONNECTED: all processes from this source flagged (spec Section 3.3).
        self._conn.execute(
            "UPDATE processes SET staleness_state = 'STALE' "
            "WHERE source_id = ? AND staleness_state NOT IN ('GHOST', 'ARCHIVED')",
            (source_id,),
        )
        self._conn.commit()

    def list_sources(self) -> List[sqlite3.Row]:
        return self._conn.execute("SELECT * FROM sources ORDER BY connected_at").fetchall()

    def get_source(self, source_id: str) -> Optional[sqlite3.Row]:
        return self._conn.execute("SELECT * FROM sources WHERE source_id = ?", (source_id,)).fetchone()

    def find_source_by_path(self, path: str) -> Optional[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM sources WHERE path = ? AND status = 'connected'", (path,)
        ).fetchone()

    # ---------------------------------------------------------------
    # Processes (L3 factory output lands here)
    # ---------------------------------------------------------------

    def register_process(
        self,
        slug: str,
        tier: str,
        format_type: str,
        source_id: str,
        source_path: str,
        source_hash: str,
        content_text: str,
        tags: Optional[List[str]] = None,
    ) -> str:
        """Store a process's content as a flat file and register its metadata + FTS entry."""
        process_id = f"proc-{uuid.uuid4().hex[:12]}"
        tier_dir = self.content_dir / f"tier-{tier[0]}"
        tier_dir.mkdir(parents=True, exist_ok=True)
        content_path = tier_dir / f"{process_id}.json"
        content_path.write_text(content_text, encoding='utf-8')

        now = _now()
        tags = tags or []
        self._conn.execute(
            "INSERT INTO processes (process_id, slug, tier, format_type, source_id, source_path, "
            "source_hash, ingest_timestamp, build_timestamp, staleness_state, content_path, tags) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'FRESH', ?, ?)",
            (process_id, slug, tier, format_type, source_id, source_path, source_hash,
             now, now, str(content_path), json.dumps(tags)),
        )
        self._conn.execute(
            "INSERT INTO processes_fts (process_id, content, tags) VALUES (?, ?, ?)",
            (process_id, content_text, ' '.join(tags)),
        )
        self._conn.commit()
        return process_id

    # --- Catalog / View / Search (spec Section 6.4) --------------------

    def catalog(
        self,
        source_id: str = None,
        tier: str = None,
        format_type: str = None,
        staleness: str = None,
        tag: str = None,
    ) -> List[ProcessRecord]:
        query = "SELECT * FROM processes WHERE 1=1"
        params: List[Any] = []
        if source_id:
            query += " AND source_id = ?"
            params.append(source_id)
        if tier:
            query += " AND tier = ?"
            params.append(tier)
        if format_type:
            query += " AND format_type = ?"
            params.append(format_type)
        if staleness:
            query += " AND staleness_state = ?"
            params.append(staleness)
        query += " ORDER BY build_timestamp DESC"
        rows = self._conn.execute(query, params).fetchall()
        records = [ProcessRecord.from_row(r) for r in rows]
        if tag:
            records = [r for r in records if tag in r.tags]
        return records

    def view(self, process_id: str) -> Optional[ProcessRecord]:
        row = self._conn.execute("SELECT * FROM processes WHERE process_id = ?", (process_id,)).fetchone()
        return ProcessRecord.from_row(row) if row else None

    def read_content(self, process_id: str) -> Optional[str]:
        record = self.view(process_id)
        if not record:
            return None
        return Path(record.content_path).read_text(encoding='utf-8')

    def search(self, query: str, limit: int = 20) -> List[ProcessRecord]:
        rows = self._conn.execute(
            "SELECT p.* FROM processes_fts f "
            "JOIN processes p ON p.process_id = f.process_id "
            "WHERE processes_fts MATCH ? ORDER BY rank LIMIT ?",
            (query, limit),
        ).fetchall()
        return [ProcessRecord.from_row(r) for r in rows]

    def record_usage(self, process_id: str):
        self._conn.execute(
            "INSERT INTO usage_history (process_id, invoked_at) VALUES (?, ?)",
            (process_id, _now()),
        )
        self._conn.commit()

    # --- Edit / Rebuild / Delete / Ghost Management ---------------------

    def edit_tags(self, process_id: str, tags: List[str]):
        self._conn.execute(
            "UPDATE processes SET tags = ? WHERE process_id = ?",
            (json.dumps(tags), process_id),
        )
        self._conn.execute("UPDATE processes_fts SET tags = ? WHERE process_id = ?", (' '.join(tags), process_id))
        self._conn.commit()

    def mark_staleness(self, process_id: str, state: str):
        self._conn.execute(
            "UPDATE processes SET staleness_state = ? WHERE process_id = ?", (state, process_id)
        )
        self._conn.commit()

    def mark_ghost(self, process_id: str):
        """All source files deleted or source disconnected. Still usable; sourceless (spec 5.3)."""
        self.mark_staleness(process_id, 'GHOST')

    def list_ghosts(self, source_id: str = None) -> List[ProcessRecord]:
        return self.catalog(source_id=source_id, staleness='GHOST')

    def soft_delete(self, process_id: str):
        self.mark_staleness(process_id, 'ARCHIVED')

    def hard_delete(self, process_id: str, confirm: bool = False):
        if not confirm:
            raise ValueError("hard_delete requires explicit confirm=True")
        record = self.view(process_id)
        if record:
            Path(record.content_path).unlink(missing_ok=True)
        self._conn.execute("DELETE FROM processes WHERE process_id = ?", (process_id,))
        self._conn.execute("DELETE FROM processes_fts WHERE process_id = ?", (process_id,))
        self._conn.commit()

    def check_staleness(self, process_id: str, current_source_hash: str) -> bool:
        """Returns True if the process is now STALE (source hash changed since build)."""
        record = self.view(process_id)
        if not record or record.staleness_state in ('GHOST', 'ARCHIVED'):
            return False
        if record.source_hash != current_source_hash:
            self.mark_staleness(process_id, 'STALE')
            return True
        return False
