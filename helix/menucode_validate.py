#!/usr/bin/env python3
"""
menucode_validate.py — Helix Codex P3.2.

Named across multiple Helix canonical documents as "the first concrete
artifact" in the implementation backlog: "the smallest, most independent
piece... it unlocks everything else... it produces immediate value" (the
Custom Third Set file can be checked for compliance immediately). This is
that artifact, built for real against the Custom Third Set spec (Helix
Codex canonical_documents/menucode_documentation.md Section XI).

Checks a MenuCode Custom Third Set-style Python file against all 8
documented formatting conventions. Uses AST parsing for semantic checks
(fragment/NOTES dict structure, naming, DEPLOYMENT_CONTEXT, import
ordering) and line-based regex for the stylistic conventions (section
dividers, bracketed docstring headers) that don't have AST representation.

Honesty note: menucode_documentation.md Section XI - Alt shows an
illustrative example CLI run with specific counts (e.g. "12 docstrings").
Those are the document's own worked illustration, not a fixture this
validator is tuned to reproduce — it reports whatever the real counts are
for whatever file it's pointed at, including this repo's own
menucode_third_set.py (which does not match the illustration's numbers
exactly; see README notes in the commit that added this file).

Usage:
    python3 -m helix.menucode_validate <path/to/file.py>
"""

import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

REQUIRED_OPTION_NOTE_FIELDS = ('description', 'type', 'valid_range', 'default',
                                'semantic_role', 'affects', 'requires')
VALID_SEMANTIC_ROLES = {'computational', 'semantic', 'structural', 'temporal'}
VALID_DEPLOYMENT_CONTEXTS_PREFIXES = ('public', 'internal', 'specific:')

_TOP_DIVIDER_RE = re.compile(r'^#\s*(=+)\s*$')
_MID_DIVIDER_RE = re.compile(r'^#\s*(-+)\s*$')
_FRAGMENT_HEADER_RE = re.compile(r'\[\s*FRAGMENT\s+\d+\s*[—-]\s*([A-Z0-9_]+)\s*\]')
_BRACKET_HEADER_RE = re.compile(r'^\[ ([^\]]+) \]$')
_UPPER_SNAKE_RE = re.compile(r'^[A-Z][A-Z0-9_]*$')


@dataclass
class ConventionResult:
    number: int
    name: str
    passed: bool
    detail: str
    violations: List[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    path: str
    results: List[ConventionResult]

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    def render(self) -> str:
        lines = [f"$ menucode_validate.py {self.path}"]
        for r in self.results:
            mark = '[+]' if r.passed else '[-]'
            lines.append(f"{mark} Convention {r.number} ({r.name}): {'PASS' if r.passed else 'FAIL'} ({r.detail})")
            for v in r.violations:
                lines.append(f"      - {v}")
        if self.all_passed:
            lines.append("[+] Overall: VALID Custom Third Set form")
        else:
            failed = sum(1 for r in self.results if not r.passed)
            lines.append(f"[-] Overall: INVALID Custom Third Set form ({failed} convention(s) failed)")
        return '\n'.join(lines)


def _module_level_dict_assigns(tree: ast.Module):
    """Yield (name, ast.Assign, ast.Dict) for every top-level `NAME = {...}`."""
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if isinstance(node.value, ast.Dict):
                yield node.targets[0].id, node, node.value


def _module_level_docstring_exprs(tree: ast.Module):
    """Yield (ast.Expr, str) for every standalone string-literal statement at module level."""
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, (ast.Constant,)) and isinstance(node.value.value, str):
            yield node, node.value.value


def check_convention_1(source: str, tree: ast.Module) -> ConventionResult:
    """Fragment Block Structure: divider + bracketed docstring + dict + NOTES dict + blank line."""
    lines = source.splitlines()
    headers = [(m.start(), m.group(1)) for m in _FRAGMENT_HEADER_RE.finditer(source)]
    dict_names = {name for name, _, _ in _module_level_dict_assigns(tree)}

    violations = []
    for _, name in headers:
        if name not in dict_names:
            violations.append(f"Fragment header names {name!r} but no `{name} = {{...}}` dict found")
        elif f"{name}_NOTES" not in dict_names:
            violations.append(f"Fragment {name!r} has no matching `{name}_NOTES` dict")

    detail = f"{len(headers)} fragments detected"
    return ConventionResult(1, "Fragment Block Structure", len(violations) == 0, detail, violations)


