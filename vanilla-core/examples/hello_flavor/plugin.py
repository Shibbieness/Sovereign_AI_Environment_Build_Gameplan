def run(capability: str | None = None, params: dict | None = None) -> dict:
    """Minimal proof that Vanilla Core can discover, floor-check, and execute
    a flavor end to end. Real flavors replace this module; the contract —
    a flavor.toml plus run(capability, params) — is what stays constant."""
    params = params or {}
    return {
        "capability": capability or "greet",
        "message": "hello from a Vanilla Core flavor",
        "params": params,
    }
