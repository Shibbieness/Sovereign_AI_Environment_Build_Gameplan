from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# A flavor may declare any license it actually holds rights to use; these are
# the ones Vanilla Core recognizes out of the box. Add to this set in the
# same change that adds the license text/explanation the flavor needs.
KNOWN_LICENSES = {"AGPL-3.0-or-later", "AGPL-3.0-only", "MIT", "Commercial"}

# Strings that must never appear in a flavor's own manifest metadata: vendor
# contact addresses, private chat-session links, and vendor co-author
# trailers. These are deliberately specific rather than blanket vendor-name
# matches — a flavor that legitimately integrates a vendor's API needs to be
# able to say so (e.g. capabilities = ["anthropic-api-routing"]) without
# tripping the floor. The target is misattribution and leaked links, not
# mentioning a vendor at all.
DISALLOWED_MARKERS = (
    "noreply@anthropic.com",
    "claude.ai/code/session",
    "claude.ai/share",
    "co-authored-by: claude",
)


@dataclass(frozen=True)
class FlavorManifest:
    name: str
    version: str
    license: str
    entrypoint: str
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    path: Path | None = None

    @classmethod
    def load(cls, manifest_path: Path) -> "FlavorManifest":
        data = tomllib.loads(Path(manifest_path).read_text())
        flavor = data.get("flavor", {})
        return cls(
            name=flavor.get("name", ""),
            version=flavor.get("version", ""),
            license=flavor.get("license", ""),
            entrypoint=flavor.get("entrypoint", ""),
            capabilities=tuple(flavor.get("capabilities", [])),
            path=Path(manifest_path).resolve().parent,
        )
