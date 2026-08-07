"""
ragready_common.py — Shared parsing and helpers for the ragready validator.

Pure stdlib. No external dependencies. Minimal frontmatter parser handles a
constrained YAML subset (scalars, inline lists, block lists, 2-space nesting).
"""

from __future__ import annotations

import re
import os
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ----------------------------------------------------------------------------
# Frontmatter parser — minimal YAML subset
# ----------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n", re.DOTALL)


def _coerce_scalar(value: str) -> Any:
    v = value.strip()
    if v == "" or v.lower() == "null" or v == "~":
        return None
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    # quoted strings
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    # numbers
    try:
        if "." in v or "e" in v.lower():
            return float(v)
        return int(v)
    except ValueError:
        pass
    return v


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from a markdown document.

    Supports: scalars, inline lists [a, b, c], block lists with `- item`,
    and nested keys via 2-space indent.

    Returns (frontmatter_dict, body_text). If no frontmatter, returns ({}, text).
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text

    fm_text = m.group(1)
    body = text[m.end():]

    result: dict = {}
    stack: list[tuple[int, dict | list]] = [(-1, result)]
    pending_list_key: str | None = None

    for raw_line in fm_text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        # Pop stack to current indent level
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1] if stack else result

        # List item under a key
        if line.startswith("- "):
            item = line[2:].strip()
            if isinstance(parent, list):
                parent.append(_coerce_scalar(item))
            elif isinstance(parent, dict) and pending_list_key:
                lst = parent.setdefault(pending_list_key, [])
                if ": " in item and not item.startswith('"'):
                    # list of mappings
                    obj: dict = {}
                    k, _, v = item.partition(": ")
                    obj[k.strip()] = _coerce_scalar(v)
                    lst.append(obj)
                    stack.append((indent, obj))
                else:
                    lst.append(_coerce_scalar(item))
            continue

        # key: value or key:
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if value == "":
                # nested object or list follows
                child: dict | list = {}
                if isinstance(parent, dict):
                    parent[key] = child
                pending_list_key = key
                stack.append((indent, child))
            elif value.startswith("[") and value.endswith("]"):
                inner = value[1:-1]
                items = [_coerce_scalar(x) for x in inner.split(",") if x.strip()]
                if isinstance(parent, dict):
                    parent[key] = items
                pending_list_key = None
            else:
                if isinstance(parent, dict):
                    parent[key] = _coerce_scalar(value)
                pending_list_key = None

    return result, body


# ----------------------------------------------------------------------------
# Section extraction
# ----------------------------------------------------------------------------

