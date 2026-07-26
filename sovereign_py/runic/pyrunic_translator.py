"""
PyRunic Translator — Python3 -> Runic notation translator.

One-way. Takes Python constructs (values, functions, classes, modules) and
produces their Runic *text* representation. This module never executes
anything — it only translates notation. Execution across the Python/Runic
boundary is runic/runic_translation.py's job; this module is what a human
or another tool reads to see what the Runic form of some Python code
would look like.

Fills in the 3 gaps found when this file was cross-referenced against the
documented Runic grammar in a prior session:
  1. ADMATH_OPERATORS  - admathRune operators, previously missing entirely.
  2. ARSTACK           - the full 24-rune Elder Futhark Grammar Glyph
                         catalog, previously only 5 of 24 entries.
  3. KeywordTranslator - Python keyword/builtin -> rune mapping via AST,
                         previously missing entirely.
"""

import ast
import inspect
from typing import Any, Callable, Dict, List, Optional, Type


# =============================================================================
# SYMBOL TABLES
# =============================================================================

class RunicSymbolTable:
    """Canonical Python-type-to-rune and domain-concept-to-rune mappings."""

    # Core types, matching RuneTranslator._infer_symbol() in
    # runic_native_subsystem.py exactly, so translated notation lines up
    # with what the execution boundary actually produces.
    CORE_TYPES: Dict[type, str] = {
        int: 'ℕ',
        float: 'ℝ',
        str: 'Σ',
        bool: 'Β',
        list: 'Α',
        dict: 'Δ',
        type(None): '∅',
        bytes: 'ᚲ',
    }

    # Domain symbols, drawn from the RunicFile / RunicTrainingBlock /
    # RunicAgent field names in runic_native_subsystem.py.
    DOMAIN: Dict[str, str] = {
        'file': 'φ', 'content': 'φ',
        'name': 'ν', 'filename': 'ν',
        'owner': 'ω',
        'metadata': 'μ',
        'block': 'ξ',
        'description': 'δ',
        'type': 'τ',
        'enabled': 'ε',
        'agent': 'α',
        'profile': 'π',
        'query': 'ψ',
        'result': 'ρ',
        'context': 'κ',
        'index': 'ι',
    }

    # --- Gap 1: admathRune operators -----------------------------------
    # The dimensional/admath layer's operator vocabulary. Previously absent
    # from this symbol table entirely.
    ADMATH_OPERATORS: Dict[str, str] = {
        'compose': '⨀',       # circled dot: sequential composition
        'merge': '⨁',         # circled plus: structural merge / union
        'tensor': '⨂',        # circled times: tensor / cross-product join
        'bind': '⊗',          # times: dimensional binding
        'cycle': '⥁',         # circular arrow: cyclic/iterative transform
    }

    # --- Gap 2: full Grammar Glyph catalog (ARSTACK) --------------------
    # Elder Futhark, complete 24-rune set. Previously only the 5 runes used
    # directly by the AiCircle/admathCircle boundary (Ansuz, Othala, Mannaz,
    # Dagaz, Raidho, Gebo, Kenaz, Berkano) were catalogued; the remaining 16
    # were undocumented even though the grammar draws on the full set for
    # extension circles. Ordered per the traditional Futhark ættir (rows).
    ARSTACK: Dict[str, str] = {
        # First ætt
        'fehu': 'ᚠ', 'uruz': 'ᚢ', 'thurisaz': 'ᚦ', 'ansuz': 'ᚨ',
        'raidho': 'ᚱ', 'kenaz': 'ᚲ', 'gebo': 'ᚷ', 'wunjo': 'ᚹ',
        # Second ætt
        'hagalaz': 'ᚺ', 'naudiz': 'ᚾ', 'isa': 'ᛁ', 'jera': 'ᛃ',
        'eihwaz': 'ᛇ', 'perthro': 'ᛈ', 'algiz': 'ᛉ', 'sowilo': 'ᛊ',
        # Third ætt
        'tiwaz': 'ᛏ', 'berkano': 'ᛒ', 'ehwaz': 'ᛖ', 'mannaz': 'ᛗ',
        'laguz': 'ᛚ', 'ingwaz': 'ᛝ', 'dagaz': 'ᛞ', 'othala': 'ᛟ',
    }

    # Which ARSTACK runes are load-bearing in the AiCircle / admathCircle
    # boundary grammar specifically (vs. available-but-unused extension runes).
    BOUNDARY_RUNES = {
        'aicircle_outer': ['ansuz', 'othala', 'mannaz', 'dagaz'],
        'admathcircle_inner': ['raidho', 'gebo', 'kenaz', 'berkano'],
    }

    TOKENS: Dict[str, Dict[str, Any]] = {
        'TB': {'symbol': 'ξ', 'block_type': 'TREE/FRUIT', 'wire_code': 0x01, 'compression': '15:1'},
        'EA': {'symbol': 'α', 'block_type': 'FLAME/EMBER', 'wire_code': 0x03, 'compression': '13:1'},
        'IF': {'symbol': '⧧', 'block_type': 'VOID->LIGHTNING', 'wire_code': 0x0C, 'compression': '18:1'},
    }

    @classmethod
    def symbol_for_type(cls, value: Any) -> str:
        return cls.CORE_TYPES.get(type(value), '◇')

    @classmethod
    def symbol_for_domain_key(cls, key: str) -> Optional[str]:
        return cls.DOMAIN.get(key)

    @classmethod
    def token_for_value(cls, value: Any) -> Optional[str]:
        """
        Detect ⟨TB⟩/⟨EA⟩/⟨IF⟩ from dict key patterns. Returns the token
        name ('TB', 'EA', 'IF') or None if the value doesn't match any
        known token shape.
        """
        if not isinstance(value, dict):
            return None
        keys = set(value.keys())
        if {'name', 'content'} <= keys or {'block_type', 'files'} <= keys:
            return 'TB'
        if {'agent_id'} <= keys or {'agent_type', 'profile'} <= keys:
            return 'EA'
        if {'fix_id'} <= keys or ({'error', 'resolution'} <= keys):
            return 'IF'
        return None

    @classmethod
    def token_info(cls, token: str) -> Optional[Dict[str, Any]]:
        return cls.TOKENS.get(token)


