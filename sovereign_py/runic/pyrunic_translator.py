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

Also carries the full multiscript layer — all four Runic scripts, not just
Futhark — pulled from runic-language-system sub-skill E (Greek, Hiragana)
and the Helix Codex Stages 5-12 (Cuneiform/Sumerian, the fourth script):
  - GrRu (Greek):     24 letters, math meaning + separate QRen payload-class
                       register. Math meaning is never redefined, only
                       contextually extended.
  - HiRu (Hiragana):  46 characters, process-flow meaning. Upstream status
                       is PROPOSED (OQ-RLS-005), carried here as-is.
  - CuRu (Cuneiform)  in SuRu (Sumerian) mode: 9 test glyphs (Helix Stage 5
                       Section XXVII's 8 + Stage 7's 𒁕 empty-slot addition).
                       Mark's "test build" status, not a finalized catalog —
                       represented honestly as such, not silently promoted.
  MultiscriptComposer implements the cross-script grammar: UniversalRune
  composition ((FuRu)(GrRu)(HiRu)) and the CuRu-leading script-mode
  declaration ((FuRu)? CuRu+ target) that Helix Stage 12 settled on,
  superseding an earlier FuRu-leading proposal from Stage 11.
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

    # --- Script 2 of 4: GREEK (GrRu) -------------------------------------
    # Complete 24-letter Greek alphabet, per runic-language-system sub-skill
    # E-01. Two separate semantic registers, never conflated: the standard
    # mathematical meaning (which a Greek letter must NEVER lose — extension
    # is contextual, not redefinitional) and the QRen inner-ring payload-class
    # role (a distinct register, active only inside QRen annotation context).
    GREEK: Dict[str, str] = {
        'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'delta': 'δ', 'epsilon': 'ε',
        'zeta': 'ζ', 'eta': 'η', 'theta': 'θ', 'iota': 'ι', 'kappa': 'κ',
        'lambda': 'λ', 'mu': 'μ', 'nu': 'ν', 'xi': 'ξ', 'omicron': 'ο',
        'pi': 'π', 'rho': 'ρ', 'sigma': 'σ', 'tau': 'τ', 'upsilon': 'υ',
        'phi': 'φ', 'chi': 'χ', 'psi': 'ψ', 'omega': 'ω',
    }

    GREEK_MATH_MEANING: Dict[str, str] = {
        'α': 'angles, coefficients, alpha particles', 'β': 'angles, coefficients, beta decay',
        'γ': 'Euler-Mascheroni constant, gamma function', 'δ': 'change (Δ), infinitesimal (δ), Kronecker delta',
        'ε': 'arbitrarily small positive quantity', 'ζ': 'Riemann zeta function, damping ratio',
        'η': 'efficiency, viscosity, conformal time', 'θ': 'angles, big-Theta notation',
        'ι': 'subscript index', 'κ': 'curvature, conductivity',
        'λ': 'eigenvalues, wavelength', 'μ': 'mean, micro-prefix',
        'ν': 'frequency, kinematic viscosity', 'ξ': 'random variable',
        'ο': 'variable', 'π': '3.14159..., circular constant',
        'ρ': 'density, correlation', 'σ': 'standard deviation, summation',
        'τ': 'torque, time constant', 'υ': 'rapidity (physics)',
        'φ': 'golden ratio, phase angle', 'χ': 'chi-squared statistic',
        'ψ': 'wave function', 'ω': 'angular frequency, last',
    }

    # QRen inner-ring payload class (separate register from GREEK_MATH_MEANING;
    # active only inside QRen magic-circle annotation, not admathCircle).
    GREEK_QREN_PAYLOAD_CLASS: Dict[str, str] = {
        'α': 'URL / address / direct reference', 'β': 'binary / executable content',
        'γ': 'structured data (JSON, YAML, config)', 'δ': 'change record / version delta',
        'ε': 'entity / identity payload', 'ζ': 'network / distributed topology',
        'η': 'ML model / weights / training data', 'θ': 'mathematical / geometric computation',
        'ι': 'identity metadata / Runic index', 'κ': 'cache / memory snapshot',
        'λ': 'logic / function / script', 'μ': 'manifest / structural map',
        'ν': 'narrative / persona / creative', 'ξ': 'cross-reference / external link',
        'ο': 'opcode / QRVM instruction', 'π': 'persistent archive / sealed state',
    }

    # --- Script 3 of 4: HIRAGANA (HiRu) -----------------------------------
    # 46 base characters, per runic-language-system sub-skill E-02. Defines
    # HOW a process BEHAVES (state transitions, flow control, temporal
    # sequence) — distinct from Futhark (what it IS) and Greek (how it
    # COMPUTES). Status inherited from source: PROPOSED, not yet Stage-3
    # finalized in the Runic Language System's own tracking (OQ-RLS-005) —
    # carried here as-is rather than silently promoted to settled canon.
    HIRAGANA: Dict[str, str] = {
        'a': 'あ', 'i': 'い', 'u': 'う', 'e': 'え', 'o': 'お',
        'ka': 'か', 'ki': 'き', 'ku': 'く', 'ke': 'け', 'ko': 'こ',
        'sa': 'さ', 'shi': 'し', 'su': 'す', 'se': 'せ', 'so': 'そ',
        'ta': 'た', 'chi': 'ち', 'tsu': 'つ', 'te': 'て', 'to': 'と',
        'na': 'な', 'ni': 'に', 'nu': 'ぬ', 'ne': 'ね', 'no': 'の',
        'ha': 'は', 'hi': 'ひ', 'fu': 'ふ', 'he': 'へ', 'ho': 'ほ',
        'ma': 'ま', 'mi': 'み', 'mu': 'む', 'me': 'め', 'mo': 'も',
        'ya': 'や', 'yu': 'ゆ', 'yo': 'よ',
        'ra': 'ら', 'ri': 'り', 'ru': 'る', 're': 'れ', 'ro': 'ろ',
        'wa': 'わ', 'wo': 'を', 'n': 'ん',
    }

    HIRAGANA_MEANING: Dict[str, str] = {
        'あ': 'start / initiation', 'い': 'input / receive', 'う': 'processing / transform',
        'え': 'evaluate / check', 'お': 'output / emit',
        'か': 'cache / store', 'き': 'key / trigger', 'く': 'queue / buffer',
        'け': 'condition / predicate', 'こ': 'commit / finalize',
        'さ': 'start sequence', 'し': 'shift / transition', 'す': 'suspend / pause',
        'せ': 'sequence / order', 'そ': 'sort / arrange',
        'た': 'task / job', 'ち': 'check / validate', 'つ': 'accumulate / collect',
        'て': 'test / probe', 'と': 'transfer / move',
        'な': 'navigate / route', 'に': 'notify / signal', 'ぬ': 'null / void',
        'ね': 'nest / embed', 'の': 'node / point',
        'は': 'handle / process', 'ひ': 'iterate / repeat', 'ふ': 'filter / select',
        'へ': 'halt / stop', 'ほ': 'hold / maintain',
        'ま': 'map / associate', 'み': 'merge / combine', 'む': 'mutate / modify',
        'め': 'measure / quantify', 'も': 'monitor / watch',
        'や': 'yield / produce', 'ゆ': 'union / join', 'よ': 'call / invoke',
        'ら': 'read / fetch', 'り': 'release / free', 'る': 'run / execute',
        'れ': 'return / respond', 'ろ': 'roll back / undo',
        'わ': 'wait / delay', 'を': 'write / persist', 'ん': 'end marker / null',
    }

    # --- Script 4 of 4: CUNEIFORM (CuRu) in Sumerian mode (SuRu) ----------
    # The fourth Runic script, per Helix Codex Stage 5 Section XXVII (test
    # build) through Stage 7 Section XXXVI (empty-slot glyph added, mode
    # confirmed as Greek-supplement not replacement) through Stage 11-12
    # (CuRu/SuRu shorthand canonized; CuRu-leading script-mode-declaration
    # grammar settled, superseding an earlier FuRu-leading proposal).
    #
    # CuRu = the glyph itself. SuRu = the semantic mode those glyphs carry
    # here (foundational / archaeological / precision-by-discipline) — the
    # same script-vs-mode separation as "Futhark glyphs in ontological mode".
    #
    # Honesty note: this is Mark's "test build" status, not a finalized
    # 25-40 glyph catalog (that expansion was deferred to a later stage).
    # Nine glyphs: the original 8-glyph test set plus BAD, added when the
    # empty-slot need was identified.
    CUNEIFORM: Dict[str, str] = {
        'dingir': '𒀭', 'en': '𒂗', 'ki': '𒆠', 'ka': '𒅗', 'me': '𒈨',
        'e': '𒂊', 'shu': '𒋗', 'nig': '𒁁', 'bad': '𒁕',
    }

    CUNEIFORM_SUMERIAN_MEANING: Dict[str, str] = {
        '𒀭': 'foundational designation (DINGIR: god/divine/sky) — also the script-mode declaration leader',
        '𒂗': 'canonical-status declaration (EN: lord/authority/canonical)',
        '𒆠': 'residency/location anchor (KI: earth/ground/place)',
        '𒅗': 'declaration speech-act (KA: mouth/speech/utterance)',
        '𒈨': 'invariant principle — CASL-floor invariants (ME: divine power/ordinance)',
        '𒂊': 'flow-through declaration (E: water/canal/flow)',
        '𒋗': 'agent-acting designation (ŠU: hand/agent/doer)',
        '𒁁': 'concrete-substance designation (NÍG: thing/matter/substance)',
        '𒁕': 'intentional emptiness — the empty-slot glyph (BAD: empty/open/cleared); '
              'two operational forms: single annotation, or Circle-pair scope',
    }

    # Script-name -> mode-name shorthand pairs (Helix Stage 11 Section LI).
    # CuRu/SuRu is the odd one out: CuRu is glyph, SuRu is the mode it
    # carries here — same script/mode separation FuRu/GrRu/HiRu already have,
    # just made explicit because Cuneiform is new enough to need it spelled out.
    SCRIPT_SHORTHAND: Dict[str, str] = {
        'FuRu': 'Futhark Rune — Elder Futhark glyphs, ontological/identity mode',
        'GrRu': 'Greek Rune — Greek alphabet + admathRune operators, mathematical/logical mode',
        'HiRu': 'Hiragana Rune — Japanese hiragana glyphs, behavioral/process mode (proposed)',
        'CuRu': 'Cuneiform Rune — the glyph itself',
        'SuRu': 'Sumerian mode — CuRu glyphs interpreted in foundational/archaeological/precision register',
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
    def greek_letter(cls, name: str) -> Optional[str]:
        return cls.GREEK.get(name.lower())

    @classmethod
    def hiragana_char(cls, romaji: str) -> Optional[str]:
        return cls.HIRAGANA.get(romaji.lower())

    @classmethod
    def cuneiform_glyph(cls, name: str) -> Optional[str]:
        return cls.CUNEIFORM.get(name.lower())

    @classmethod
    def script_of(cls, glyph: str) -> Optional[str]:
        """Which of the four scripts (FuRu/GrRu/HiRu/CuRu) a glyph belongs to."""
        if glyph in cls.ARSTACK.values():
            return 'FuRu'
        if glyph in cls.GREEK.values():
            return 'GrRu'
        if glyph in cls.HIRAGANA.values():
            return 'HiRu'
        if glyph in cls.CUNEIFORM.values():
            return 'CuRu'
        return None

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
# MULTISCRIPT COMPOSITION (Futhark / Greek / Hiragana / Cuneiform)
# =============================================================================

class MultiscriptComposer:
    """
    Cross-script composition per runic-language-system sub-skill E-03
    (UniversalRune) and the Helix Codex Stage 5-12 script-mode-declaration
    grammar. Each of the four scripts carries one orthogonal register and
    none may be substituted for another:

        FuRu (Futhark)   -> what it IS      (structural identity)
        GrRu (Greek)     -> how it COMPUTES (mathematical form, never
                             redefined — only extended contextually)
        HiRu (Hiragana)  -> how it BEHAVES  (process sequence; proposed,
                             not yet Stage-3 finalized upstream)
        CuRu (Cuneiform) -> what persists   (foundational/archaeological/
                             precision substrate, in SuRu mode); Mark's
                             test-build status, not a finalized catalog
    """

    @staticmethod
    def universal_rune(futhark: str = '', greek: str = '', hiragana: str = '') -> str:
        """
        Compose a UniversalRune: ((FuRu)(GrRu)(HiRu)). Any component may be
        omitted; omitted registers are simply absent from the composition,
        not filled with a default.
        """
        parts = [p for p in (futhark, greek, hiragana) if p]
        return '(' + ')('.join(parts) + ')' if parts else '()'

    @staticmethod
    def script_mode_declaration(target: str, curu: str = '𒀭', furu: Optional[str] = None) -> str:
        """
        CuRu-leading script-mode declaration (Helix Stage 12 Section LIV;
        supersedes the earlier Stage 11 FuRu-leading proposal). Grammar:

            script_mode_declaration ::= (FuRu)? CuRu+ target

        `curu` defaults to 𒀭 (DINGIR) for basic Sumerian-mode declaration.
        Pass a doubled glyph (e.g. '𒀭𒀭') for "alternative-of-the-alternative".
        `furu` is an optional Futhark prefix that flavors *which* alternative
        is meant (e.g. ᚱ Raidho for a Root-semantic flavor of the alternative).
        """
        prefix = furu or ''
        return f"{prefix}{curu}({target})"

    @staticmethod
    def empty_slot(count: int = 1) -> str:
        """
        The 𒁕 (BAD) empty-slot glyph: intentional emptiness as first-class
        Circle content, not "missing data". Repeated for multi-position
        emptiness (Helix Stage 7 Section XXXVI).
        """
        return ' '.join(['𒁕'] * max(count, 1))

    @staticmethod
    def admath_circle(body: str, sumerian_mode: bool = False) -> str:
        """
        ᛟ○ ... ᛟ○0 (Greek mode, default) or 𒀭ᛟ○ ... 𒀭ᛟ○0 (Sumerian mode,
        precision arithmetic — base-60, supplementing rather than replacing
        Greek mode, per Helix Stage 7 Section XXXVI Specification 1).
        """
        prefix = '𒀭' if sumerian_mode else ''
        return f"{prefix}ᛟ○ {body} {prefix}ᛟ○0"


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
    multiscript = MultiscriptComposer

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

    print("\n" + "=" * 60)
    print("The four Runic scripts (FuRu / GrRu / HiRu / CuRu)")
    print("=" * 60)

    print(f"\n-- 1. FuRu (Futhark): {len(RunicSymbolTable.ARSTACK)} runes — see ARSTACK above --")

    print(f"\n-- 2. GrRu (Greek): {len(RunicSymbolTable.GREEK)} letters --")
    for name, sym in list(RunicSymbolTable.GREEK.items())[:5]:
        math = RunicSymbolTable.GREEK_MATH_MEANING.get(sym, '')
        qren = RunicSymbolTable.GREEK_QREN_PAYLOAD_CLASS.get(sym, '(no QRen role)')
        print(f"  {name:10} {sym}  math: {math}")
        print(f"  {'':10} {' '}  QRen: {qren}")
    print(f"  ... ({len(RunicSymbolTable.GREEK) - 5} more)")

    print(f"\n-- 3. HiRu (Hiragana): {len(RunicSymbolTable.HIRAGANA)} characters (PROPOSED, not Stage-3 finalized) --")
    for romaji, sym in list(RunicSymbolTable.HIRAGANA.items())[:5]:
        print(f"  {romaji:10} {sym}  {RunicSymbolTable.HIRAGANA_MEANING.get(sym, '')}")
    print(f"  ... ({len(RunicSymbolTable.HIRAGANA) - 5} more)")

    print(f"\n-- 4. CuRu (Cuneiform) in SuRu mode: {len(RunicSymbolTable.CUNEIFORM)} test glyphs (Mark's test-build status) --")
    for name, sym in RunicSymbolTable.CUNEIFORM.items():
        print(f"  {name:10} {sym}  {RunicSymbolTable.CUNEIFORM_SUMERIAN_MEANING.get(sym, '')}")

    print("\n-- Script shorthand registry --")
    for shorthand, meaning in RunicSymbolTable.SCRIPT_SHORTHAND.items():
        print(f"  {shorthand:6} {meaning}")

    print("\n-- MultiscriptComposer: UniversalRune composition (e_03_skill.md examples) --")
    print("  " + MultiscriptComposer.universal_rune('ᚠα', '', 'あ') + "  (primary variable flow initiator)")
    print("  " + MultiscriptComposer.universal_rune('ᛟψ', '', 'る') + "  (execute advanced wave function computation)")
    print("  " + MultiscriptComposer.universal_rune('ᚨδ', '', 'む') + "  (AI-driven adaptive modification)")

    print("\n-- MultiscriptComposer: script-mode declaration (Helix Stage 12 Section LIV) --")
    print("  " + MultiscriptComposer.script_mode_declaration('target_rune') + "  (basic SuRu-mode declaration)")
    print("  " + MultiscriptComposer.script_mode_declaration('target_rune', furu='ᚱ') + "  (Root-flavored)")
    print("  " + MultiscriptComposer.script_mode_declaration('target_rune', curu='𒀭𒀭') + "  (alternative-of-the-alternative)")
    print("  " + MultiscriptComposer.admath_circle('computation_using_base_60_arithmetic', sumerian_mode=True))

    print("\n-- MultiscriptComposer: empty-slot glyph --")
    print("  " + MultiscriptComposer.empty_slot(3) + "  (three deliberately empty Circle positions)")

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
          f"{len(RunicSymbolTable.ARSTACK)} FuRu + "
          f"{len(RunicSymbolTable.GREEK)} GrRu + "
          f"{len(RunicSymbolTable.HIRAGANA)} HiRu + "
          f"{len(RunicSymbolTable.CUNEIFORM)} CuRu + "
          f"{KeywordTranslator.coverage()} keywords/builtins")
    print("=" * 60)


if __name__ == '__main__':
    _run_diagnostics()
