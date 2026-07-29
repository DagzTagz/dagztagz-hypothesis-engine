"""Local-file retrieval (privacy-first; no remote fetch).

Supports text/markdown, optional PDF (pypdf), recursive corpus walk, and chunking.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from hypothesis_engine.models import RetrievedPassage

_TEXT_SUFFIXES = frozenset({".txt", ".md", ".markdown"})
_PDF_SUFFIXES = frozenset({".pdf"})
_MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MiB (chunked after read)
_MAX_FILES_SCANNED = 120
_MAX_WALK_DEPTH = 4  # corpus root = depth 0
_MAX_SNIPPET_CHARS = 1200
_CHUNK_CHARS = 1800
_CHUNK_OVERLAP = 200
_TOKEN_RE = re.compile(r"[a-z0-9]{2,}", re.IGNORECASE)


@dataclass
class RetrieveResult:
    """Passages plus human-readable skip warnings (no paths with secrets beyond names)."""

    passages: list[RetrievedPassage] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def pdf_support_available() -> bool:
    """True if optional pypdf is installed."""
    try:
        import pypdf  # noqa: F401
    except ImportError:
        return False
    return True


def retrieve_local(
    topic: str,
    *,
    corpus_dirs: list[Path] | None = None,
    source_files: list[Path] | None = None,
    k: int = 5,
    full_paths: bool = False,
) -> RetrieveResult:
    """Score local files/chunks against the topic; return top-k passages.

    Does not open network connections. Skips unreadable or oversized files.
    PDFs require optional: pip install 'dagztagz-hypothesis-engine[pdf]'

    By default, ``identifier`` uses a privacy-friendlier path (home → ``~``).
    Pass ``full_paths=True`` to keep absolute paths (debugging).
    """
    k = max(1, min(10, int(k)))
    paths, collect_warnings = _collect_paths(corpus_dirs or [], source_files or [])
    warnings: list[str] = list(collect_warnings)
    if not paths:
        return RetrieveResult(warnings=warnings)

    topic_tokens = _tokenize(topic)
    scored: list[tuple[float, RetrievedPassage]] = []
    pdf_ok = pdf_support_available()

    for path in paths:
        is_pdf = path.suffix.lower() in _PDF_SUFFIXES
        if is_pdf and not pdf_ok:
            warnings.append(
                f"PDF skipped (install PDF support: pip install '.[pdf]'): {path.name}"
            )
            continue

        text, skip_reason = _read_document_with_status(path)
        if skip_reason:
            if is_pdf:
                warnings.append(f"PDF skipped ({skip_reason}): {path.name}")
            # Non-PDF skips stay silent (empty/unreadable text notes are common)
            continue
        if not text:
            if is_pdf:
                warnings.append(
                    f"PDF skipped (no extractable text): {path.name}"
                )
            continue

        try:
            resolved = str(path.resolve())
        except OSError:
            resolved = str(path)
        ident = resolved if full_paths else privacy_path(resolved)

        chunks = _chunk_text(text)
        for ci, chunk in enumerate(chunks, start=1):
            score = _score(topic_tokens, chunk)
            if score <= 0:
                continue
            title = path.name if len(chunks) == 1 else f"{path.name}#chunk{ci}"
            scored.append(
                (
                    score,
                    RetrievedPassage(
                        id="S0",  # renumber later
                        title=title,
                        identifier=ident if len(chunks) == 1 else f"{ident}#chunk{ci}",
                        snippet=_snippet(chunk, topic_tokens),
                        year=None,
                        backend="local",
                        score=round(score, 4),
                    ),
                )
            )

    scored.sort(key=lambda pair: (-pair[0], pair[1].title.lower()))
    if not scored:
        return RetrieveResult(passages=[], warnings=warnings)
    top = [p for _, p in scored[:k]]
    for i, passage in enumerate(top, start=1):
        passage.id = f"S{i}"
    return RetrieveResult(passages=top, warnings=warnings)


def mock_passages(topic: str, *, k: int = 2) -> list[RetrievedPassage]:
    """Deterministic offline passages for dry-run demos (no disk required)."""
    k = max(1, min(10, int(k)))
    base = [
        RetrievedPassage(
            id="S1",
            title="mock-notes-overview.md",
            identifier="mock://local/mock-notes-overview.md",
            snippet=(
                f"Mock local note related to '{topic}'. "
                "In real --retrieve mode this text would come from your files. "
                "Dry-run does not read the network."
            ),
            year=None,
            backend="mock",
            score=1.0,
        ),
        RetrievedPassage(
            id="S2",
            title="mock-methods-caveats.md",
            identifier="mock://local/mock-methods-caveats.md",
            snippet=(
                "Mock caveat: local retrieval is not a literature search. "
                "Only files you supply are considered. Cite only retrieved snippets."
            ),
            year=None,
            backend="mock",
            score=0.5,
        ),
    ]
    return base[:k]


def _allowed_suffix(path: Path) -> bool:
    suf = path.suffix.lower()
    if suf in _TEXT_SUFFIXES:
        return True
    if suf in _PDF_SUFFIXES:
        return True  # may fail later if pypdf missing
    return False


def _is_under_root(path: Path, root_resolved: Path) -> bool:
    """True if path resolves to a location inside root (blocks symlink escape)."""
    try:
        path.resolve().relative_to(root_resolved)
        return True
    except (OSError, ValueError):
        return False


def _collect_paths(
    corpus_dirs: list[Path],
    source_files: list[Path],
) -> tuple[list[Path], list[str]]:
    found: list[Path] = []
    seen: set[str] = set()
    warnings: list[str] = []

    def _add(path: Path) -> None:
        if len(found) >= _MAX_FILES_SCANNED:
            return
        try:
            key = str(path.resolve())
        except OSError:
            key = str(path)
        if key in seen:
            return
        if not path.is_file():
            return
        if not _allowed_suffix(path):
            return
        seen.add(key)
        found.append(path)

    # Explicit --source paths: user chose them; no corpus-root jail.
    for raw in source_files:
        _add(Path(raw).expanduser())

    for raw_dir in corpus_dirs:
        directory = Path(raw_dir).expanduser()
        if not directory.is_dir():
            continue
        try:
            root_resolved = directory.resolve()
        except OSError:
            root_resolved = directory
        try:
            for path in sorted(directory.rglob("*"), key=lambda p: str(p).lower()):
                if len(found) >= _MAX_FILES_SCANNED:
                    break
                if not path.is_file() and not path.is_symlink():
                    continue
                # Symlink or hard path that resolves outside the corpus root → skip.
                if not _is_under_root(path, root_resolved):
                    warnings.append(
                        f"Skipped path outside corpus (possible symlink): {path.name}"
                    )
                    continue
                if not path.is_file():
                    continue
                try:
                    rel = path.resolve().relative_to(root_resolved)
                    depth = len(rel.parts) - 1  # file in root → 0
                except (OSError, ValueError):
                    warnings.append(
                        f"Skipped path outside corpus (possible symlink): {path.name}"
                    )
                    continue
                if depth > _MAX_WALK_DEPTH:
                    continue
                _add(path)
        except OSError:
            continue

    return found[:_MAX_FILES_SCANNED], warnings


def _read_document_with_status(path: Path) -> tuple[str, str | None]:
    """Return (text, skip_reason). skip_reason is set when nothing usable was read."""
    suf = path.suffix.lower()
    if suf in _PDF_SUFFIXES:
        return _read_pdf_with_status(path)
    text = _read_text_file(path)
    if not text:
        return "", "unreadable or empty"
    return text, None


def _read_text_file(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError:
        return ""
    if size <= 0 or size > _MAX_FILE_BYTES:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _read_pdf_with_status(path: Path) -> tuple[str, str | None]:
    if not pdf_support_available():
        return "", "PDF support not installed"
    try:
        size = path.stat().st_size
    except OSError:
        return "", "unreadable"
    if size <= 0:
        return "", "empty file"
    if size > _MAX_FILE_BYTES:
        return "", "file too large"
    try:
        from pypdf import PdfReader
    except ImportError:
        return "", "PDF support not installed"
    try:
        reader = PdfReader(str(path))
        if getattr(reader, "is_encrypted", False):
            try:
                reader.decrypt("")  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                return "", "encrypted or locked"
        parts: list[str] = []
        for page in reader.pages:
            try:
                t = page.extract_text() or ""
            except Exception:  # noqa: BLE001 — skip bad pages
                t = ""
            if t.strip():
                parts.append(t)
        text = "\n\n".join(parts).strip()
        if not text:
            return "", "no extractable text (corrupt, scanned, or empty)"
        return text, None
    except Exception:  # noqa: BLE001 — corrupt PDF
        return "", "unreadable or corrupt"


def _chunk_text(text: str) -> list[str]:
    """Split long documents into overlapping character windows."""
    cleaned = text.strip()
    if not cleaned:
        return []
    if len(cleaned) <= _CHUNK_CHARS:
        return [cleaned]
    chunks: list[str] = []
    start = 0
    n = len(cleaned)
    while start < n:
        end = min(n, start + _CHUNK_CHARS)
        # prefer break at paragraph/space near end
        if end < n:
            window = cleaned[start:end]
            br = max(window.rfind("\n\n"), window.rfind("\n"), window.rfind(" "))
            if br > _CHUNK_CHARS // 3:
                end = start + br
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = max(end - _CHUNK_OVERLAP, start + 1)
    return chunks or [cleaned[:_CHUNK_CHARS]]


def _tokenize(text: str) -> set[str]:
    return {m.group(0).lower() for m in _TOKEN_RE.finditer(text)}


def _score(topic_tokens: set[str], document: str) -> float:
    if not topic_tokens:
        return 0.0
    doc_tokens = _tokenize(document)
    if not doc_tokens:
        return 0.0
    overlap = topic_tokens & doc_tokens
    return len(overlap) / (len(topic_tokens) ** 0.5)


def _snippet(text: str, topic_tokens: set[str]) -> str:
    cleaned = " ".join(text.split())
    if not cleaned:
        return ""
    if not topic_tokens:
        return cleaned[:_MAX_SNIPPET_CHARS]

    lower = cleaned.lower()
    best_idx = 0
    for tok in topic_tokens:
        idx = lower.find(tok)
        if idx != -1:
            best_idx = max(0, idx - 80)
            break
    window = cleaned[best_idx : best_idx + _MAX_SNIPPET_CHARS]
    if best_idx > 0:
        window = "…" + window
    if best_idx + _MAX_SNIPPET_CHARS < len(cleaned):
        window = window + "…"
    return window


def privacy_path(path_str: str) -> str:
    """Rewrite absolute home paths to ``~/...`` for safer JSON/logs.

    Paths outside the home directory are left unchanged (caller chose them).
    """
    if path_str.startswith("mock://"):
        return path_str
    try:
        home = str(Path.home().resolve())
    except OSError:
        home = str(Path.home())
    # Handle both resolved and raw home prefixes
    for prefix in {home, str(Path.home())}:
        if path_str == prefix:
            return "~"
        if path_str.startswith(prefix + "/") or path_str.startswith(prefix + "\\"):
            return "~" + path_str[len(prefix) :]
    return path_str


def short_path_for_display(identifier: str, *, max_len: int = 52) -> str:
    """Shorten a path for CLI tables (home → ~, then truncate if needed)."""
    if identifier.startswith("mock://"):
        return identifier if len(identifier) <= max_len else identifier[: max_len - 1] + "…"
    display = privacy_path(identifier)
    if len(display) <= max_len:
        return display
    return "…" + display[-(max_len - 1) :]