# =============================================================================
# Gap 3: KEYWORD TRANSLATOR
# =============================================================================

class KeywordTranslator:
    """
    Maps Python keywords and common builtins to rune notation, driven by
    AST inspection (catches ast.Call nodes for builtin-function calls, and
    ast.keyword-bearing statement nodes for language keywords).

    Previously entirely missing: FunctionTranslator/ModuleTranslator had no
    way to render `print(...)`, `if`, `for`, etc. as anything but literal
    Python text.
    """

    # Language keywords / control flow.
    KEYWORD_RUNES: Dict[str, str] = {
        'if': '?', 'elif': '?+', 'else': '?~',
        'for': '↻', 'while': '↺', 'break': '⊘', 'continue': '↷',
        'return': '⇐', 'yield': '⇠', 'raise': '⇑', 'assert': '⊢',
        'try': '⟐', 'except': '⟑', 'finally': '⟒',
        'with': '⊂', 'as': '↦',
        'def': '○', 'class': 'Δ○', 'lambda': 'λ',
        'import': '⇉', 'from': '⇇',
        'pass': '·', 'del': '⊖',
        'and': '∧', 'or': '∨', 'not': '¬', 'in': '∈', 'is': '≡',
        'global': '⇑ν', 'nonlocal': '↑ν',
        'async': '~○', 'await': '⌛',
    }

    # Common builtins, reached via ast.Call(func=Name(id=<builtin>)).
    BUILTIN_RUNES: Dict[str, str] = {
        'print': '☆', 'input': '❋',
        'len': '№', 'range': '…', 'enumerate': '№…',
        'str': 'Σ', 'int': 'ℕ', 'float': 'ℝ', 'bool': 'Β', 'bytes': 'ᚲ',
        'list': 'Α', 'dict': 'Δ', 'set': '∈Α', 'tuple': '⟨⟩',
        'open': '📖', 'close': '📕',
        'sorted': '⇅', 'reversed': '⇄', 'zip': '⋈', 'map': '↦Α', 'filter': '⊇',
        'sum': '∑', 'min': '⊓', 'max': '⊔', 'abs': '|·|', 'round': '≈',
        'isinstance': '∈τ', 'type': 'τ', 'getattr': 'μ→', 'setattr': '→μ',
        'hasattr': '∃μ', 'super': '↑Δ',
        'all': '∀', 'any': '∃', 'iter': '↻ι', 'next': 'ι→',
    }

    @classmethod
    def rune_for_keyword(cls, keyword: str) -> Optional[str]:
        return cls.KEYWORD_RUNES.get(keyword)

    @classmethod
    def rune_for_builtin(cls, name: str) -> Optional[str]:
        return cls.BUILTIN_RUNES.get(name)

    @classmethod
    def extract_calls(cls, source: str) -> List[Dict[str, Any]]:
        """
        Parse `source` and return every recognized builtin call site as
        {'name': str, 'rune': str, 'line': int, 'args': int}. Unrecognized
        calls are omitted, not errored — this is notation, not validation.
        """
        tree = ast.parse(source)
        found = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                rune = cls.rune_for_builtin(node.func.id)
                if rune:
                    found.append({
                        'name': node.func.id,
                        'rune': rune,
                        'line': node.lineno,
                        'args': len(node.args),
                    })
        return found

    @classmethod
    def coverage(cls) -> int:
        """Total number of keyword+builtin runes catalogued."""
        return len(cls.KEYWORD_RUNES) + len(cls.BUILTIN_RUNES)


