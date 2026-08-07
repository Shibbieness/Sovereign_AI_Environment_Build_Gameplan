def run(capability: str | None = None) -> dict:
    """Minimal proof that Vanilla Core can discover, floor-check, and execute
    a flavor end to end. Real flavors (Eidoa, ML Filesystem, QRen Coder, the
    Sovereign AI Environment gameplan) replace this module; the manifest
    contract is what stays constant."""
    return {"capability": capability or "greet", "message": "hello from a Vanilla Core flavor"}
