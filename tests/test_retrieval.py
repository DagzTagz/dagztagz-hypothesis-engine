"""Local-file retrieval (RAG v0) — offline only."""

from __future__ import annotations

import json
from pathlib import Path

from hypothesis_engine.cli import main
from hypothesis_engine.retrieval import mock_passages, retrieve_local
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
    hits = retrieve_local(
        "photosynthesis efficiency chlorophyll",
        corpus_dirs=[notes],
        k=2,
    )
    assert hits
    assert hits[0].title == "photosynthesis.md"
    assert hits[0].backend == "local"
    assert hits[0].id == "S1"
    assert "Chlorophyll" in hits[0].snippet or "photosynthesis" in hits[0].snippet.lower()


def test_retrieve_local_empty_dir(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert retrieve_local("anything", corpus_dirs=[empty], k=3) == []


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
    hits = retrieve_local(
        "coral bleaching temperature",
        corpus_dirs=[notes],
        k=5,
    )
    titles = [h.title for h in hits]
    assert "on-topic.md" in titles
    assert "bread.md" not in titles


def test_retrieve_local_all_zero_score_returns_empty(tmp_path: Path):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "bread.md").write_text(
        "Sourdough starter needs flour water and time.",
        encoding="utf-8",
    )
    hits = retrieve_local(
        "coral bleaching temperature",
        corpus_dirs=[notes],
        k=5,
    )
    assert hits == []


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
    assert data["meta"]["retrieval"] == "rag_v0_local"
    assert data["background"]["sources"]
    assert data["meta"]["engine_version"] == "0.3.0"