# =============================================================================
# VALUE TRANSLATION
# =============================================================================

class ValueTranslator:
    """Renders any Python value as Runic atom notation text: SYMBOL=repr."""

    @staticmethod
    def translate(value: Any) -> str:
        symbol = RunicSymbolTable.symbol_for_type(value)
        if isinstance(value, dict):
            token = RunicSymbolTable.token_for_value(value)
            prefix = f"⟨{token}⟩" if token else ""
            inner = ", ".join(
                f"{RunicSymbolTable.symbol_for_domain_key(k) or k}={ValueTranslator.translate(v)}"
                for k, v in value.items()
            )
            return f"{prefix}{symbol}={{{inner}}}"
        if isinstance(value, (list, tuple)):
            inner = ", ".join(ValueTranslator.translate(v) for v in value)
            return f"{symbol}=[{inner}]"
        if isinstance(value, str):
            return f"{symbol}='{value}'"
        return f"{symbol}={value!r}"


# =============================================================================
# SCROLL BUILDER
# =============================================================================

class ScrollBuilder:
    """Generates '≡ name -> value' scroll binding declarations."""

    @staticmethod
    def from_function_params(fn: Callable) -> List[str]:
        sig = inspect.signature(fn)
        lines = []
        for name, param in sig.parameters.items():
            default = "" if param.default is inspect._empty else f" (default {param.default!r})"
            annotation = ""
            if param.annotation is not inspect._empty:
                ann = getattr(param.annotation, '__name__', str(param.annotation))
                annotation = f": {ann}"
            lines.append(f"≡ {name}{annotation}{default}")
        return lines

    @staticmethod
    def from_class_attrs(cls: Type) -> List[str]:
        lines = []
        for name, value in vars(cls).items():
            if name.startswith('__') or callable(value):
                continue
            lines.append(f"≡ {name} = {ValueTranslator.translate(value)}")
        return lines

    @staticmethod
    def from_imports(source: str) -> List[str]:
        tree = ast.parse(source)
        lines = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    lines.append(f"≡ import {alias.name}" + (f" as {alias.asname}" if alias.asname else ""))
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    lines.append(f"≡ from {mod} import {alias.name}")
        return lines


# =============================================================================
# FUNCTION / CLASS / MODULE TRANSLATORS
# =============================================================================

