"""Retrieval outcome as one explicit state (audit F10)."""

import pydantic
import pytest

from hypothesis_engine import workflow
from hypothesis_engine.models import BackgroundBrief, Grounding, Retrieval
from hypothesis_engine.workflow import RETRIEVAL_SCHEMA, retrieval_meta, run_workflow


def test_status_strings_are_a_pinned_contract():
    """vesper-bind matches these spellings; renaming one is a breaking change."""
    assert [r.value for r in Retrieval] == ["skipped", "empty", "ok", "ok_mock"]
    assert [g.value for g in Grounding] == ["model_only", "retrieved", "mixed"]


@pytest.mark.parametrize(
    ("state", "n", "expected"),
    [
        (Retrieval.OFF, 0, ("off", "none", "skipped", 0, "model_knowledge_only")),
        (Retrieval.EMPTY, 0, (RETRIEVAL_SCHEMA, "local", "empty", 0, "local_retrieval_empty")),
        (Retrieval.OK, 2, (RETRIEVAL_SCHEMA, "local", "ok", 2, "local_retrieval+model")),
        (
            Retrieval.MOCK_FILLED,
            2,
            (RETRIEVAL_SCHEMA, "mock", "ok_mock", 2, "local_retrieval+model"),
        ),
    ],
)
def test_one_state_fixes_every_field(state, n, expected):
    passages = workflow.mock_passages("t", k=n) if n else []
    meta = retrieval_meta(state, passages, [])
    keys = ("retrieval", "retrieval_backend", "retrieval_status", "n_passages", "background_mode")
    assert tuple(meta[k] for k in keys) == expected
    assert "retrieval_warnings" not in meta


def test_off_cannot_report_passages():
    meta = retrieval_meta(Retrieval.OFF, workflow.mock_passages("t", k=2), ["w"])
    assert meta["n_passages"] == 0 and "retrieval_warnings" not in meta


def test_grounding_rejects_unknown_values():
    with pytest.raises(pydantic.ValidationError):
        BackgroundBrief(topic="t", summary="s", grounding="vibes")


def test_live_and_dry_run_share_the_vocabulary(monkeypatch, tmp_path):
    """Live with no matching file reports EMPTY through the same helper."""
    replies = iter(
        [
            {"summary": "brief", "grounding": "retrieved"},
            {"hypotheses": [{"id": "H1", "statement": "X raises Y.", "rationale": "r"}]},
            {"verdict": "plausible", "confidence": "low", "checks": []},
            {"tests": []},
        ]
    )
    monkeypatch.setattr(workflow, "chat_json", lambda *a, **k: next(replies))
    monkeypatch.setenv("XAI_API_KEY", "xai-test-not-a-real-key")
    empty = tmp_path / "corpus"
    empty.mkdir()
    bundle = run_workflow(
        "probe topic", n_hypotheses=1, client=object(), retrieve=True, corpus_dirs=[empty]
    )
    assert bundle.meta["retrieval_status"] == Retrieval.EMPTY
    assert bundle.meta["background_mode"] == "local_retrieval_empty"
    assert bundle.background.grounding is Grounding.MODEL_ONLY
