"""Single workflow: background → generate → multi-check verify → suggest tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from openai import OpenAI

from hypothesis_engine import __version__, prompts
from hypothesis_engine.config import Settings, get_settings
from hypothesis_engine.llm import build_client, chat_json
from hypothesis_engine.models import (
    REQUIRED_CHECK_IDS,
    BackgroundBrief,
    CheckResult,
    CheckStatus,
    Confidence,
    Hypothesis,
    HypothesisBundle,
    RetrievedPassage,
    SuggestedTest,
    Verdict,
    VerificationResult,
)
from hypothesis_engine.retrieval import mock_passages, retrieve_local

# Schema tags for Phase 2 thin slices (still one API call per step type).
VERIFICATION_SCHEMA = "multi_check_v1"
TESTS_SCHEMA = "richer_tests_v1"
RETRIEVAL_SCHEMA = "rag_v0_local"

# Soft caps so a runaway model reply cannot blow up memory/logs (polish / safety).
_MAX_FIELD_CHARS = 4000
_MAX_LIST_ITEMS = 24
_MAX_LIST_ITEM_CHARS = 500
_KNOWN_TEST_METHODS = frozenset(
    {"experiment", "simulation", "analysis", "observation"}
)


def estimate_api_calls(n_hypotheses: int) -> int:
    """Rough live-mode call count: background + generate + verify×N + tests×N.

    Multi-check verification and richer tests still use one call each per
    hypothesis (richer JSON, not extra round-trips).
    """
    n = max(1, min(5, int(n_hypotheses)))
    return 2 + 2 * n


def run_workflow(
    topic: str,
    *,
    n_hypotheses: int = 2,
    settings: Settings | None = None,
    client: OpenAI | None = None,
    dry_run: bool = False,
    on_progress: Callable[[str], None] | None = None,
    retrieve: bool = False,
    corpus_dirs: list[Path] | None = None,
    source_files: list[Path] | None = None,
    retrieve_k: int = 5,
) -> HypothesisBundle:
    """Run the full pipeline for a topic (background → generate → verify → tests).

    Parameters
    ----------
    topic:
        Scientific topic or short research question.
    n_hypotheses:
        How many hypotheses to propose (kept small for cost/clarity).
    dry_run:
        If True, return deterministic mock output without calling the API.
    on_progress:
        Optional callback for human-readable step updates (e.g. CLI spinner text).
    retrieve:
        If True, ground background on local files (RAG v0). No remote fetch.
    corpus_dirs / source_files:
        Local paths for retrieval when retrieve=True.
    retrieve_k:
        Max passages to keep (1–10).
    """
    topic = topic.strip()
    if not topic:
        raise ValueError("topic must be non-empty")
    if n_hypotheses < 1 or n_hypotheses > 5:
        raise ValueError("n_hypotheses must be between 1 and 5")

    def _progress(message: str) -> None:
        if on_progress is not None:
            on_progress(message)

    settings = settings or get_settings()
    corpus_dirs = list(corpus_dirs or [])
    source_files = list(source_files or [])
    retrieve_k = max(1, min(10, int(retrieve_k)))

    if dry_run:
        _progress("Dry-run: building mock results (no network)…")
        return _mock_bundle(
            topic,
            n_hypotheses,
            retrieve=retrieve,
            corpus_dirs=corpus_dirs,
            source_files=source_files,
            retrieve_k=retrieve_k,
        )

    client = client or build_client(settings)
    model = settings.xai_model
    total = estimate_api_calls(n_hypotheses)
    step = 0

    def _tick(label: str) -> None:
        nonlocal step
        step += 1
        _progress(f"[{step}/{total}] {label}")

    passages: list[RetrievedPassage] = []
    retrieval_status = "skipped"
    if retrieve:
        _progress("Local retrieval: scoring your files (no remote search)…")
        passages = retrieve_local(
            topic,
            corpus_dirs=corpus_dirs,
            source_files=source_files,
            k=retrieve_k,
        )
        retrieval_status = "ok" if passages else "empty"
        _progress(f"Local retrieval done ({len(passages)} passage(s)).")

    _tick("Calling xAI for background brief (this can take a while)…")
    background = _step_background(client, model, topic, passages=passages)
    _progress("Background brief received.")

    _tick("Generating hypotheses (please wait; do not type)…")
    hypotheses = _step_generate(client, model, topic, background, n_hypotheses)
    _progress(f"Generated {len(hypotheses)} hypothesis(es).")

    verifications: list[VerificationResult] = []
    tests: list[SuggestedTest] = []
    for hyp in hypotheses:
        _tick(f"Multi-check verifying {hyp.id} (one API call)…")
        ver = _step_verify(client, model, topic, background, hyp)
        verifications.append(ver)
        check_bits = ", ".join(f"{c.id}={c.status.value}" for c in ver.checks)
        _progress(f"{hyp.id} verification done ({ver.verdict.value}; {check_bits}).")

        _tick(f"Suggesting richer tests for {hyp.id} (one API call)…")
        tests.extend(_step_tests(client, model, topic, hyp, ver))
        n_tests = sum(1 for t in tests if t.hypothesis_id == hyp.id)
        _progress(f"{hyp.id} test suggestions done ({n_tests}).")

    _progress("All API steps finished. Assembling report…")
    overall = _overall_notes(hypotheses, verifications)
    bg_mode = (
        "local_retrieval+model"
        if retrieve and passages
        else ("local_retrieval_empty" if retrieve else "model_knowledge_only")
    )
    meta: dict = {
        "phase": 2,
        "engine_version": __version__,
        "model": model,
        "n_hypotheses": n_hypotheses,
        "background_mode": bg_mode,
        "verification": VERIFICATION_SCHEMA,
        "tests": TESTS_SCHEMA,
        "retrieval": RETRIEVAL_SCHEMA if retrieve else "off",
        "retrieval_backend": "local" if retrieve else "none",
        "retrieval_status": retrieval_status if retrieve else "skipped",
        "n_passages": len(passages) if retrieve else 0,
    }
    return HypothesisBundle(
        topic=topic,
        background=background,
        hypotheses=hypotheses,
        verifications=verifications,
        tests=tests,
        overall_notes=overall,
        meta=meta,
    )


def _step_background(
    client: OpenAI,
    model: str,
    topic: str,
    *,
    passages: list[RetrievedPassage] | None = None,
) -> BackgroundBrief:
    passages = passages or []
    if passages:
        user = prompts.BACKGROUND_USER_RETRIEVED.format(
            topic=topic,
            passages_json=json.dumps(
                [p.model_dump(mode="json") for p in passages],
                ensure_ascii=False,
            ),
        )
    else:
        user = prompts.BACKGROUND_USER.format(topic=topic)

    data = chat_json(
        client,
        model=model,
        system=prompts.SYSTEM_SCIENTIST,
        user=user,
        temperature=0.3,
    )
    return _normalize_background(data, topic=topic, passages=passages)


def _normalize_background(
    data: dict,
    *,
    topic: str,
    passages: list[RetrievedPassage],
) -> BackgroundBrief:
    """Attach/normalize grounding + sources after the background LLM call."""
    if not isinstance(data, dict):
        data = {}
    data = dict(data)
    data.setdefault("topic", topic)
    if "known_limitations" not in data or not data["known_limitations"]:
        data["known_limitations"] = [
            "Background is not a comprehensive literature search.",
        ]
    if passages:
        # Prefer engine-side sources of truth (paths the user supplied).
        data["sources"] = [p.model_dump(mode="json") for p in passages]
        grounding = str(data.get("grounding") or "mixed").strip().lower()
        if grounding not in {"model_only", "retrieved", "mixed"}:
            grounding = "mixed"
        # Empty model claim of retrieved-only is ok; empty passages → model_only
        data["grounding"] = grounding if grounding != "model_only" else "mixed"
        lim = data.get("known_limitations")
        if isinstance(lim, list):
            note = (
                "Grounding used local-file retrieval only (RAG v0); "
                "not a full literature review."
            )
            if note not in lim:
                lim = [str(x) for x in lim] + [note]
            data["known_limitations"] = lim
    else:
        data["sources"] = []
        data["grounding"] = "model_only"
        if "summary" not in data:
            data["summary"] = ""
    # Soft lists
    for key in ("key_concepts", "known_limitations", "caveats"):
        val = data.get(key)
        if val is None:
            data[key] = []
        elif isinstance(val, str):
            data[key] = [val] if val.strip() else []
        elif not isinstance(val, list):
            data[key] = []
    if not data.get("summary"):
        data["summary"] = "No summary returned by the model."
    return BackgroundBrief.model_validate(data)


def _step_generate(
    client: OpenAI,
    model: str,
    topic: str,
    background: BackgroundBrief,
    n: int,
) -> list[Hypothesis]:
    data = chat_json(
        client,
        model=model,
        system=prompts.SYSTEM_SCIENTIST,
        user=prompts.GENERATE_USER.format(
            topic=topic,
            background_json=background.model_dump_json(),
            n=n,
        ),
        temperature=0.6,
    )
    raw = data.get("hypotheses", data if isinstance(data, list) else [])
    if not isinstance(raw, list) or not raw:
        raise ValueError("Model returned no hypotheses")
    hyps: list[Hypothesis] = []
    for i, item in enumerate(raw[:n], start=1):
        if not isinstance(item, dict):
            continue
        try:
            h = _normalize_hypothesis(item, fallback_id=f"H{i}")
        except Exception:  # noqa: BLE001 — skip one bad row
            continue
        hyps.append(h)
    if not hyps:
        raise ValueError("Model returned no usable hypotheses")
    # Normalize ids if model forgot them / duplicates
    for i, h in enumerate(hyps, start=1):
        if not h.id:
            h.id = f"H{i}"
    return hyps


def _step_verify(
    client: OpenAI,
    model: str,
    topic: str,
    background: BackgroundBrief,
    hyp: Hypothesis,
) -> VerificationResult:
    data = chat_json(
        client,
        model=model,
        system=prompts.SYSTEM_SCIENTIST,
        user=prompts.VERIFY_USER.format(
            topic=topic,
            background_json=background.model_dump_json(),
            hypothesis_json=hyp.model_dump_json(),
        ),
        temperature=0.3,
    )
    return _normalize_verification(data if isinstance(data, dict) else {}, hyp_id=hyp.id)


def _clip_text(value: object, *, max_chars: int = _MAX_FIELD_CHARS) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def _clip_str_list(raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        items = [raw] if raw.strip() else []
    elif isinstance(raw, list):
        items = [str(x).strip() for x in raw if str(x).strip()]
    else:
        return []
    out: list[str] = []
    for item in items[:_MAX_LIST_ITEMS]:
        out.append(_clip_text(item, max_chars=_MAX_LIST_ITEM_CHARS))
    return out


def _parse_confidence(raw: object, *, default: Confidence = Confidence.MEDIUM) -> Confidence:
    if isinstance(raw, Confidence):
        return raw
    if isinstance(raw, str):
        key = raw.strip().lower()
        try:
            return Confidence(key)
        except ValueError:
            pass
    return default


def _parse_verdict(raw: object, *, default: Verdict = Verdict.NEEDS_REVISION) -> Verdict:
    if isinstance(raw, Verdict):
        return raw
    if isinstance(raw, str):
        key = raw.strip().lower().replace(" ", "_").replace("-", "_")
        try:
            return Verdict(key)
        except ValueError:
            pass
    return default


def _parse_check_status(raw: object) -> CheckStatus:
    if isinstance(raw, CheckStatus):
        return raw
    if isinstance(raw, str):
        key = raw.strip().lower()
        try:
            return CheckStatus(key)
        except ValueError:
            pass
    return CheckStatus.UNCLEAR


def _normalize_hypothesis(item: dict, *, fallback_id: str) -> Hypothesis:
    data = {
        "id": _clip_text(item.get("id") or fallback_id, max_chars=32) or fallback_id,
        "statement": _clip_text(item.get("statement")),
        "rationale": _clip_text(item.get("rationale")),
        "assumptions": _clip_str_list(item.get("assumptions")),
        "domain": _clip_text(item.get("domain"), max_chars=200) or None,
    }
    if not data["statement"]:
        raise ValueError("hypothesis missing statement")
    if not data["rationale"]:
        data["rationale"] = "No rationale provided by the model."
    return Hypothesis.model_validate(data)


def _normalize_verification(raw: dict, *, hyp_id: str) -> VerificationResult:
    """Coerce multi-check verification JSON; soft-default bad enums."""
    data = dict(raw)
    data["hypothesis_id"] = _clip_text(data.get("hypothesis_id") or hyp_id, max_chars=32)
    data["verdict"] = _parse_verdict(data.get("verdict")).value
    data["confidence"] = _parse_confidence(data.get("confidence")).value
    data["consistency_notes"] = _clip_text(
        data.get("consistency_notes") or "No consistency notes returned."
    )
    data["contradictions"] = _clip_str_list(data.get("contradictions"))
    data["revision_suggestions"] = _clip_str_list(data.get("revision_suggestions"))

    critiques_in = data.get("critiques")
    critiques: list[dict] = []
    if isinstance(critiques_in, list):
        for c in critiques_in[:_MAX_LIST_ITEMS]:
            if not isinstance(c, dict):
                continue
            claim = _clip_text(c.get("claim"), max_chars=_MAX_LIST_ITEM_CHARS)
            if not claim:
                continue
            critiques.append(
                {
                    "claim": claim,
                    "severity": _parse_confidence(
                        c.get("severity"), default=Confidence.MEDIUM
                    ).value,
                    "evidence_or_reasoning": _clip_text(
                        c.get("evidence_or_reasoning") or "",
                        max_chars=_MAX_LIST_ITEM_CHARS,
                    ),
                }
            )
    data["critiques"] = critiques
    data["checks"] = [
        c.model_dump(mode="json") for c in _normalize_checks(data.get("checks"))
    ]
    return VerificationResult.model_validate(data)


def _normalize_checks(raw: object) -> list[CheckResult]:
    """Ensure the four fixed multi-check slots are present and ordered.

    Unknown ids from the model are dropped; missing required ids become unclear.
    """
    by_id: dict[str, CheckResult] = {}
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            cid = str(item.get("id", "")).strip().lower().replace(" ", "_").replace("-", "_")
            if cid not in REQUIRED_CHECK_IDS or cid in by_id:
                continue
            try:
                by_id[cid] = CheckResult(
                    id=cid,
                    status=_parse_check_status(item.get("status")),
                    summary=_clip_text(
                        item.get("summary") or "No summary provided.",
                        max_chars=_MAX_LIST_ITEM_CHARS,
                    ),
                )
            except Exception:  # noqa: BLE001 — bad model row → placeholder
                by_id[cid] = CheckResult(
                    id=cid,
                    status=CheckStatus.UNCLEAR,
                    summary="Model returned an invalid check object for this id.",
                )

    ordered: list[CheckResult] = []
    for cid in REQUIRED_CHECK_IDS:
        if cid in by_id:
            ordered.append(by_id[cid])
        else:
            ordered.append(
                CheckResult(
                    id=cid,
                    status=CheckStatus.UNCLEAR,
                    summary="Model omitted this check; treat as not assessed.",
                )
            )
    return ordered


def _mock_checks(*, plausible: bool) -> list[CheckResult]:
    """Deterministic multi-check rows for dry-run."""
    if plausible:
        return [
            CheckResult(
                id="consistency",
                status=CheckStatus.PASS,
                summary="Mock: statement coheres with its listed assumptions.",
            ),
            CheckResult(
                id="testability",
                status=CheckStatus.PASS,
                summary="Mock: claim is framed as measurable and falsifiable.",
            ),
            CheckResult(
                id="confounds",
                status=CheckStatus.WARN,
                summary="Mock: alternative explanations not fully ruled out.",
            ),
            CheckResult(
                id="prior_knowledge",
                status=CheckStatus.PASS,
                summary="Mock: no obvious conflict with well-established knowledge.",
            ),
        ]
    return [
        CheckResult(
            id="consistency",
            status=CheckStatus.WARN,
            summary="Mock: some tension between claim and assumptions.",
        ),
        CheckResult(
            id="testability",
            status=CheckStatus.PASS,
            summary="Mock: still testable in principle.",
        ),
        CheckResult(
            id="confounds",
            status=CheckStatus.FAIL,
            summary="Mock: major confounds missing; needs clearer controls.",
        ),
        CheckResult(
            id="prior_knowledge",
            status=CheckStatus.WARN,
            summary="Mock: partial tension with established patterns (synthetic).",
        ),
    ]


def _step_tests(
    client: OpenAI,
    model: str,
    topic: str,
    hyp: Hypothesis,
    ver: VerificationResult,
) -> list[SuggestedTest]:
    data = chat_json(
        client,
        model=model,
        system=prompts.SYSTEM_SCIENTIST,
        user=prompts.TESTS_USER.format(
            topic=topic,
            hypothesis_json=hyp.model_dump_json(),
            verification_json=ver.model_dump_json(),
        ),
        temperature=0.5,
    )
    raw = data.get("tests", [])
    if not isinstance(raw, list):
        return []
    tests: list[SuggestedTest] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if "hypothesis_id" not in item:
            item = {**item, "hypothesis_id": hyp.id}
        tests.append(_normalize_suggested_test(item, hyp_id=hyp.id))
    return tests


def _normalize_suggested_test(item: dict, *, hyp_id: str) -> SuggestedTest:
    """Coerce richer-test fields so partial model JSON still validates."""
    data = dict(item)
    data["hypothesis_id"] = _clip_text(data.get("hypothesis_id") or hyp_id, max_chars=32)

    data["controls"] = _clip_str_list(data.get("controls"))
    data["materials_or_data"] = _clip_str_list(data.get("materials_or_data"))
    data["notes"] = _clip_str_list(data.get("notes"))

    # Keep only known multi-check ids; normalize casing/separators.
    allowed = set(REQUIRED_CHECK_IDS)
    cleaned_ids: list[str] = []
    for cid in _clip_str_list(data.get("addresses_checks")):
        norm = cid.lower().replace(" ", "_").replace("-", "_")
        if norm in allowed and norm not in cleaned_ids:
            cleaned_ids.append(norm)
    data["addresses_checks"] = cleaned_ids

    for str_key in (
        "what_is_measured",
        "rough_duration",
        "description",
        "title",
        "what_would_falsify",
    ):
        data[str_key] = _clip_text(data.get(str_key))

    if not data.get("title"):
        data["title"] = f"Suggested test for {hyp_id}"
    if not data.get("description"):
        data["description"] = "No description provided by the model."
    if not data.get("what_would_falsify"):
        data["what_would_falsify"] = "Not specified by the model."

    method = _clip_text(data.get("method") or "analysis", max_chars=64).lower()
    if method not in _KNOWN_TEST_METHODS:
        method = "analysis"
    data["method"] = method

    data["rough_difficulty"] = _parse_confidence(
        data.get("rough_difficulty"), default=Confidence.MEDIUM
    ).value

    return SuggestedTest.model_validate(data)


def _overall_notes(
    hypotheses: list[Hypothesis],
    verifications: list[VerificationResult],
) -> str:
    by_id = {v.hypothesis_id: v for v in verifications}
    parts: list[str] = []
    for h in hypotheses:
        v = by_id.get(h.id)
        if not v:
            parts.append(f"{h.id}: no verification")
            continue
        parts.append(f"{h.id}: verdict={v.verdict.value}, confidence={v.confidence.value}")
    return (
        "Run complete (multi-check verification + richer tests). "
        "Treat outputs as research aids, not established science. "
        + " | ".join(parts)
    )


def _mock_suggested_test(hid: str, *, plausible: bool) -> SuggestedTest:
    """Deterministic richer-test row for dry-run."""
    if plausible:
        return SuggestedTest(
            hypothesis_id=hid,
            title=f"Mock test for {hid}",
            method="simulation",
            description=(
                "Run a toy simulation that varies Y under controlled noise and "
                "records steady-state X; compare against a null of no Y→X link."
            ),
            what_would_falsify="No dependence of X on Y under the stated conditions.",
            what_is_measured="Steady-state value of X as a function of Y (synthetic units).",
            controls=[
                "Null model with Y shuffled",
                "Hold Z fixed across runs",
            ],
            materials_or_data=[
                "Laptop or small compute instance",
                "Open-source ODE/agent simulator (mock)",
            ],
            addresses_checks=["testability", "confounds"],
            rough_difficulty=Confidence.LOW,
            rough_duration="hours",
            notes=["dry-run", "not a real protocol"],
        )
    return SuggestedTest(
        hypothesis_id=hid,
        title=f"Mock pilot for {hid} (revision path)",
        method="experiment",
        description=(
            "Minimal pilot that operationalizes X and Y with explicit baselines "
            "before a full causal design (addresses confounds warn/fail)."
        ),
        what_would_falsify=(
            "Pilot cannot define measurable X/Y, or baseline already matches "
            "the predicted effect without manipulating Y."
        ),
        what_is_measured="Operational definitions of X and Y plus baseline rates.",
        controls=["Pre-manipulation baseline", "Negative control condition"],
        materials_or_data=["Lab notebook template", "Calibrated meter (mock)"],
        addresses_checks=["confounds", "testability", "consistency"],
        rough_difficulty=Confidence.MEDIUM,
        rough_duration="days",
        notes=["dry-run", "prefer clarify claim before large study"],
    )


def _mock_bundle(
    topic: str,
    n: int,
    *,
    retrieve: bool = False,
    corpus_dirs: list[Path] | None = None,
    source_files: list[Path] | None = None,
    retrieve_k: int = 5,
) -> HypothesisBundle:
    """Deterministic offline output for demos and tests (no network)."""
    passages: list[RetrievedPassage] = []
    retrieval_status = "skipped"
    if retrieve:
        passages = retrieve_local(
            topic,
            corpus_dirs=corpus_dirs or [],
            source_files=source_files or [],
            k=retrieve_k,
        )
        if not passages:
            # Demo fill only — not a real local hit (see meta.retrieval_status).
            passages = mock_passages(topic, k=min(2, retrieve_k))
            retrieval_status = "ok_mock"
        else:
            retrieval_status = "ok"

    if passages:
        summary = (
            f"Mock background for '{topic}' grounded on {len(passages)} local "
            "passage(s) (dry-run). Not a literature search."
        )
        grounding = "mixed"
        limitations = [
            "dry-run mode; no LLM call",
            "local-file retrieval only (RAG v0); not a full literature review",
        ]
    else:
        summary = (
            f"Mock background for '{topic}'. In live mode this would be a short "
            "model-knowledge briefing, not a literature review."
        )
        grounding = "model_only"
        limitations = ["dry-run mode; no LLM call"]

    background = BackgroundBrief(
        topic=topic,
        summary=summary,
        key_concepts=["mock-concept"],
        known_limitations=limitations,
        caveats=["For local testing only"],
        sources=passages,
        grounding=grounding,
    )
    hypotheses: list[Hypothesis] = []
    verifications: list[VerificationResult] = []
    tests: list[SuggestedTest] = []
    for i in range(1, n + 1):
        hid = f"H{i}"
        plausible = i % 2 == 1
        hypotheses.append(
            Hypothesis(
                id=hid,
                statement=f"Mock hypothesis {i} about {topic}: measurable effect X depends on Y.",
                rationale="Generated in dry-run mode for scaffolding tests.",
                assumptions=["This is synthetic data"],
                domain="mock",
            )
        )
        verifications.append(
            VerificationResult(
                hypothesis_id=hid,
                verdict=Verdict.PLAUSIBLE if plausible else Verdict.NEEDS_REVISION,
                confidence=Confidence.LOW,
                consistency_notes="Dry-run multi-check verification placeholder.",
                checks=_mock_checks(plausible=plausible),
                critiques=[],
                contradictions=[],
                revision_suggestions=["Replace with live run for real critique"],
            )
        )
        tests.append(_mock_suggested_test(hid, plausible=plausible))
    return HypothesisBundle(
        topic=topic,
        background=background,
        hypotheses=hypotheses,
        verifications=verifications,
        tests=tests,
        overall_notes="Dry-run mock output; no API calls were made.",
        meta={
            "phase": 2,
            "engine_version": __version__,
            "dry_run": True,
            "n_hypotheses": n,
            "verification": VERIFICATION_SCHEMA,
            "tests": TESTS_SCHEMA,
            "retrieval": RETRIEVAL_SCHEMA if retrieve else "off",
            "retrieval_backend": _retrieval_backend_label(retrieve, passages),
            "retrieval_status": retrieval_status if retrieve else "skipped",
            "n_passages": len(passages) if retrieve else 0,
            "background_mode": (
                "local_retrieval+model" if retrieve and passages else "model_knowledge_only"
            ),
        },
    )


def _retrieval_backend_label(
    retrieve: bool, passages: list[RetrievedPassage]
) -> str:
    if not retrieve:
        return "none"
    if any(p.backend == "local" for p in passages):
        return "local"
    if any(p.backend == "mock" for p in passages):
        return "mock"
    return "local"


def bundle_to_json(bundle: HypothesisBundle, *, indent: int = 2) -> str:
    return json.dumps(bundle.to_pretty_dict(), indent=indent, ensure_ascii=False)