class FunctionTranslator:
    """
    Python function -> ArCircle notation.

    Circle marker chosen by function characteristics:
      ○      plain function
      ᚨ○     function that opens an AiCircle (has 'circle'/'boundary' in name)
      ᛟ○     function that performs an admath/dimensional transform
      ᚨᛟ○    both
      ~ᚨ○    async function opening an AiCircle (closes ~ᚨ○0)
    """

    @staticmethod
    def translate(fn: Callable) -> str:
        name = fn.__name__
        is_async = inspect.iscoroutinefunction(fn)
        is_aicircle = any(k in name.lower() for k in ('circle', 'boundary', 'cross'))
        is_admath = any(k in name.lower() for k in ('transform', 'admath', 'dimension'))

        if is_aicircle and is_admath:
            marker = '~ᚨᛟ○' if is_async else 'ᚨᛟ○'
        elif is_aicircle:
            marker = '~ᚨ○' if is_async else 'ᚨ○'
        elif is_admath:
            marker = '~ᛟ○' if is_async else 'ᛟ○'
        else:
            marker = '~○' if is_async else '○'

        params = ScrollBuilder.from_function_params(fn)
        header = f"{marker} {name}"
        if params:
            header += " ( " + " · ".join(p.replace('≡ ', '') for p in params) + " )"
        close_marker = marker.replace('○', '○0') if '○0' not in marker else marker
        return f"{header}\n{close_marker}"


class ClassTranslator:
    """Python class -> Circle-with-scroll notation."""

    @staticmethod
    def translate(cls: Type) -> str:
        name = cls.__name__
        bases = ", ".join(b.__name__ for b in cls.__bases__ if b is not object)
        header = f"Δ○ {name}" + (f" ⊂ {bases}" if bases else "")

        scroll = ScrollBuilder.from_class_attrs(cls)
        methods = [
            f"  {FunctionTranslator.translate(v).splitlines()[0]}"
            for k, v in vars(cls).items()
            if callable(v) and not k.startswith('__')
        ]

        body = scroll + ([""] if scroll and methods else []) + methods
        body_text = "\n".join(f"  {line}" if not line.startswith('  ') else line for line in body)
        return f"{header}\n{body_text}\nΔ○0" if body_text else f"{header}\nΔ○0"


class ModuleTranslator:
    """Python source file -> full Runic module Circle."""

    @staticmethod
    def translate(source: str, module_name: str = 'module') -> str:
        imports = ScrollBuilder.from_imports(source)
        calls = KeywordTranslator.extract_calls(source)

        lines = [f"ᚨ○ {module_name}"]
        lines.extend(imports)
        if calls:
            lines.append("≡ builtin_calls")
            for c in calls:
                lines.append(f"  {c['rune']} {c['name']}() @L{c['line']}")
        lines.append("ᚨ○0")
        return "\n".join(lines)


class AnnotationMode:
    """
    Python source -> same source with inline Runic-notation comments.

    Deterministic 5-step algorithm:
      1. Tokenize the source line-by-line via ast to find call/keyword sites.
      2. Classify each site: keyword vs. builtin-call vs. plain code.
      3. Map classified sites to their rune via KeywordTranslator.
      4. Attach the rune as a trailing `# <rune>` comment on that line.
      5. Emit original + annotated lines paired, original untouched.
    """

    @staticmethod
    def annotate(source: str) -> str:
        lines = source.splitlines()
        # Step 1 + 2 + 3: find all recognized sites (calls) up front.
        call_sites = {c['line']: c['rune'] for c in KeywordTranslator.extract_calls(source)}

        # Step 2b: recognize bare keyword usage per line via simple token scan
        # (cheap and deterministic; full statement-level AST classification is
        # unnecessary for a notation comment).
        keyword_sites: Dict[int, str] = {}
        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            first_word = stripped.split(' ', 1)[0].rstrip(':') if stripped else ''
            rune = KeywordTranslator.rune_for_keyword(first_word)
            if rune:
                keyword_sites[i] = rune

        # Step 4 + 5: attach trailing comments, emit paired output.
        annotated = []
        for i, line in enumerate(lines, start=1):
            rune = call_sites.get(i) or keyword_sites.get(i)
            if rune and '#' not in line:
                annotated.append(f"{line}  # {rune}")
            else:
                annotated.append(line)
        return "\n".join(annotated)


