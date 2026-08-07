"""Master DB — routes to the right store by purpose.

ML Filesystem carries two SQLAlchemy declarative registries that were never
reconciled, and reconciling them is the wrong move: they model different
things and six of their table names collide (``users``, ``files``,
``ml_agents``, ``tags``, ``file_embeddings``, ``activity_logs``) with
different columns on each side. Pointing both at one SQLite file makes
whichever ``create_all`` runs second either silently lose columns or fail.

So they get separate stores, and this module is the layer that knows which
is which:

  ``hierarchy``  core/models_v1.py  — the sandboxed hierarchical filesystem.
                 Its ``File`` has ``is_directory``, ``parent_id`` and
                 ``storage_path``, which is what ``fs_engine/filesystem.py``
                 actually queries: directories, parents, tree walking.

  ``enhanced``   core/database.py + core/enhanced_models.py — the v1.8
                 system: file chains, training blocks, ML agents, embeddings,
                 VM/IDE/API integration. Its ``File`` is flat but carries
                 ``embedding_generated`` and ``in_training_blocks``.

Neither is "canonical". They are different stores for different jobs, which
is the whole point of routing rather than merging.

## Known limitation

The two stores each have a ``files`` table and they are not synchronized. A
FileChain in the enhanced store referencing file id 7 does not necessarily
mean file id 7 in the hierarchy store. Nothing today crosses that boundary —
``fs_engine/filesystem.py`` stays entirely in ``hierarchy`` and
``fs_engine/filechain.py`` stays entirely in ``enhanced`` — but any future
feature that joins a chain to a file on disk has to reconcile identity
across stores explicitly. That is a real design task, deliberately not
pre-solved here; see AI-OS.md.
"""

from __future__ import annotations

from pathlib import Path

STORES = ("hierarchy", "enhanced")


class MasterDB:
    """Owns one engine per store and hands out the right one."""

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._hierarchy = None
        self._enhanced = None

    # ── store URLs ────────────────────────────────────────────────────

    def url(self, store: str) -> str:
        if store not in STORES:
            raise ValueError(f"unknown store {store!r}; expected one of {STORES}")
        return f"sqlite:///{self.data_dir / (store + '.db')}"

    # ── stores ────────────────────────────────────────────────────────

    @property
    def hierarchy(self):
        """models_v1 store: hierarchical filesystem with directories."""
        if self._hierarchy is None:
            import core.models_v1 as models_v1

            db = models_v1.Database(self.url("hierarchy"))
            db.create_all()
            self._hierarchy = db
        return self._hierarchy

    @property
    def enhanced(self):
        """core.database store: chains, training blocks, agents, integrations.

        Deliberately repoints the existing ``core.database.db`` singleton
        rather than constructing a second Database. FileChainManager,
        TrainingBlockManager, operations, and the server modules all import
        that singleton directly, so handing back a different instance would
        leave them talking to a database this layer does not manage — two
        connections, one of them stale.
        """
        if self._enhanced is None:
            from core.database import db

            wanted = self.url("enhanced")
            if db.database_url != wanted:
                db.database_url = wanted
                db.engine = None
            if db.engine is None:
                db.init_db()
            self._enhanced = db
        return self._enhanced

    def init_all(self) -> dict:
        """Materialize both stores. Returns a per-store table report."""
        self.hierarchy  # noqa: B018 - property call creates tables
        self.enhanced   # noqa: B018
        return self.report()

    # ── seeding ───────────────────────────────────────────────────────

    def ensure_user(self, store: str = "hierarchy") -> int:
        """Return a usable owner id for `store`, creating one if absent.

        The enhanced store seeds a default admin during init_db(); the
        hierarchy store only runs create_all() and starts empty, so file
        operations there would fail on a null owner. Both are handled here so
        callers do not need to know which store self-seeds.
        """
        if store == "enhanced":
            from core.database import User

            session = self.enhanced.Session()
        else:
            import core.models_v1 as models_v1

            User = models_v1.User
            session = self.hierarchy.Session()

        try:
            existing = session.query(User).order_by(User.id).first()
            if existing is not None:
                return existing.id
            user = User(
                username="admin",
                email="admin@localhost",
                password_hash="!",  # unusable placeholder, not a real login
            )
            session.add(user)
            session.commit()
            return user.id
        finally:
            session.close()

    # ── introspection ─────────────────────────────────────────────────

    def report(self) -> dict:
        """Table names actually present in each store, read from SQLite."""
        import sqlite3

        out: dict = {}
        for store in STORES:
            path = self.data_dir / f"{store}.db"
            if not path.exists():
                out[store] = {"path": str(path), "exists": False, "tables": []}
                continue
            conn = sqlite3.connect(path)
            try:
                tables = [
                    r[0]
                    for r in conn.execute(
                        "select name from sqlite_master where type='table' "
                        "and name not like 'sqlite_%' order by name"
                    )
                ]
            finally:
                conn.close()
            out[store] = {
                "path": str(path),
                "exists": True,
                "table_count": len(tables),
                "tables": tables,
            }
        return out