_SECTION_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+?)(?:\s+\{#([^}]+)\})?\s*$", re.MULTILINE)
_BLOCK_TYPE_RE = re.compile(r"^\[block:\s*([a-zA-Z0-9_-]+)\s*\]\s*$", re.MULTILINE)
_SOURCE_RE = re.compile(r"^\[source:\s*([^\]]+)\]\s*$", re.MULTILINE)
_FUSES_RE = re.compile(r"^\[fuses-with:\s*([^\]]+)\]\s*$", re.MULTILINE)
_ANCHOR_REF_RE = re.compile(r"⟨ANCHOR\s+([^⟩\s]+)\s*⟩")
_TOKEN_RE = re.compile(r"⟨([A-Z]+)(?:\s+([^⟩]+))?⟩")


@dataclass
class Section:
    level: int
    title: str
    anchor: str | None
    block_type: str | None
    source: str | None
    fuses_with: list[str] = field(default_factory=list)
    anchor_refs: list[str] = field(default_factory=list)
    tokens: list[tuple[str, str]] = field(default_factory=list)
    body: str = ""
    start_line: int = 0


def extract_sections(body: str) -> list[Section]:
    """Walk a doc body and pull out sections."""
    lines = body.splitlines(keepends=True)
    headers: list[tuple[int, re.Match]] = []
    offset = 0
    for i, line in enumerate(lines):
        m = _SECTION_HEADER_RE.match(line)
        if m:
            headers.append((i, m))
        offset += len(line)

    sections: list[Section] = []
    for idx, (line_no, m) in enumerate(headers):
        level = len(m.group(1))
        title = m.group(2).strip()
        anchor = m.group(3)
        # body of section runs to next header
        next_line = headers[idx + 1][0] if idx + 1 < len(headers) else len(lines)
        sec_text = "".join(lines[line_no + 1 : next_line])

        block_type = None
        bt_m = _BLOCK_TYPE_RE.search(sec_text)
        if bt_m:
            block_type = bt_m.group(1)

        source = None
        src_m = _SOURCE_RE.search(sec_text)
        if src_m:
            source = src_m.group(1).strip()

        fuses = []
        fz_m = _FUSES_RE.search(sec_text)
        if fz_m:
            fuses = [x.strip() for x in fz_m.group(1).split(",") if x.strip()]

        anchor_refs = _ANCHOR_REF_RE.findall(sec_text)
        tokens = [(t.group(1), (t.group(2) or "").strip()) for t in _TOKEN_RE.finditer(sec_text)]

        sections.append(Section(
            level=level,
            title=title,
            anchor=anchor,
            block_type=block_type,
            source=source,
            fuses_with=fuses,
            anchor_refs=anchor_refs,
            tokens=tokens,
            body=sec_text,
            start_line=line_no + 1,
        ))
    return sections


# ----------------------------------------------------------------------------
# Profile loading
# ----------------------------------------------------------------------------

def find_profile(start_path: Path) -> Path | None:
    """Walk up from start_path looking for ragready.profile.yaml."""
    p = start_path.resolve()
    if p.is_file():
        p = p.parent
    while True:
        candidate = p / "ragready.profile.yaml"
        if candidate.is_file():
            return candidate
        if p.parent == p:
            return None
        p = p.parent


def load_profile(profile_path: Path) -> dict:
    """Load a profile YAML file using our minimal parser."""
    text = profile_path.read_text(encoding="utf-8")
    # Profile files don't have frontmatter delimiters — they're just YAML.
    # Wrap to use our parser.
    wrapped = "---\n" + text + "\n---\n"
    fm, _ = parse_frontmatter(wrapped)
    return fm


DEFAULT_BLOCK_TYPES = {
    "concept", "procedure", "spec", "code",
    "slm", "daemon", "corpus", "note", "glyph",
}


# ----------------------------------------------------------------------------
# Validation result types
# ----------------------------------------------------------------------------

@dataclass
class Finding:
    severity: str  # "pass", "warn", "fail"
    check: str
    message: str
    location: str = ""


@dataclass
class ValidationReport:
    target: str
    findings: list[Finding] = field(default_factory=list)

    def pass_(self, check: str, message: str = "", location: str = "") -> None:
        self.findings.append(Finding("pass", check, message, location))

    def warn(self, check: str, message: str, location: str = "") -> None:
        self.findings.append(Finding("warn", check, message, location))

    def fail(self, check: str, message: str, location: str = "") -> None:
        self.findings.append(Finding("fail", check, message, location))

    @property
    def passed(self) -> bool:
        return not any(f.severity == "fail" for f in self.findings)

    def to_text(self, verbose: bool = False) -> str:
        out: list[str] = []
        out.append(f"=== Validation report: {self.target} ===")
        for f in self.findings:
            if f.severity == "pass" and not verbose:
                continue
            tag = {"pass": "✓", "warn": "!", "fail": "✗"}[f.severity]
            line = f"  [{tag}] {f.check}"
            if f.message:
                line += f" — {f.message}"
            if f.location:
                line += f" ({f.location})"
            out.append(line)
        passed_n = sum(1 for f in self.findings if f.severity == "pass")
        warn_n = sum(1 for f in self.findings if f.severity == "warn")
        fail_n = sum(1 for f in self.findings if f.severity == "fail")
        out.append(f"--- pass:{passed_n} warn:{warn_n} fail:{fail_n} ---")
        out.append("RESULT: " + ("PASS" if self.passed else "FAIL"))
        return "\n".join(out)

    def to_json(self) -> str:
        return json.dumps({
            "target": self.target,
            "passed": self.passed,
            "findings": [
                {"severity": f.severity, "check": f.check, "message": f.message, "location": f.location}
                for f in self.findings
            ],
        }, indent=2)


# ----------------------------------------------------------------------------
# File walking
# ----------------------------------------------------------------------------

def walk_markdown(path: Path) -> list[Path]:
    """Return all .md files under path. If path is a file, return [path]."""
    if path.is_file():
        return [path]
    results: list[Path] = []
    for root, _, files in os.walk(path):
        for f in files:
            if f.endswith(".md"):
                results.append(Path(root) / f)
    return sorted(results)


# ----------------------------------------------------------------------------
# Heuristic checks
# ----------------------------------------------------------------------------

PRONOUN_REFERENCE_PATTERNS = [
    re.compile(r"\b(this|that|these|those)\s+(was|is|will be|approach|idea|concept|step|stage|section|paragraph)\b", re.IGNORECASE),
    re.compile(r"\b(as discussed|as mentioned|as described)\s+(above|earlier|previously)\b", re.IGNORECASE),
    re.compile(r"\bsee\s+(above|earlier)\b", re.IGNORECASE),
]


def has_back_reference(section_body: str) -> tuple[bool, str]:
    """Heuristic: does this section assume the previous section was just read?"""
    # Skip code blocks and citations
    cleaned = re.sub(r"```.*?```", "", section_body, flags=re.DOTALL)
    cleaned = re.sub(r"`[^`]+`", "", cleaned)
    for pat in PRONOUN_REFERENCE_PATTERNS:
        m = pat.search(cleaned)
        if m:
            return True, m.group(0)
    return False, ""
