"""
L2 — Ingestion Layer (AiDEA-style extraction).

"Receives artifact event records from L1, extracts content via AiDEA,
classifies artifacts by type and tier, and routes the structured output to
the ML Process Factory. It is the translation layer between raw filesystem
content and the tier-aware process factory." (spec Section 4.1)

AiDEA's real design constraint carried over here: stdlib-only, no external
parser dependencies, safe under tight memory (streams/limits rather than
loading everything). L2 extracts and classifies; it does not build
processes (L3) or store anything (L4).
"""

import ast
import configparser
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- Artifact type classification (spec Section 4.3) -----------------------

SOURCE_CODE_SUFFIXES = {'.py', '.rs', '.c', '.js', '.ts', '.sh'}
DOCUMENTATION_SUFFIXES = {'.md', '.rst', '.txt'}
CONFIG_SUFFIXES = {'.toml', '.yaml', '.yml', '.json', '.ini', '.cfg'}
NOTEBOOK_SUFFIXES = {'.ipynb'}
BINARY_MEDIA_SUFFIXES = {'.png', '.jpg', '.jpeg', '.gif', '.pdf', '.mp4', '.mp3', '.wav', '.ico'}


@dataclass
class ExtractedUnit:
    """One semantic unit within an artifact (a docstring, a heading+body, a key-value pair, ...)."""
    unit_type: str
    label: str
    text: str


@dataclass
class ExtractionResult:
    path: Path
    artifact_type: str          # source_code | documentation | word_document | skill_capsule |
                                 # index_file | config | notebook | binary_media | unknown
    extraction_approach: str
    units: List[ExtractedUnit] = field(default_factory=list)
    full_text: str = ''         # concatenated text used for chunking/RAG
    metadata: Dict[str, Any] = field(default_factory=dict)


def classify_artifact_type(path: Path) -> str:
    name = path.name
    suffix = path.suffix.lower()

    if name in ('SKILL.md', 'PseudoSKILL.md') or suffix == '.skill':
        return 'skill_capsule'
    if name == 'MASTER_INDEX.md' or name.endswith('.INDEX.md'):
        return 'index_file'
    if suffix == '.docx':
        return 'word_document'
    if suffix in NOTEBOOK_SUFFIXES:
        return 'notebook'
    if suffix in SOURCE_CODE_SUFFIXES:
        return 'source_code'
    if suffix in DOCUMENTATION_SUFFIXES or name.upper().startswith('README'):
        return 'documentation'
    if suffix in CONFIG_SUFFIXES:
        return 'config'
    if suffix in BINARY_MEDIA_SUFFIXES:
        return 'binary_media'
    return 'unknown'


# --- Extractors --------------------------------------------------------

def extract_source_code(path: Path, text: str) -> ExtractionResult:
    units: List[ExtractedUnit] = []
    approach = 'full_text'

    if path.suffix == '.py':
        try:
            tree = ast.parse(text, filename=str(path))
            approach = 'ast'
            mod_doc = ast.get_docstring(tree)
            if mod_doc:
                units.append(ExtractedUnit('docstring', 'module', mod_doc))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    sig = f"{'async ' if isinstance(node, ast.AsyncFunctionDef) else ''}def {node.name}(" \
                          f"{', '.join(a.arg for a in node.args.args)})"
                    units.append(ExtractedUnit('signature', node.name, sig))
                    doc = ast.get_docstring(node)
                    if doc:
                        units.append(ExtractedUnit('docstring', node.name, doc))
                elif isinstance(node, ast.ClassDef):
                    units.append(ExtractedUnit('signature', node.name, f"class {node.name}"))
                    doc = ast.get_docstring(node)
                    if doc:
                        units.append(ExtractedUnit('docstring', node.name, doc))
        except SyntaxError:
            approach = 'full_text'

    if approach == 'full_text' or not units:
        # Comments as a distinct unit even when AST parsing succeeded, since
        # ast doesn't retain them.
        comments = [line.strip() for line in text.splitlines() if line.strip().startswith('#')]
        if comments:
            units.append(ExtractedUnit('comments', 'file', '\n'.join(comments[:50])))

    return ExtractionResult(
        path=path, artifact_type='source_code', extraction_approach=approach,
        units=units, full_text=text,
        metadata={'line_count': text.count('\n') + 1},
    )


_HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)$')
_CODE_FENCE_RE = re.compile(r'^```')


def extract_documentation(path: Path, text: str) -> ExtractionResult:
    units: List[ExtractedUnit] = []
    current_heading = '(preamble)'
    buffer: List[str] = []
    in_code_block = False

    def flush():
        if buffer:
            units.append(ExtractedUnit('paragraph', current_heading, '\n'.join(buffer).strip()))
            buffer.clear()

    for line in text.splitlines():
        if _CODE_FENCE_RE.match(line):
            in_code_block = not in_code_block
            buffer.append(line)
            continue
        if not in_code_block:
            m = _HEADING_RE.match(line)
            if m:
                flush()
                current_heading = m.group(2).strip()
                continue
        buffer.append(line)
    flush()

    return ExtractionResult(
        path=path, artifact_type='documentation', extraction_approach='structural_parsing',
        units=units, full_text=text,
    )


def extract_word_document(path: Path) -> ExtractionResult:
    """Stdlib-only .docx extraction: unzip and pull text runs from word/document.xml,
    preserving heading hierarchy via the paragraph style name."""
    units: List[ExtractedUnit] = []
    full_text_parts = []
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read('word/document.xml').decode('utf-8', errors='replace')
    except (zipfile.BadZipFile, KeyError, OSError):
        return ExtractionResult(path=path, artifact_type='word_document', extraction_approach='failed', metadata={'error': 'unreadable'})

    for para_xml in re.split(r'</w:p>', xml):
        style_match = re.search(r'<w:pStyle w:val="([^"]*)"', para_xml)
        style = style_match.group(1) if style_match else 'Normal'
        texts = re.findall(r'<w:t[^>]*>(.*?)</w:t>', para_xml, re.DOTALL)
        text = ''.join(texts).strip()
        if not text:
            continue
        unit_type = 'heading' if style.lower().startswith('heading') else 'paragraph'
        units.append(ExtractedUnit(unit_type, style, text))
        full_text_parts.append(text)

    return ExtractionResult(
        path=path, artifact_type='word_document', extraction_approach='zipfile_xml',
        units=units, full_text='\n'.join(full_text_parts),
    )


def extract_skill_capsule(path: Path, text: str) -> ExtractionResult:
    """SKILL.md / PseudoSKILL.md: YAML frontmatter + body as typed units."""
    units: List[ExtractedUnit] = []
    frontmatter = {}
    body = text

    if text.startswith('---'):
        end = text.find('\n---', 3)
        if end != -1:
            fm_text = text[3:end].strip()
            body = text[end + 4:]
            for line in fm_text.splitlines():
                if ':' in line:
                    k, _, v = line.partition(':')
                    frontmatter[k.strip()] = v.strip().strip('"')
            units.append(ExtractedUnit('frontmatter', 'metadata', json.dumps(frontmatter)))

    doc_result = extract_documentation(path, body)
    units.extend(doc_result.units)

    return ExtractionResult(
        path=path, artifact_type='skill_capsule', extraction_approach='frontmatter_plus_structural',
        units=units, full_text=text, metadata={'frontmatter': frontmatter},
    )


def extract_index_file(path: Path, text: str) -> ExtractionResult:
    """MASTER_INDEX.md / *.INDEX.md: each table row / bullet becomes a reference node."""
    doc_result = extract_documentation(path, text)
    nodes = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('|') and stripped.count('|') >= 2:
            nodes.append(ExtractedUnit('reference_node', 'table_row', stripped))
        elif stripped.startswith('- ') or stripped.startswith('* '):
            nodes.append(ExtractedUnit('reference_node', 'bullet', stripped[2:]))
    return ExtractionResult(
        path=path, artifact_type='index_file', extraction_approach='navigation_map_extraction',
        units=doc_result.units + nodes, full_text=text,
    )