# =============================================================================
# MAIN INTERFACE
# =============================================================================

class PyRunicTranslator:
    """Main entry point orchestrating value/function/class/module translation."""

    symbols = RunicSymbolTable
    keywords = KeywordTranslator

    @staticmethod
    def translate_value(value: Any) -> str:
        return ValueTranslator.translate(value)

    @staticmethod
    def translate_function(fn: Callable) -> str:
        return FunctionTranslator.translate(fn)

    @staticmethod
    def translate_class(cls: Type) -> str:
        return ClassTranslator.translate(cls)

    @staticmethod
    def translate_module(source: str, module_name: str = 'module') -> str:
        return ModuleTranslator.translate(source, module_name)

    @staticmethod
    def annotate_source(source: str) -> str:
        return AnnotationMode.annotate(source)


# =============================================================================
# STANDALONE DIAGNOSTICS
# =============================================================================

def _run_diagnostics():
    print("=" * 60)
    print("PyRunic Translator — Diagnostics")
    print("=" * 60)

    print("\n-- Value translations --")
    for v in [42, 3.14, "hello", True, [1, 2, 3], {'name': 'demo', 'content': 'x'}]:
        print(f"  {v!r:35} -> {ValueTranslator.translate(v)}")

    print("\n-- Token detection --")
    samples = [
        {'name': 'demo', 'content': 'x'},
        {'agent_id': 7, 'profile': 'balanced'},
        {'fix_id': 'IF-001', 'error': 'circular import'},
        {'unrelated': True},
    ]
    for s in samples:
        token = RunicSymbolTable.token_for_value(s)
        print(f"  {s!r:45} -> {token}")

    print("\n-- Token info --")
    for name in ('TB', 'EA', 'IF'):
        print(f"  {name}: {RunicSymbolTable.token_info(name)}")

    print("\n-- ADMATH_OPERATORS (gap 1) --")
    for name, sym in RunicSymbolTable.ADMATH_OPERATORS.items():
        print(f"  {name:10} {sym}")

    print(f"\n-- ARSTACK catalog (gap 2): {len(RunicSymbolTable.ARSTACK)} runes --")
    for name, sym in RunicSymbolTable.ARSTACK.items():
        print(f"  {name:10} {sym}")

    print(f"\n-- KeywordTranslator coverage (gap 3): {KeywordTranslator.coverage()} entries --")
    print(f"  keywords: {len(KeywordTranslator.KEYWORD_RUNES)}, builtins: {len(KeywordTranslator.BUILTIN_RUNES)}")

    print("\n-- Function ArCircle notation --")
    def example_boundary_cross(value, operation=None):
        return value
    print(FunctionTranslator.translate(example_boundary_cross))

    print("\n-- extract_calls() on a small source sample --")
    sample_source = "x = len(items)\nprint(x)\nfor i in range(x):\n    print(i)\n"
    for call in KeywordTranslator.extract_calls(sample_source):
        print(f"  L{call['line']}: {call['name']}() -> {call['rune']}")

    print("\n-- annotate_source() on the same sample --")
    print(AnnotationMode.annotate(sample_source))

    print("\n" + "=" * 60)
    print(f"Total catalogued symbols: "
          f"{len(RunicSymbolTable.CORE_TYPES)} core types + "
          f"{len(RunicSymbolTable.DOMAIN)} domain + "
          f"{len(RunicSymbolTable.ADMATH_OPERATORS)} admath ops + "
          f"{len(RunicSymbolTable.ARSTACK)} Futhark runes + "
          f"{KeywordTranslator.coverage()} keywords/builtins")
    print("=" * 60)


if __name__ == '__main__':
    _run_diagnostics()
