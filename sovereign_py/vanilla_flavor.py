"""ML Filesystem as a Vanilla Core flavor.

An adapter, not a rewrite. The filesystem engine, database models, and ML
runtime underneath are untouched; this maps the Vanilla Core contract
(``run(capability, params)``) onto their existing managers and returns
JSON-serializable results.

Two things differ from the QRen Coder flavor, and both are deliberate:

  * **This flavor has real dependencies.** Flask, SQLAlchemy, numpy and
    friends. Vanilla Core stays stdlib-only; a *flavor* may need whatever it
    needs. ``status`` reports which optional subsystems resolved, so a host
    can see what is actually available rather than discovering it on first
    call.
  * **Importing this module has a side effect.** ``core.module_path_bridge``
    installs ``sys.modules`` aliases at import time so the legacy flat module
    names (``models``, ``ml.*``, ``filesystem.*``) resolve. That is the
    project's existing design, not something introduced here — it is
    documented rather than worked around, because working around it would
    mean editing the modules the port is supposed to leave alone.

Nothing here imports ``vanilla_core``. ML Filesystem stays independently
usable and Vanilla Core is one possible caller, not a dependency.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

CAPABILITIES = (
    "status",
    "self-test",
    "stores",
    "fs-write",
    "fs-read",
    "fs-list",
    "fs-search",
    "chains",
    "training-blocks",
)

# Previously blocked by two divergent File models. Resolved by routing them
# to separate stores instead of merging them — see core/master_db.py.
KNOWN_GAPS: dict[str, str] = {}

_OPTIONAL = (
    "chromadb",
    "sentence_transformers",
    "sklearn",
    "anthropic",
    "docker",
    "magic",
)


class FlavorError(Exception):
    """Bad input to this adapter, kept distinct from the project's errors."""


def _require(params: dict, key: str):
    if key not in params:
        raise FlavorError(f"capability requires --param {key}=<value>")
    return params[key]


# ── lazy bootstrap ────────────────────────────────────────────────────
# Deferred so that importing this module stays cheap and `status` can
# report on a broken environment instead of failing to import at all.

_STATE: dict = {}


def _boot(data_dir: str | None = None, sandbox: str | None = None) -> dict:
    """Initialize the bridge, database, and managers exactly once per path."""
    key = (data_dir or "", sandbox or "")
    if _STATE.get("key") == key and _STATE.get("ready"):
        return _STATE

    if data_dir:
        # Config reads DATABASE_URL from the environment at import time, so
        # this must be set before core.config is first imported.
        os.environ["DATABASE_URL"] = f"sqlite:///{Path(data_dir).resolve()}/database.db"
        Path(data_dir).mkdir(parents=True, exist_ok=True)

    import core.module_path_bridge as bridge  # noqa: F401  (installs aliases)
    from core.master_db import MasterDB
    from fs_engine.filesystem import FileSystemManager
    from fs_engine.filechain import FileChainManager
    from ml_runtime.training_blocks import TrainingBlockManager

    master = MasterDB(data_dir or (_HERE / "data"))
    master.init_all()
    # `db` here is the enhanced-store singleton, repointed by MasterDB.
    db = master.enhanced

    sandbox_root = sandbox or str(_HERE / "sandbox")
    Path(sandbox_root).mkdir(parents=True, exist_ok=True)

    _STATE.update(
        key=key,
        ready=True,
        bridge=bridge,
        db=db,
        master=master,
        # The filesystem engine needs File.is_directory / File.parent_id, so
        # it is bound to the hierarchy store, not the enhanced one.
        fs=FileSystemManager(sandbox_root=sandbox_root, db=master.hierarchy),
        chains=FileChainManager(),
        blocks=TrainingBlockManager(),
        sandbox_root=sandbox_root,
    )
    return _STATE


def _default_user_id(state: dict, store: str = "hierarchy") -> int:
    """A usable owner id in the named store, created if the store is empty."""
    return state["master"].ensure_user(store)


def _ensure_root(state: dict, user_id: int) -> int:
    """Guarantee a `/` directory record exists in the hierarchy store.

    fs_engine/filesystem.py assumes a root directory row is already present —
    list_directory('/') raises NotADirectoryError without one — but nothing
    in the project ever creates it. Seeded directly rather than through
    create_directory(), which would try to look up '/' as its own parent.
    """
    import core.models_v1 as models_v1

    session = state["master"].hierarchy.Session()
    try:
        root = session.query(models_v1.File).filter_by(path="/").first()
        if root is None:
            root = models_v1.File(
                name="/", path="/", is_directory=True,
                file_type="directory", owner_id=user_id, size=0,
            )
            session.add(root)
            session.commit()
        return root.id
    finally:
        session.close()


