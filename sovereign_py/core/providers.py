"""LLM provider resolution — vendor names are data here, and nowhere else.

Why this module exists
----------------------
The vendor's name used to be braided through nine files: an environment
variable contract (``ANTHROPIC_API_KEY``), module-level SDK imports, attribute
names (``self.anthropic``), availability flags, and a hardcoded string
comparison in the routing path. That is nine places to change to support a
second provider, and nine places asserting a relationship with one company in
a repository that has no agreement with them.

A vendor SDK is a routing target, like a database driver or a DNS entry. It
belongs in a table, not in the shape of the code.

So: one registry, below. Every other module asks this one which provider is
active and gets back a spec. Nothing else imports a vendor SDK by name, and
nothing else names a vendor at all.

What could not be reduced to zero
---------------------------------
``package`` holds a name like ``"anthropic"`` because that is the identifier
of a distribution on PyPI. Rename it and ``pip install`` fetches nothing and
``import`` finds nothing. It is not a credit line; it is an address the
package manager resolves.

It can still be bypassed completely. Set ``LLM_PROVIDER_PACKAGE`` and
``LLM_PROVIDER_CLIENT`` and this registry is never consulted — the rows below
are a convenience default for the two SDKs this codebase already spoke to, not
a requirement, and not a list anyone is obliged to appear on.

Resolution order
----------------
1. ``LLM_PROVIDER_PACKAGE`` + ``LLM_PROVIDER_CLIENT``  → an ad-hoc spec; the
   registry is skipped entirely.
2. ``LLM_PROVIDER`` naming a registry row.
3. The first registry row that has a key present in the environment.
4. Nothing. ``resolve()`` returns ``None`` and callers degrade to local ML.

Step 4 is a real answer, not a failure. Every caller in this tree is written
to run without any provider at all, and that path is the one the tests
exercise, because it is the one most installations will take.
"""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass

__all__ = [
    "ProviderSpec", "PROVIDERS", "resolve", "api_key_for", "load_client",
    "provider_packages", "GENERIC_KEY_ENV", "ProviderError",
]

# The vendor-neutral variable this codebase actually documents. A provider's
# own conventional variable (see ProviderSpec.env_key) is still honoured, so an
# existing .env keeps working — but through a data lookup, not a name baked
# into the code.
GENERIC_KEY_ENV = "LLM_API_KEY"


class ProviderError(RuntimeError):
    """Raised when a provider is named but cannot be loaded."""


@dataclass(frozen=True)
class ProviderSpec:
    id: str            # what `LLM_PROVIDER` / a connection row says
    package: str       # importable distribution name — see the note above
    client: str        # attribute to pull out of that package
    env_key: str       # this vendor's conventional key variable
    default_model: str

    def api_key(self) -> str | None:
        """Generic variable first, this provider's conventional one second."""
        return os.getenv(GENERIC_KEY_ENV) or os.getenv(self.env_key)


# Two rows, because these are the two SDKs the code in this tree already knew
# how to call. Adding a third is a row, not a refactor — which is the whole
# point of the module.
PROVIDERS: dict[str, ProviderSpec] = {
    "anthropic": ProviderSpec(
        id="anthropic", package="anthropic", client="Anthropic",
        env_key="ANTHROPIC_API_KEY", default_model="claude-sonnet-4-20250514",
    ),
    "openai": ProviderSpec(
        id="openai", package="openai", client="OpenAI",
        env_key="OPENAI_API_KEY", default_model="gpt-4o",
    ),
}


def _from_env_override() -> ProviderSpec | None:
    package = os.getenv("LLM_PROVIDER_PACKAGE")
    client = os.getenv("LLM_PROVIDER_CLIENT")
    if not package or not client:
        return None
    return ProviderSpec(
        id=os.getenv("LLM_PROVIDER", package),
        package=package,
        client=client,
        env_key=GENERIC_KEY_ENV,
        default_model=os.getenv("LLM_DEFAULT_MODEL", ""),
    )


def resolve(name: str | None = None) -> ProviderSpec | None:
    """The active provider spec, or None when no provider is configured.

    `name` overrides the environment — used by the routing path, where the
    provider is a column on a stored connection rather than a process-wide
    setting.
    """
    if name:
        spec = PROVIDERS.get(name.strip().lower())
        if spec is not None:
            return spec
        override = _from_env_override()
        # An unknown name with a matching env override is a deliberate
        # pointing-at-something-new; an unknown name with nothing behind it is
        # a typo, and returning None would hide it as "no provider configured".
        if override is not None and override.id == name.strip().lower():
            return override
        raise ProviderError(
            f"unknown provider {name!r}; known: {sorted(PROVIDERS)}. Set "
            f"LLM_PROVIDER_PACKAGE and LLM_PROVIDER_CLIENT to use one that is "
            f"not listed.")

    override = _from_env_override()
    if override is not None:
        return override

    requested = os.getenv("LLM_PROVIDER")
    if requested:
        return resolve(requested)

    for spec in PROVIDERS.values():
        if spec.api_key():
            return spec
    return None


def api_key_for(spec: ProviderSpec | None = None) -> str | None:
    spec = spec or resolve()
    return spec.api_key() if spec else None


