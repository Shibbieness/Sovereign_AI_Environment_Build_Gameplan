from __future__ import annotations

from dataclasses import dataclass

from .manifest import DISALLOWED_MARKERS, KNOWN_LICENSES, FlavorManifest


@dataclass(frozen=True)
class FloorViolation:
    check: str
    detail: str


def check_floor(manifest: FlavorManifest) -> list[FloorViolation]:
    """The minimum a flavor must satisfy before Vanilla Core will run it.

    This is deliberately small. It is not a stand-in for a full CASL/security
    review of a flavor's actual behavior — it is the floor: the handful of
    things that must never regress silently (missing license, stray
    third-party attribution, an unresolvable entrypoint).
    """
    violations: list[FloorViolation] = []

    if not manifest.name:
        violations.append(FloorViolation("name", "flavor.name is required"))
    if not manifest.version:
        violations.append(FloorViolation("version", "flavor.version is required"))
    if manifest.license not in KNOWN_LICENSES:
        violations.append(
            FloorViolation(
                "license",
                f"flavor.license must be one of {sorted(KNOWN_LICENSES)}, got {manifest.license!r}",
            )
        )
    if not manifest.entrypoint or ":" not in manifest.entrypoint:
        violations.append(
            FloorViolation("entrypoint", "flavor.entrypoint must be 'module:callable'")
        )

    haystack = " ".join(
        [manifest.name, manifest.version, manifest.license, manifest.entrypoint, *manifest.capabilities]
    ).lower()
    for marker in DISALLOWED_MARKERS:
        if marker in haystack:
            violations.append(
                FloorViolation("attribution", f"manifest contains a disallowed marker: {marker!r}")
            )

    return violations
