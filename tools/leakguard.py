#!/usr/bin/env python3
"""Publication guard — refuse to publish content that must stay private.

Why this exists rather than a .gitignore:

  * .gitignore only stops *untracked* files. Anything already committed is
    published the moment the remote is public, and rewriting history does
    not recall what was already fetched.
  * .gitignore matches paths. Leaks are content. A file named
    `distribution_model.py` looks like engine code and contains financial
    strategy; a file named `decisions.py` looks like logic and contains the
    decision substrate as Python literals. Both were found by reading, not
    by their names.
  * .gitignore is advisory. `git add -f`, an editor plugin, a packaging
    step, or a tool that does not consult it will all sail straight past.

This scans file *contents* against a denylist, reports every hit with
file:line, and exits non-zero. Wire it into CI and a pre-commit hook so the
rule is enforced by machinery rather than by remembering.

The envelope, not just the payload
----------------------------------
For a while this tool scanned tracked file contents and nothing else, and
reported `130 files scanned, no leaks — safe to publish` across a repository
where 39 commits carried a vendor address in their author identity and their
Co-Authored-By trailer.

Every one of those was published exactly as much as any file was. Commit
messages and author identities travel with the repository, show on every
GitHub commit page, and survive in every clone. The guard was reading the
letter and never the envelope it came in.

`--history` closes that. It is a separate mode rather than the default
because the two answer different questions — "is this working tree safe to
publish" and "is this repository's record safe to publish" — and a run that
silently answered both would make the file-scan exit code mean something new
without saying so.

Usage:
    leakguard.py                      scan git-tracked files in cwd
    leakguard.py path [path ...]      scan specific paths
    leakguard.py --history            scan commit messages + author identities
                                        across every ref
    leakguard.py --staged-msg FILE    scan one prospective commit message
                                        (for a commit-msg hook)
    leakguard.py --patterns FILE      use a custom denylist (one regex/line)
    leakguard.py --list               print the active denylist and exit

Exit codes: 0 clean · 1 leak found · 2 usage error.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Default denylist. Case-insensitive regexes.
#
# Seeded from the canonical-term list the GILWRIGHT scrub checklist already
# maintains (FORGE.md Appendix B), plus the vendor-attribution and
# session-link markers Vanilla Core's floor rejects. Extend it whenever a
# leak is found — a term list that never grows is a term list nobody is
# checking against reality.
DEFAULT_PATTERNS = [
    # vendor attribution / leaked session links
    r"noreply@anthropic\.com",
    r"claude\.ai/code/session",
    r"claude\.ai/share",
    r"co-authored-by:\s*claude",
    # credentials — never publishable regardless of project
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"\bAKIA[0-9A-Z]{16}\b",
    r"\bgh[pousr]_[A-Za-z0-9]{20,}",
    r"\bsk-(ant-)?[A-Za-z0-9_\-]{20,}",
    # business-substrate markers: presence means a corpus leaked into code
    r"audience world",
    r"capability node",
    r"spending policy",
    r"owner distribution",
    r"reserve position",
    r"revenue hierarchy",
    r"invariant floor",
    r"sole owner regardless",
]

# Exemptions. A file whose *purpose* is to define or test the prohibition
# must contain the forbidden pattern — the floor cannot reject a vendor
# address without naming one, and its tests cannot prove it works without
# planting one.
#
# This list is deliberately a set of exact paths, never a glob or a
# directory. A blanket exemption is how a guard quietly stops guarding: the
# GILWRIGHT scrub reported "zero canonical-term hits" while its shipped
# product contained the pattern it forbade, because the checklist had no way
# to say "this one is legitimate" and so the claim was simply wrong.
# Recording an exemption explicitly keeps the claim true.
DEFAULT_ALLOWLIST = {
    "tools/leakguard.py",
    "tools/test_leakguard.py",
    # defines the disallowed markers the flavor floor rejects
    "vanilla-core/src/vanilla_core/manifest.py",
    # plants each marker to prove the floor actually rejects it
    "vanilla-core/tests/test_floor.py",
}

_BINARY = re.compile(rb"[\x00]")


def tracked_files(root: Path) -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=False
    )
    if out.returncode != 0:
        raise SystemExit(f"not a git repository: {root}")
    return [root / line for line in out.stdout.split("\n") if line.strip()]


def load_patterns(path: Path | None) -> list[str]:
    if path is None:
        return list(DEFAULT_PATTERNS)
    lines = path.read_text().splitlines()
    return [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]


def scan_file(path: Path, regexes: list[re.Pattern]) -> list[tuple[int, str, str]]:
    """Return (line_no, pattern, excerpt) for every hit."""
    try:
        raw = path.read_bytes()
    except (OSError, IsADirectoryError):
        return []
    if _BINARY.search(raw[:8192]):
        # Binary files cannot be reviewed line by line. A database or archive
        # is exactly where a corpus hides, so flag it for a human rather than
        # silently skipping it.
        text = raw.decode("utf-8", errors="ignore")
        hits = []
        for rx in regexes:
            if rx.search(text):
                hits.append((0, rx.pattern, "<binary file — inspect manually>"))
        return hits

    hits = []
    for n, line in enumerate(raw.decode("utf-8", errors="replace").splitlines(), 1):
        for rx in regexes:
            if rx.search(line):
                hits.append((n, rx.pattern, line.strip()[:120]))
    return hits


# ── history ───────────────────────────────────────────────────────────────
#
# A commit carries four things a denylist should see: the message, and the
# author and committer identities (name plus email). The identity fields
# matter on their own — a commit whose message is spotless still publishes
# `Claude <noreply@anthropic.com>` on every view of it, and a message-only
# scan reports that repository clean.

_RECORD_SEP = "\x1e"
_FIELD_SEP = "\x1f"


def scan_history(root: Path, regexes: list[re.Pattern]) -> tuple[list[str], int]:
    """Return (findings, commits_scanned) across every ref in the repo."""
    fmt = _FIELD_SEP.join(["%H", "%an <%ae>", "%cn <%ce>", "%B"]) + _RECORD_SEP
    out = subprocess.run(
        ["git", "log", "--all", "--no-color", f"--format={fmt}"],
        cwd=root, capture_output=True, text=True, check=False)
    if out.returncode != 0:
        raise SystemExit(f"not a git repository: {root}")

    findings: list[str] = []
    records = [r for r in out.stdout.split(_RECORD_SEP) if r.strip()]
    for record in records:
        parts = record.lstrip("\n").split(_FIELD_SEP)
        if len(parts) < 4:
            continue
        sha, author, committer, message = parts[0], parts[1], parts[2], parts[3]
        for label, value in (("author", author), ("committer", committer),
                             ("message", message)):
            for rx in regexes:
                for line in value.splitlines() or [""]:
                    if rx.search(line):
                        findings.append(
                            f"  LEAK  {sha[:12]} {label}\n"
                            f"        pattern: {rx.pattern}\n"
                            f"        {line.strip()[:120]}")
    return findings, len(records)


def scan_message_file(path: Path, regexes: list[re.Pattern]) -> list[str]:
    """Scan one prospective commit message. For a commit-msg hook."""
    findings = []
    for n, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
        for rx in regexes:
            if rx.search(line):
                findings.append(
                    f"  LEAK  commit message:{n}\n"
                    f"        pattern: {rx.pattern}\n"
                    f"        {line.strip()[:120]}")
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="leakguard")
    ap.add_argument("paths", nargs="*", help="files to scan; default = git-tracked")
    ap.add_argument("--patterns", type=Path, help="denylist file, one regex per line")
    ap.add_argument("--allow", action="append", default=[], help="repo-relative path to skip")
    ap.add_argument("--list", action="store_true", help="print denylist and exit")
    ap.add_argument("--history", action="store_true",
                    help="scan commit messages and author identities across all refs")
    ap.add_argument("--staged-msg", type=Path, metavar="FILE",
                    help="scan one prospective commit message (commit-msg hook)")
    args = ap.parse_args(argv)

    patterns = load_patterns(args.patterns)
    if args.list:
        for p in patterns:
            print(p)
        return 0

    regexes = [re.compile(p, re.IGNORECASE) for p in patterns]
    root = Path.cwd()

    if args.staged_msg:
        findings = scan_message_file(args.staged_msg, regexes)
        for f in findings:
            print(f)
        if findings:
            print(f"\n  {len(findings)} leak(s) in the commit message — COMMIT BLOCKED")
            return 1
        return 0

    if args.history:
        findings, commits = scan_history(root, regexes)
        for f in findings:
            print(f)
        if findings:
            print(f"\n  {len(findings)} leak(s) across {commits} commits — PUBLICATION BLOCKED")
            return 1
        # Naming the population matters: "0 leaks" over 0 commits is true and
        # says nothing, and this tool has already shipped one clean-looking
        # report that was measuring the wrong thing.
        print(f"  {commits} commits scanned (message + author + committer), no leaks")
        return 0
    allow = DEFAULT_ALLOWLIST | set(args.allow)

    targets = [Path(p) for p in args.paths] if args.paths else tracked_files(root)

    findings = 0
    for path in targets:
        try:
            rel = str(path.resolve().relative_to(root.resolve()))
        except ValueError:
            rel = str(path)
        if rel in allow or not path.is_file():
            continue
        for line_no, pattern, excerpt in scan_file(path, regexes):
            findings += 1
            where = f"{rel}:{line_no}" if line_no else rel
            print(f"  LEAK  {where}\n        pattern: {pattern}\n        {excerpt}")

    scanned = sum(1 for p in targets if p.is_file())
    if findings:
        print(f"\n  {findings} leak(s) across {scanned} files — PUBLICATION BLOCKED")
        return 1
    print(f"  {scanned} files scanned, no leaks — safe to publish")
    return 0


if __name__ == "__main__":
    sys.exit(main())