def check_convention_2(tree: ast.Module) -> ConventionResult:
    """Naming Convention: UPPER_SNAKE_CASE for fragment names and their dict keys."""
    violations = []
    for name, assign_node, dict_node in _module_level_dict_assigns(tree):
        if name.endswith('_NOTES'):
            continue  # NOTES dicts checked via their base fragment's keys below
        if not _UPPER_SNAKE_RE.match(name):
            violations.append(f"Fragment variable {name!r} is not UPPER_SNAKE_CASE")
        for key_node in dict_node.keys:
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                if not _UPPER_SNAKE_RE.match(key_node.value):
                    violations.append(f"Option key {key_node.value!r} in {name} is not UPPER_SNAKE_CASE")
    return ConventionResult(2, "Naming Convention", len(violations) == 0,
                             "checked" if not violations else f"{len(violations)} violation(s)", violations)


def check_convention_3(source: str) -> ConventionResult:
    """Section Divider Hierarchy: consistent top-level (=) vs mid-level (-) dividers."""
    lines = source.splitlines()
    top_lengths = set()
    mid_lengths = set()
    top_count = 0
    mid_count = 0
    violations = []

    for i, line in enumerate(lines, 1):
        m_top = _TOP_DIVIDER_RE.match(line)
        m_mid = _MID_DIVIDER_RE.match(line)
        if m_top:
            top_count += 1
            top_lengths.add(len(m_top.group(1)))
        elif m_mid:
            mid_count += 1
            mid_lengths.add(len(m_mid.group(1)))
        elif '=====' in line and not line.strip().startswith('#'):
            pass  # divider-looking content inside a docstring body; not a comment-line divider, ignore

    if len(top_lengths) > 1:
        violations.append(f"Top-level dividers use inconsistent lengths: {sorted(top_lengths)}")
    if len(mid_lengths) > 1:
        violations.append(f"Mid-level dividers use inconsistent lengths: {sorted(mid_lengths)}")

    detail = f"{top_count} top-level, {mid_count} mid-level, {len(violations)} violations"
    return ConventionResult(3, "Section Divider Hierarchy", len(violations) == 0, detail, violations)


def check_convention_4(tree: ast.Module) -> ConventionResult:
    """Docstring Format: bracketed [ HEADER ] with rule lines above/below, per module-level string block."""
    violations = []
    matching = 0
    total = 0
    for _, text in _module_level_docstring_exprs(tree):
        stripped_lines = [ln.strip() for ln in text.strip('\n').splitlines()]
        if not stripped_lines:
            continue
        total += 1
        is_structural = len(stripped_lines) >= 3 and set(stripped_lines[0]) <= {'='} and _BRACKET_HEADER_RE.match(stripped_lines[1] if len(stripped_lines) > 1 else '')
        if not is_structural:
            # Not every module-level string is a structural docstring (e.g. plain
            # comments-as-strings); only ones that *start* the bracket pattern are checked.
            continue
        header_line = stripped_lines[1]
        closing_rule_present = any(set(ln) <= {'='} and len(ln) >= 10 for ln in stripped_lines[2:])
        if _BRACKET_HEADER_RE.match(header_line) and closing_rule_present:
            matching += 1
        else:
            violations.append(f"Docstring near header {header_line!r} does not close its rule properly")

    structural_total = matching + len(violations)
    detail = f"{structural_total} docstrings, {matching} match format" if structural_total else "0 structural docstrings found"
    return ConventionResult(4, "Docstring Format", len(violations) == 0, detail, violations)