def _file_row(state: dict, path: str) -> dict:
    """Read a file record into a plain dict inside a session we control.

    The managers return ORM instances bound to sessions they have already
    closed, so touching any attribute afterwards raises DetachedInstanceError.
    """
    import core.models_v1 as models_v1

    session = state["master"].hierarchy.Session()
    try:
        row = session.query(models_v1.File).filter_by(path=path).first()
        if row is None:
            return {}
        return {
            "file_id": row.id,
            "name": row.name,
            "size": row.size,
            "file_type": row.file_type,
            "is_directory": bool(row.is_directory),
            "parent_id": row.parent_id,
        }
    finally:
        session.close()


# ── capabilities ──────────────────────────────────────────────────────


def _status(params: dict) -> dict:
    """Environment health: aliases, optional subsystems, database shape.

    Reports rather than raises, so this stays useful on a broken install —
    which is when it matters most.
    """
    report: dict = {"ok": True, "optional_subsystems": {}, "errors": []}

    for name in _OPTIONAL:
        try:
            __import__(name)
            report["optional_subsystems"][name] = "available"
        except Exception:
            report["optional_subsystems"][name] = "missing"

    try:
        state = _boot(params.get("data_dir"), params.get("sandbox"))
        aliases = state["bridge"].installed_aliases()
        unresolved = [legacy for legacy, _ in aliases if legacy not in sys.modules]
        report["bridge_aliases"] = len(aliases)
        report["bridge_unresolved"] = unresolved
        if unresolved:
            report["ok"] = False
            report["errors"].append(f"unresolved aliases: {unresolved}")

        stores = state["master"].report()
        report["stores"] = stores
        report["table_count"] = sum(s.get("table_count", 0) for s in stores.values())
        for name, info in stores.items():
            if not info.get("exists"):
                report["ok"] = False
                report["errors"].append(f"store {name} was not created")
    except Exception as exc:  # noqa: BLE001 - status must never raise
        report["ok"] = False
        report["errors"].append(f"{type(exc).__name__}: {exc}")

    return report


def _stores(params: dict) -> dict:
    """Report the Master DB routing: which store holds what."""
    state = _boot(params.get("data_dir"), params.get("sandbox"))
    return {
        "ok": True,
        "routing": {
            "hierarchy": "core/models_v1.py — sandboxed filesystem tree "
                         "(File.is_directory, File.parent_id)",
            "enhanced": "core/database.py + core/enhanced_models.py — chains, "
                        "training blocks, agents, embeddings, VM/IDE/API",
        },
        "stores": state["master"].report(),
    }


def _fs_write(params: dict) -> dict:
    state = _boot(params.get("data_dir"), params.get("sandbox"))
    path = str(_require(params, "path"))
    content = str(_require(params, "content"))
    user_id = int(params.get("user_id") or _default_user_id(state))
    _ensure_root(state, user_id)
    state["fs"].create_file(path, content, user_id)
    return {"ok": True, "path": path, "user_id": user_id, **_file_row(state, path)}


def _fs_read(params: dict) -> dict:
    state = _boot(params.get("data_dir"), params.get("sandbox"))
    path = str(_require(params, "path"))
    user_id = int(params.get("user_id") or _default_user_id(state))
    return {"ok": True, "path": path, "content": state["fs"].read_file(path, user_id)}


def _fs_list(params: dict) -> dict:
    state = _boot(params.get("data_dir"), params.get("sandbox"))
    path = str(params.get("path", "/"))
    user_id = int(params.get("user_id") or _default_user_id(state))
    _ensure_root(state, user_id)

    import core.models_v1 as models_v1

    session = state["master"].hierarchy.Session()
    try:
        parent = (
            session.query(models_v1.File)
            .filter_by(path=path, is_directory=True)
            .first()
        )
        if parent is None:
            raise FlavorError(f"not a directory: {path}")
        rows = session.query(models_v1.File).filter_by(parent_id=parent.id).all()
        entries = [
            {
                "name": r.name, "path": r.path, "size": r.size,
                "is_directory": bool(r.is_directory), "file_type": r.file_type,
            }
            for r in rows
        ]
    finally:
        session.close()
    return {"ok": True, "path": path, "count": len(entries), "entries": entries}


def _fs_search(params: dict) -> dict:
    """Search file names and content in the hierarchy store.

    Mirrors FileSystemManager.search_files' filter (owner, then name-or-content
    contains) but runs in a session this function owns, because the manager
    returns ORM instances bound to a session it has already closed — reading
    any un-loaded attribute afterwards raises DetachedInstanceError.
    """
    state = _boot(params.get("data_dir"), params.get("sandbox"))
    query = str(_require(params, "query"))
    user_id = int(params.get("user_id") or _default_user_id(state))
    file_type = params.get("file_type")

    import core.models_v1 as models_v1

    File = models_v1.File
    session = state["master"].hierarchy.Session()
    try:
        db_query = session.query(File).filter_by(owner_id=user_id)
        if query:
            db_query = db_query.filter(
                File.name.contains(query) | File.content.contains(query)
            )
        if file_type:
            db_query = db_query.filter_by(file_type=file_type)
        results = [
            {
                "name": r.name, "path": r.path, "size": r.size,
                "file_type": r.file_type, "is_directory": bool(r.is_directory),
            }
            for r in db_query.order_by(File.path).all()
        ]
    finally:
        session.close()
    return {"ok": True, "query": query, "count": len(results), "results": results}