def extract_config(path: Path, text: str) -> ExtractionResult:
    units: List[ExtractedUnit] = []
    suffix = path.suffix.lower()
    parsed: Any = None

    try:
        if suffix == '.json':
            parsed = json.loads(text)
        elif suffix in ('.ini', '.cfg'):
            cp = configparser.ConfigParser()
            cp.read_string(text)
            parsed = {s: dict(cp.items(s)) for s in cp.sections()}
        # .yaml/.toml: no stdlib parser; fall through to key-value line scan below.
    except (json.JSONDecodeError, configparser.Error):
        parsed = None

    if isinstance(parsed, dict):
        for k, v in parsed.items():
            units.append(ExtractedUnit('key_value', str(k), json.dumps(v)[:500]))
    else:
        # Best-effort key: value line scan for yaml/toml/unparseable configs.
        for line in text.splitlines():
            m = re.match(r'^([A-Za-z0-9_.\-]+)\s*[:=]\s*(.+)$', line.strip())
            if m:
                units.append(ExtractedUnit('key_value', m.group(1), m.group(2)))

    return ExtractionResult(
        path=path, artifact_type='config', extraction_approach='key_value_structure',
        units=units, full_text=text, metadata={'schema_inferred': parsed is not None},
    )


def extract_notebook(path: Path, text: str) -> ExtractionResult:
    units: List[ExtractedUnit] = []
    try:
        nb = json.loads(text)
        for i, cell in enumerate(nb.get('cells', [])):
            source = ''.join(cell.get('source', []))
            units.append(ExtractedUnit(cell.get('cell_type', 'unknown'), f'cell_{i}', source))
    except json.JSONDecodeError:
        pass
    return ExtractionResult(
        path=path, artifact_type='notebook', extraction_approach='cell_by_cell',
        units=units, full_text=text,
    )


def extract_binary_media(path: Path) -> ExtractionResult:
    """Phase 1: metadata only. Content extraction (OCR/transcription) is Phase 2 OPTIONAL."""
    try:
        size = path.stat().st_size
    except OSError:
        size = None
    return ExtractionResult(
        path=path, artifact_type='binary_media', extraction_approach='metadata_only',
        metadata={'size_bytes': size, 'suffix': path.suffix},
    )


def extract_unknown(path: Path, text: Optional[str]) -> ExtractionResult:
    """UNKNOWN_TYPE: ingest as raw text, flag for review (spec Section 4.3)."""
    return ExtractionResult(
        path=path, artifact_type='unknown', extraction_approach='raw_text',
        full_text=text or '', metadata={'flagged_for_review': True},
    )


MAX_READ_BYTES = 5 * 1024 * 1024  # AiDEA's tight-memory posture: cap what we read into memory


def extract(path: Path) -> ExtractionResult:
    """Dispatch to the right extractor based on classify_artifact_type()."""
    artifact_type = classify_artifact_type(path)

    if artifact_type == 'binary_media':
        return extract_binary_media(path)
    if artifact_type == 'word_document':
        return extract_word_document(path)

    try:
        text = path.read_text(encoding='utf-8', errors='replace')[:MAX_READ_BYTES]
    except (OSError, UnicodeDecodeError):
        return extract_binary_media(path)

    if artifact_type == 'source_code':
        return extract_source_code(path, text)
    if artifact_type == 'documentation':
        return extract_documentation(path, text)
    if artifact_type == 'skill_capsule':
        return extract_skill_capsule(path, text)
    if artifact_type == 'index_file':
        return extract_index_file(path, text)
    if artifact_type == 'config':
        return extract_config(path, text)
    if artifact_type == 'notebook':
        return extract_notebook(path, text)
    return extract_unknown(path, text)


# --- Tier classification (spec Section 4.4) --------------------------------
# Phase 1 builds Tier 4a (Prompt Capsule) + Tier 4b (RAG Package). Every
# artifact type with usable extracted text is eligible for both; binary
# media (metadata-only) and empty extractions are not.

def is_tier4_eligible(result: ExtractionResult) -> bool:
    if result.artifact_type == 'binary_media':
        return False
    return bool(result.full_text.strip()) or bool(result.units)