def check_convention_5(tree: ast.Module) -> ConventionResult:
    """OPTION_NOTES Schema Compliance: every NOTES entry has all 7 required fields."""
    violations = []
    option_count = 0

    for name, _, dict_node in _module_level_dict_assigns(tree):
        if not name.endswith('_NOTES'):
            continue
        for key_node, value_node in zip(dict_node.keys, dict_node.values):
            option_name = key_node.value if isinstance(key_node, ast.Constant) else '<?>'
            option_count += 1
            if not isinstance(value_node, ast.Dict):
                violations.append(f"{name}[{option_name!r}] is not a dict")
                continue
            present_fields = {
                k.value for k in value_node.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            }
            missing = [f for f in REQUIRED_OPTION_NOTE_FIELDS if f not in present_fields]
            if missing:
                violations.append(f"{name}[{option_name!r}] missing fields: {missing}")

            for k, v in zip(value_node.keys, value_node.values):
                if isinstance(k, ast.Constant) and k.value == 'semantic_role':
                    if isinstance(v, ast.Constant) and v.value not in VALID_SEMANTIC_ROLES:
                        violations.append(
                            f"{name}[{option_name!r}].semantic_role = {v.value!r} not in {sorted(VALID_SEMANTIC_ROLES)}"
                        )

    detail = f"{option_count} options, all schema-compliant" if not violations else f"{option_count} options, {len(violations)} violation(s)"
    return ConventionResult(5, "OPTION_NOTES Schema Compliance", len(violations) == 0, detail, violations)


def check_convention_6(tree: ast.Module) -> ConventionResult:
    """Imports and Top-Level Variables: imports and scalar context vars precede fragment dicts."""
    import_lines = [n.lineno for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    fragment_lines = [
        assign.lineno for name, assign, _ in _module_level_dict_assigns(tree)
        if not name.endswith('_NOTES')
    ]
    violations = []
    if import_lines and fragment_lines:
        if max(import_lines) > min(fragment_lines):
            violations.append("At least one import statement appears after the first fragment dict")
    return ConventionResult(6, "Imports and Top-Level Variables", len(violations) == 0,
                             "checked" if not violations else f"{len(violations)} violation(s)", violations)


def check_convention_7(tree: ast.Module) -> ConventionResult:
    """DEPLOYMENT_CONTEXT Required: top-level declaration with a valid value."""
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id == 'DEPLOYMENT_CONTEXT':
                value = node.value.value if isinstance(node.value, ast.Constant) else None
                valid = isinstance(value, str) and (
                    value in ('public', 'internal') or value.startswith('specific:')
                )
                detail = f'declared as "{value}"'
                violations = [] if valid else [f"DEPLOYMENT_CONTEXT value {value!r} is not public/internal/specific:*"]
                return ConventionResult(7, "DEPLOYMENT_CONTEXT Required", valid, detail, violations)
    return ConventionResult(7, "DEPLOYMENT_CONTEXT Required", False,
                             "not declared — defaults to public Vanilla per spec, but explicit declaration required",
                             ["DEPLOYMENT_CONTEXT not found at module level"])


def check_convention_8(tree: ast.Module) -> ConventionResult:
    """Forward-Integration Hooks Documented: closing docstring lists future integrations."""
    hook_lines = []
    for _, text in _module_level_docstring_exprs(tree):
        if re.search(r'future integrations', text, re.IGNORECASE):
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith('- '):
                    hook_lines.append(stripped[2:])
    passed = len(hook_lines) > 0
    detail = f"{len(hook_lines)} hooks documented" if passed else "no 'future integrations' bullet list found"
    return ConventionResult(8, "Forward-Integration Hooks", passed, detail,
                             [] if passed else ["No docstring contains a 'future integrations' bullet list"])


def validate(path: Path) -> ValidationReport:
    source = path.read_text(encoding='utf-8')
    tree = ast.parse(source, filename=str(path))

    results = [
        check_convention_1(source, tree),
        check_convention_2(tree),
        check_convention_3(source),
        check_convention_4(tree),
        check_convention_5(tree),
        check_convention_6(tree),
        check_convention_7(tree),
        check_convention_8(tree),
    ]
    return ValidationReport(path=str(path), results=results)


def main(argv: Optional[List[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 1:
        print("Usage: menucode_validate.py <path/to/file.py>", file=sys.stderr)
        return 2

    path = Path(argv[0])
    if not path.is_file():
        print(f"error: {path} is not a file", file=sys.stderr)
        return 2

    report = validate(path)
    print(report.render())
    return 0 if report.all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