def _chains(params: dict) -> dict:
    state = _boot(params.get("data_dir"), params.get("sandbox"))
    owner = params.get("owner_id")
    listed = state["chains"].list_chains(int(owner) if owner is not None else None)
    return {"ok": True, "count": len(listed), "chains": listed}


def _training_blocks(params: dict) -> dict:
    """List training blocks.

    Queries directly rather than going through TrainingBlockManager.list_blocks:
    that returns ORM instances bound to a session it has already closed, so
    touching any attribute afterwards raises DetachedInstanceError. Reading
    the fields inside a session we control avoids depending on the manager's
    session lifetime.
    """
    from core.database import TrainingBlock

    state = _boot(params.get("data_dir"), params.get("sandbox"))
    owner = params.get("owner_id")

    session = state["master"].enhanced.Session()
    try:
        query = session.query(TrainingBlock)
        if owner is not None:
            query = query.filter_by(owner_id=int(owner))
        if params.get("enabled_only"):
            query = query.filter_by(enabled=True)
        blocks = [
            {
                "id": b.id,
                "name": b.name,
                "description": getattr(b, "description", None),
                "enabled": getattr(b, "enabled", None),
                "owner_id": getattr(b, "owner_id", None),
            }
            for b in query.order_by(TrainingBlock.id).all()
        ]
    finally:
        session.close()

    return {"ok": True, "count": len(blocks), "blocks": blocks}


def _self_test(params: dict) -> dict:
    """Boot into a throwaway data dir and exercise the filesystem end to end.

    Uses its own temporary database and sandbox so it never touches a real
    install, which means a host can run it to check the environment without
    risking existing data.
    """
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = str(Path(tmp) / "data")
        sandbox = str(Path(tmp) / "sandbox")
        steps: list[dict] = []

        status = _status({"data_dir": data_dir, "sandbox": sandbox})
        steps.append({"step": "status", "ok": status["ok"], "tables": status.get("table_count")})

        state = _boot(data_dir, sandbox)
        user_id = _default_user_id(state)
        steps.append({"step": "seed-user", "ok": True, "user_id": user_id})

        body = "vanilla core round trip\nsecond line\n"
        common = {"user_id": user_id, "data_dir": data_dir, "sandbox": sandbox}
        written = _fs_write({"path": "/selftest.txt", "content": body, **common})
        steps.append({"step": "fs-write", "ok": written["ok"], "file_id": written.get("file_id")})

        read = _fs_read({"path": "/selftest.txt", **common})
        steps.append({"step": "fs-read", "ok": read["content"] == body})

        listing = _fs_list({"path": "/", **common})
        steps.append({"step": "fs-list", "ok": listing["count"] >= 1, "count": listing["count"]})

        search = _fs_search({"query": "round trip", **common})
        steps.append({"step": "fs-search", "ok": search["count"] >= 1, "count": search["count"]})

        chains = _chains({"data_dir": data_dir, "sandbox": sandbox})
        steps.append({"step": "chains", "ok": chains["ok"], "count": chains["count"]})

        blocks = _training_blocks({"data_dir": data_dir, "sandbox": sandbox})
        steps.append(
            {"step": "training-blocks", "ok": blocks["count"] > 0, "count": blocks["count"]}
        )

        return {
            "ok": all(s["ok"] for s in steps),
            "table_count": status.get("table_count"),
            "bridge_aliases": status.get("bridge_aliases"),
            "known_gaps": sorted(KNOWN_GAPS),
            "stores": {k: v.get("table_count") for k, v in status.get("stores", {}).items()},
            "steps": steps,
        }


_DISPATCH = {
    "status": _status,
    "self-test": _self_test,
    "stores": _stores,
    "fs-write": _fs_write,
    "fs-read": _fs_read,
    "fs-list": _fs_list,
    "fs-search": _fs_search,
    "chains": _chains,
    "training-blocks": _training_blocks,
}


def run(capability: str | None = None, params: dict | None = None) -> dict:
    """Vanilla Core entrypoint. See CAPABILITIES for what `capability` accepts."""
    params = params or {}
    capability = capability or "status"
    handler = _DISPATCH.get(capability)
    if handler is None:
        raise FlavorError(
            f"unknown capability {capability!r}; expected one of {list(_DISPATCH)}"
        )
    return handler(params)
