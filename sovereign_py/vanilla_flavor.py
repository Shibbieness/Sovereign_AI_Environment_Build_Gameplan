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
    "fs-search",
    "chains",
    "training-blocks",
)

# Implemented, but blocked upstream. Kept dispatchable so they raise an
# explanation rather than an opaque SQLAlchemy error, and deliberately NOT
# declared in flavor.toml — a manifest should not promise what cannot run.
KNOWN_GAPS = {
    "fs-write": "File model split",
    "fs-read": "File model split (untestable without fs-write)",
    "fs-list": "File model split",
}

_GAP_EXPLANATION = """\
Blocked by an upstream defect, not by this adapter.

fs_engine/filesystem.py queries File.is_directory and File.parent_id, but
the `models` bridge alias points at core.database, whose File model defines
neither. core/models_v1.py does define them — the two model generations have
diverged, and they register on separate declarative Bases, so they cannot be
merged by changing the alias alone.

Resolving this is a design decision about which model generation is
canonical, and it changes the database schema. That is an owner's call, not
something an adapter should paper over."""

# Subsystems whose absence degrades the system rather than breaking it. The
# status capability reports these instead of letting a caller find out by
# hitting an ImportError mid-operation.
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
    from core.database import db
    from fs_engine.filesystem import FileSystemManager
    from fs_engine.filechain import FileChainManager
    from ml_runtime.training_blocks import TrainingBlockManager

    # `db` is a module-level singleton that captured Config.DATABASE_URL when
    # core.database was first imported. Setting the environment variable above
    # therefore only takes effect on the very first boot of a process — every
    # later boot would silently keep using the original path. Point the
    # singleton at the requested database explicitly and re-initialize when it
    # changes, so repeated boots (tests, or a host serving several data dirs)
    # actually land where they were told to.
    if data_dir:
        wanted = f"sqlite:///{Path(data_dir).resolve()}/database.db"
        if db.database_url != wanted:
            db.database_url = wanted
            db.engine = None

    if db.engine is None:
        db.init_db()

    sandbox_root = sandbox or str(_HERE / "sandbox")
    Path(sandbox_root).mkdir(parents=True, exist_ok=True)

    _STATE.update(
        key=key,
        ready=True,
        bridge=bridge,
        db=db,
        fs=FileSystemManager(sandbox_root=sandbox_root, db=db),
        chains=FileChainManager(),
        blocks=TrainingBlockManager(),
        sandbox_root=sandbox_root,
    )
    return _STATE


def _default_user_id(state: dict) -> int:
    """The seeded admin user, unless a caller names another."""
    from core.database import User

    session = state["db"].Session()
    try:
        user = session.query(User).order_by(User.id).first()
        if user is None:
            raise FlavorError("no users in database; run entry/rebuild_db.py first")
        return user.id
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

        import sqlite3

        url = state["db"].database_url
        if url.startswith("sqlite:///"):
            path = url.replace("sqlite:///", "", 1)
            conn = sqlite3.connect(path)
            try:
                tables = [
                    r[0]
                    for r in conn.execute(
                        "select name from sqlite_master where type='table' order by name"
                    )
                ]
            finally:
                conn.close()
            report["database_path"] = path
            report["table_count"] = len(tables)
            report["tables"] = tables
    except Exception as exc:  # noqa: BLE001 - status must never raise
        report["ok"] = False
        report["errors"].append(f"{type(exc).__name__}: {exc}")

    return report


def _fs_write(params: dict) -> dict:
    state = _boot(params.get("data_dir"), params.get("sandbox"))
    path = str(_require(params, "path"))
    content = str(_require(params, "content"))
    user_id = int(params.get("user_id") or _default_user_id(state))
    record = state["fs"].create_file(path, content, user_id)
    return {
        "ok": True,
        "path": path,
        "file_id": getattr(record, "id", None),
        "size": getattr(record, "size", len(content)),
        "user_id": user_id,
    }


def _fs_read(params: dict) -> dict:
    state = _boot(params.get("data_dir"), params.get("sandbox"))
    path = str(_require(params, "path"))
    user_id = int(params.get("user_id") or _default_user_id(state))
    return {"ok": True, "path": path, "content": state["fs"].read_file(path, user_id)}


def _fs_list(params: dict) -> dict:
    state = _boot(params.get("data_dir"), params.get("sandbox"))
    path = str(params.get("path", "/"))
    user_id = int(params.get("user_id") or _default_user_id(state))
    entries = state["fs"].list_directory(path, user_id)
    return {
        "ok": True,
        "path": path,
        "count": len(entries),
        "entries": [
            e.to_dict() if hasattr(e, "to_dict") else str(e) for e in entries
        ],
    }


def _fs_search(params: dict) -> dict:
    state = _boot(params.get("data_dir"), params.get("sandbox"))
    query = str(_require(params, "query"))
    user_id = int(params.get("user_id") or _default_user_id(state))
    results = state["fs"].search_files(query, user_id, params.get("file_type"))
    return {
        "ok": True,
        "query": query,
        "count": len(results),
        "results": [
            r.to_dict() if hasattr(r, "to_dict") else str(r) for r in results
        ],
    }


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

    session = state["db"].Session()
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

        search = _fs_search(
            {"query": "selftest", "user_id": user_id,
             "data_dir": data_dir, "sandbox": sandbox}
        )
        steps.append({"step": "fs-search", "ok": search["ok"], "count": search["count"]})

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
            "steps": steps,
        }


def _blocked(capability: str):
    def handler(params: dict) -> dict:
        raise FlavorError(
            f"{capability} is unavailable ({KNOWN_GAPS[capability]}).\n\n{_GAP_EXPLANATION}"
        )
    return handler


_DISPATCH = {
    "status": _status,
    "self-test": _self_test,
    "fs-search": _fs_search,
    "chains": _chains,
    "training-blocks": _training_blocks,
    **{cap: _blocked(cap) for cap in KNOWN_GAPS},
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
