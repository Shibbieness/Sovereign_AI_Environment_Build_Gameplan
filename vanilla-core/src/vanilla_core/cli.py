from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .floor import check_floor
from .manifest import FlavorManifest
from .registry import FloorViolationError, discover, load_flavor


def _cmd_list(args: argparse.Namespace) -> int:
    manifests = discover(Path(args.root))
    if not manifests:
        print(f"no flavor.toml found under {args.root}")
        return 0
    for path in manifests:
        manifest = FlavorManifest.load(path)
        print(f"{manifest.name} {manifest.version}  ({path})")
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    manifest = FlavorManifest.load(Path(args.manifest))
    violations = check_floor(manifest)
    if not violations:
        print(f"PASS: {manifest.name} {manifest.version}")
        return 0
    print(f"FAIL: {manifest.name or '<unnamed flavor>'}")
    for violation in violations:
        print(f"  - {violation.check}: {violation.detail}")
    return 1


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        flavor = load_flavor(Path(args.manifest))
    except FloorViolationError as exc:
        print(f"refusing to run, floor violations: {exc}", file=sys.stderr)
        return 1
    result = flavor.run(capability=args.capability)
    print(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vanilla-core")
    sub = parser.add_subparsers(dest="command", required=True)

    list_p = sub.add_parser("list", help="discover flavor.toml manifests under a root")
    list_p.add_argument("root")
    list_p.set_defaults(func=_cmd_list)

    check_p = sub.add_parser("check", help="run the floor check against a manifest")
    check_p.add_argument("manifest")
    check_p.set_defaults(func=_cmd_check)

    run_p = sub.add_parser("run", help="load and run a flavor's entrypoint")
    run_p.add_argument("manifest")
    run_p.add_argument("--capability", default=None)
    run_p.set_defaults(func=_cmd_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    raise SystemExit(main())
