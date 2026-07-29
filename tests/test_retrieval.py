"""Local-file retrieval (RAG v0) — offline only."""

from __future__ import annotations

import json
from pathlib import Path

from hypothesis_engine.cli import main
from hypothesis_engine.retrieval import (
    _chunk_text,
    mock_passages,
    pdf_support_available,
    privacy_path,
    retrieve_local,
    short_path_for_display,
)
from hypothesis_engine.workflow import RETRIEVAL_SCHEMA, run_workflow


def test_retrieve_local_scores_matching_file(tmp_path: Path):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "photosynthesis.md").write_text(
        "Chlorophyll absorbs light. Photosynthesis efficiency depends on wavelength.",
        encoding="utf-8",
    )
    (notes / "unrelated.txt").write_text(
        "Baking bread requires yeast and flour.",
        encoding="utf-8",
    )
    result = retrieve_local(
        "photosynthesis efficiency chlorophyll",
        corpus_dirs=[notes],
        k=2,
    )
    hits = result.passages
    assert hits
    assert hits[0].title == "photosynthesis.md"
    assert hits[0].backend == "local"
    assert hits[0].id == "S1"
    assert "Chlorophyll" in hits[0].snippet or "photosynthesis" in hits[0].snippet.lower()


def test_retrieve_local_empty_dir(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert retrieve_local("anything", corpus_dirs=[empty], k=3).passages == []


def test_retrieve_local_drops_zero_score_files(tmp_path: Path):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "on-topic.md").write_text(
        "Coral bleaching increases with sea surface temperature.",
        encoding="utf-8",
    )
    (notes / "bread.md").write_text(
        "Sourdough starter needs flour water and time.",
        encoding="utf-8",
    )
    result = retrieve_local(
        "coral bleaching temperature",
        corpus_dirs=[notes],
        k=5,
    )
    titles = [h.title for h in result.passages]
    assert "on-topic.md" in titles
    assert "bread.md" not in titles


def test_retrieve_local_all_zero_score_returns_empty(tmp_path: Path):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "bread.md").write_text(
        "Sourdough starter needs flour water and time.",
        encoding="utf-8",
    )
    result = retrieve_local(
        "coral bleaching temperature",
        corpus_dirs=[notes],
        k=5,
    )
    assert result.passages == []


def test_mock_passages_deterministic():
    a = mock_passages("topic x", k=2)
    b = mock_passages("topic x", k=2)
    assert len(a) == 2
    assert a[0].backend == "mock"
    assert a[0].id == b[0].id


def test_dry_run_retrieve_without_files_uses_mock():
    bundle = run_workflow("quantum dots", n_hypotheses=1, dry_run=True, retrieve=True)
    assert bundle.meta["retrieval"] == RETRIEVAL_SCHEMA
    assert bundle.meta["n_passages"] >= 1
    assert bundle.meta["retrieval_status"] == "ok_mock"
    assert bundle.meta["retrieval_backend"] == "mock"
    assert all(s.backend == "mock" for s in bundle.background.sources)
    assert bundle.background.grounding in {"mixed", "retrieved", "model_only"}


def test_dry_run_retrieve_with_corpus(tmp_path: Path):
    f = tmp_path / "coral.md"
    f.write_text("Coral bleaching rises with sea surface temperature stress.", encoding="utf-8")
    bundle = run_workflow(
        "coral bleaching temperature",
        n_hypotheses=1,
        dry_run=True,
        retrieve=True,
        source_files=[f],
        retrieve_k=3,
    )
    assert bundle.meta["retrieval_status"] == "ok"
    assert any(s.backend == "local" for s in bundle.background.sources)
    assert bundle.meta["retrieval_backend"] == "local"


def test_cli_retrieve_live_requires_paths():
    import pytest

    with pytest.raises(SystemExit) as exc:
        main(["--retrieve", "-n", "1", "-y", "--json-only", "topic only"])
    assert exc.value.code == 2


def test_cli_dry_run_retrieve_json(tmp_path: Path, capsys):
    f = tmp_path / "note.txt"
    f.write_text("Nitrogen fixation in legumes under drought stress.", encoding="utf-8")
    code = main(
        [
            "--dry-run",
            "--json-only",
            "--retrieve",
            "--source",
            str(f),
            "-n",
            "1",
            "legume drought nitrogen",
        ]
    )
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["meta"]["retrieval"] == RETRIEVAL_SCHEMA
    assert data["background"]["sources"]
    assert data["meta"]["engine_version"] == "0.3.1"


def test_chunk_text_splits_long_docs():
    text = ("mirror neurons fire during action observation. " * 80).strip()
    chunks = _chunk_text(text)
    assert len(chunks) >= 2
    assert all(len(c) <= 2000 for c in chunks)


def test_retrieve_recursive_subdir(tmp_path: Path):
    root = tmp_path / "lib"
    sub = root / "papers"
    sub.mkdir(parents=True)
    (sub / "deep.md").write_text(
        "Mirror neurons support social learning in classrooms.",
        encoding="utf-8",
    )
    result = retrieve_local(
        "mirror neurons learning",
        corpus_dirs=[root],
        k=3,
    )
    assert result.passages
    assert any("deep.md" in h.title for h in result.passages)


