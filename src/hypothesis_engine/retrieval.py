"""Local-file retrieval for RAG v0 (privacy-first; no remote fetch)."""

from __future__ import annotations

import re
from pathlib import Path

from hypothesis_engine.models import RetrievedPassage

# Keep retrieval light and predictable for shared machines / large folders.
_ALLOWED_SUFFIXES = frozenset({".txt", ".md", ".markdown"})
_MAX_FILE_BYTES = 256 * 1024
_MAX_FILES_SCANNED = 80
_MAX_SNIPPET_CHARS = 1200
_TOKEN_RE = re.compile(r"[a-z0-9]{2,}", re.IGNORECASE)


def retrieve_local(
    topic: str,
    *,
    corpus_dirs: list[Path] | None = None,
    source_files: list[Path] | None = None,
    k: int = 5,
) -> list[RetrievedPassage]:
    """Score local text/markdown files against the topic; return top-k passages.

    Does not open network connections. Skips unreadable or oversized files.
    """
    k = max(1, min(10, int(k)))
    paths = _collect_paths(corpus_dirs or [], source_files or [])
    if not paths:
        return []

    topic_tokens = _tokenize(topic)
    scored: list[tuple[float, RetrievedPassage]] = []
    for path in paths:
        text = _read_text_file(path)
        if not text:
            continue
        score = _score(topic_tokens, text)
        try:
            ident = str(path.resolve())
        except OSError:
            ident = str(path)
        scored.append(
            (
                score,
                RetrievedPassage(
                    id=f"S{len(scored) + 1}",
                    title=path.name,
                    identifier=ident,
                    snippet=_snippet(text, topic_tokens),
                    year=None,
                    backend="local",
                    score=round(score, 4),
                ),
            )
        )

    scored.sort(key=lambda pair: (-pair[0], pair[1].title.lower()))
    # Drop score==0 (no topic-token overlap). Prefer empty over irrelevant filler.
    positive = [(s, p) for s, p in scored if s > 0]
    if not positive:
        return []
    top = [p for _, p in positive[:k]]
    # Re-number ids in rank order for stable prompt references
    for i, passage in enumerate(top, start=1):
        passage.id = f"S{i}"
    return top


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


def _collect_paths(
    corpus_dirs: list[Path],
    source_files: list[Path],
) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()

    def _add(path: Path) -> None:
        try:
            key = str(path.resolve())
        except OSError:
            key = str(path)
        if key in seen:
            return
        if not path.is_file():
            return
        if path.suffix.lower() not in _ALLOWED_SUFFIXES:
            return
        seen.add(key)
        found.append(path)

    for raw in source_files:
        _add(Path(raw).expanduser())

    for raw_dir in corpus_dirs:
        directory = Path(raw_dir).expanduser()
        if not directory.is_dir():
            continue
        try:
            # Non-recursive v0: only direct children (predictable + private).
            children = sorted(directory.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            continue
        for child in children:
            if len(found) >= _MAX_FILES_SCANNED:
                break
            _add(child)

    return found[:_MAX_FILES_SCANNED]


def _read_text_file(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError:
        return ""
    if size <= 0 or size > _MAX_FILE_BYTES:
        return ""
    try:
        # utf-8 with replacement avoids crashes on odd local notes
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _tokenize(text: str) -> set[str]:
    return {m.group(0).lower() for m in _TOKEN_RE.finditer(text)}


def _score(topic_tokens: set[str], document: str) -> float:
    if not topic_tokens:
        return 0.0
    doc_tokens = _tokenize(document)
    if not doc_tokens:
        return 0.0
    overlap = topic_tokens & doc_tokens
    # Prefer more overlap; mild length normalization
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