def load_client(spec: ProviderSpec | None = None, *, api_key: str | None = None):
    """Import the SDK and return a constructed client.

    Deliberately imported here and not at module scope anywhere in this tree.
    A module-level `from <sdk> import <Client>` makes an optional dependency
    mandatory at import time: `ml_agents_v1_GHOST_BONE.py` did exactly that and
    could not be imported at all on a machine without the SDK installed. Same
    shape as the reportlab defect in Eidoa and the flask defect in this
    package's own flavor — a graceful-degradation path written where the thing
    never went missing.
    """
    spec = spec or resolve()
    if spec is None:
        raise ProviderError(
            f"no LLM provider configured — set {GENERIC_KEY_ENV}, or "
            f"LLM_PROVIDER_PACKAGE and LLM_PROVIDER_CLIENT for an SDK that is "
            f"not in the registry")

    key = api_key or spec.api_key()
    if not key:
        raise ProviderError(
            f"provider {spec.id!r} selected but no API key found — set "
            f"{GENERIC_KEY_ENV} or {spec.env_key}")

    try:
        module = importlib.import_module(spec.package)
    except ImportError as exc:
        raise ProviderError(
            f"provider {spec.id!r} needs the {spec.package!r} package: "
            f"pip install -r entry/requirements-llm.txt  ({exc})") from exc

    try:
        factory = getattr(module, spec.client)
    except AttributeError as exc:
        raise ProviderError(
            f"{spec.package!r} has no {spec.client!r} — the SDK's API changed, "
            f"or LLM_PROVIDER_CLIENT names the wrong attribute") from exc

    return factory(api_key=key)


# ── call adapters ─────────────────────────────────────────────────────────
#
# SDKs differ in call shape, not just in name, so the registry alone is not
# enough to place a call. Each adapter takes (client, model, prompt, max_tokens)
# and returns (text, tokens_used).
#
# There is exactly one adapter here, and that is deliberate. It is a
# transcription of the only call path this codebase ever actually had — the
# one that was inline in ml_runtime/enhanced_agents.py. No second adapter has
# been written, because writing one for an SDK nobody here has exercised would
# be shipping a code path whose first real test is someone else's outage.
#
# A provider with no adapter behaves exactly as it did before this refactor:
# the caller reports `no_api_caller_for_provider`. Adding one is a function,
# not a refactor.

def _chat_messages_api(client, model, prompt, max_tokens):
    response = client.messages.create(
        model=model, max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return (response.content[0].text,
            response.usage.input_tokens + response.usage.output_tokens)


CHAT_ADAPTERS = {
    "anthropic": _chat_messages_api,
}


# Connection tests are a smaller problem than completions: send a token, read
# back the model name and a usage count. Both shapes below are transcriptions
# of what server/api_manager.py already did inline, so both are real.
#
# Note the asymmetry with CHAT_ADAPTERS above, which has only one entry. That
# is not an oversight: api_manager's OpenAI branch reads `.model` and
# `.usage.total_tokens` but never extracts response *text*, so no transcribed
# text-extraction path for it exists anywhere in this codebase. Writing one
# from memory is exactly the kind of untested path this module is trying to
# stop shipping.

def _ping_messages_api(client, model):
    r = client.messages.create(
        model=model or "claude-sonnet-4-20250514", max_tokens=10,
        messages=[{"role": "user", "content": "Hi"}])
    return r.model, r.usage.input_tokens + r.usage.output_tokens


def _ping_chat_completions(client, model):
    r = client.chat.completions.create(
        model=model or "gpt-4", max_tokens=10,
        messages=[{"role": "user", "content": "Hi"}])
    return r.model, r.usage.total_tokens


PING_ADAPTERS = {
    "anthropic": _ping_messages_api,
    "openai": _ping_chat_completions,
}


def has_chat_adapter(spec: ProviderSpec | None) -> bool:
    return spec is not None and spec.id in CHAT_ADAPTERS


def has_ping_adapter(spec: ProviderSpec | None) -> bool:
    return spec is not None and spec.id in PING_ADAPTERS


def ping(spec: ProviderSpec, client, *, model: str | None = None) -> tuple[str, int]:
    """Smoke-test a connection. Returns (model_name, tokens_used)."""
    adapter = PING_ADAPTERS.get(spec.id)
    if adapter is None:
        raise ProviderError(f"no connection test for provider:{spec.id}")
    return adapter(client, model)


def chat(spec: ProviderSpec, client, prompt: str, *, model: str | None = None,
         max_tokens: int = 1000) -> tuple[str, int]:
    """Place one completion call. Returns (text, tokens_used)."""
    adapter = CHAT_ADAPTERS.get(spec.id)
    if adapter is None:
        raise ProviderError(f"no_api_caller_for_provider:{spec.id}")
    return adapter(client, model or spec.default_model, prompt, max_tokens)


def provider_packages() -> tuple[str, ...]:
    """Package names any configured provider might need.

    Used by the flavor adapter to report optional subsystems without naming a
    vendor in its own source.
    """
    names = {spec.package for spec in PROVIDERS.values()}
    override = _from_env_override()
    if override is not None:
        names.add(override.package)
    return tuple(sorted(names))