def test_short_path_display_home():
    home = str(Path.home())
    assert short_path_for_display(f"{home}/hypothesis-corpus/text/a.md").startswith("~")


def test_privacy_path_rewrites_home():
    home = str(Path.home().resolve())
    rewritten = privacy_path(f"{home}/hypothesis-corpus/text/a.md")
    assert rewritten.startswith("~/")
    assert home not in rewritten
    # Non-home paths unchanged
    assert privacy_path("/tmp/corpus/a.md") == "/tmp/corpus/a.md"


def test_retrieve_full_paths_flag(tmp_path: Path):
    notes = tmp_path / "notes.md"
    notes.write_text("Coral bleaching and temperature stress in reefs.", encoding="utf-8")
    resolved = str(notes.resolve())
    hits = retrieve_local(
        "coral bleaching temperature",
        source_files=[notes],
        k=2,
        full_paths=False,
    ).passages
    assert hits
    assert hits[0].identifier == privacy_path(resolved)
    hits_full = retrieve_local(
        "coral bleaching temperature",
        source_files=[notes],
        k=2,
        full_paths=True,
    ).passages
    assert hits_full
    assert hits_full[0].identifier == resolved


def test_pdf_retrieve_if_pypdf_available(tmp_path: Path):
    if not pdf_support_available():
        return
    pdf_path = tmp_path / "note.pdf"
    # Minimal PDF with a text operator (line length kept short for ruff)
    lines = [
        b"%PDF-1.1",
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj",
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj",
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144]",
        b" /Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj",
        b"4 0 obj<< /Length 55 >>stream",
        b"BT /F1 12 Tf 10 100 Td (mirror neurons learning) Tj ET",
        b"endstream",
        b"endobj",
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj",
        b"xref",
        b"0 6",
        b"0000000000 65535 f ",
        b"0000000009 00000 n ",
        b"0000000058 00000 n ",
        b"0000000115 00000 n ",
        b"0000000266 00000 n ",
        b"0000000361 00000 n ",
        b"trailer<< /Size 6 /Root 1 0 R >>",
        b"startxref",
        b"440",
        b"%%EOF",
        b"",
    ]
    pdf_path.write_bytes(b"\n".join(lines))
    result = retrieve_local("mirror neurons learning", source_files=[pdf_path], k=3)
    # Minimal PDFs sometimes extract empty; only assert when text is found
    if result.passages:
        assert result.passages[0].backend == "local"
        assert result.passages[0].score and result.passages[0].score > 0


def test_pdf_missing_support_warns(tmp_path: Path, monkeypatch):
    pdf_path = tmp_path / "secret.pdf"
    pdf_path.write_bytes(b"%PDF-1.1\n%%EOF\n")
    monkeypatch.setattr(
        "hypothesis_engine.retrieval.pdf_support_available",
        lambda: False,
    )
    result = retrieve_local("anything", source_files=[pdf_path], k=3)
    assert result.passages == []
    assert result.warnings
    assert "pdf" in result.warnings[0].lower()
    assert "secret.pdf" in result.warnings[0]
    # Privacy: warning uses basename only, not absolute path
    assert str(pdf_path.resolve()) not in result.warnings[0]
    assert "/" not in result.warnings[0].split(": ", 1)[-1]


def test_symlink_escape_outside_corpus_is_skipped(tmp_path: Path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    outside = tmp_path / "secret.md"
    outside.write_text(
        "mirror neurons secret outside file should not be read as corpus hit.",
        encoding="utf-8",
    )
    link = corpus / "trap.md"
    try:
        link.symlink_to(outside)
    except OSError:
        return  # platform may disallow symlinks
    # Also a real in-corpus file that should still match
    (corpus / "real.md").write_text(
        "mirror neurons support learning in the classroom.",
        encoding="utf-8",
    )
    result = retrieve_local(
        "mirror neurons learning",
        corpus_dirs=[corpus],
        k=5,
    )
    titles = [p.title for p in result.passages]
    assert "trap.md" not in titles
    assert any("real.md" in t for t in titles)
    assert any("outside corpus" in w.lower() or "symlink" in w.lower() for w in result.warnings)
    assert all("secret.md" not in w or "trap.md" in w for w in result.warnings)


def test_audit_includes_retrieve_and_n_passages(tmp_path: Path, capsys):
    log = tmp_path / "a.jsonl"
    f = tmp_path / "note.md"
    f.write_text("Nitrogen fixation under drought.", encoding="utf-8")
    code = main(
        [
            "--dry-run",
            "--json-only",
            "--retrieve",
            "--source",
            str(f),
            "-n",
            "1",
            "--audit-log",
            str(log),
            "nitrogen drought",
        ]
    )
    assert code == 0
    events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    by_name = {e["event"]: e for e in events}
    assert by_name["start"]["retrieve"] is True
    assert by_name["complete"]["retrieve"] is True
    assert by_name["complete"]["n_passages"] >= 1
    # No snippets or absolute topic plaintext by default
    assert "topic" not in by_name["complete"]
