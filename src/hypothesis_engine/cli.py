"""Command-line interface for the hypothesis engine."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hypothesis_engine import __version__
from hypothesis_engine.audit import AuditEncryptionUnavailable, topic_audit_fields
from hypothesis_engine.config import get_settings
from hypothesis_engine.workflow import bundle_to_json, estimate_api_calls, run_workflow

# Owner read/write only — avoid group/other-readable research outputs on shared hosts.
_PRIVATE_FILE_MODE = 0o600
# Truncate long topics in human panels (full topic still used for the run).
_DISPLAY_TOPIC_MAX = 160


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hypothesis-engine",
        description=(
            "DagzTagz Hypothesis Engine — generate, multi-check adversarially verify, "
            "and suggest tests for scientific hypotheses. "
            "Powered by Grok (xAI) in live mode."
        ),
    )
    parser.add_argument(
        "topic",
        nargs="?",
        help="Scientific topic or short description (or pass via --topic)",
    )
    parser.add_argument("--topic", dest="topic_opt", help="Alternative to positional topic")
    parser.add_argument(
        "-n",
        "--num-hypotheses",
        type=int,
        default=2,
        choices=(1, 2, 3, 4, 5),
        metavar="N",
        help="Number of hypotheses to generate (1-5, default: 2)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not call the API; emit deterministic mock structured output (free)",
    )
    parser.add_argument(
        "--retrieve",
        action="store_true",
        help=(
            "Opt-in local-file retrieval for background (RAG v0, privacy-first). "
            "Requires --corpus and/or --source (dry-run may use mock passages)."
        ),
    )
    parser.add_argument(
        "--corpus",
        action="append",
        type=Path,
        default=None,
        metavar="DIR",
        help="Directory of .txt/.md files to search (non-recursive; repeatable)",
    )
    parser.add_argument(
        "--source",
        action="append",
        type=Path,
        default=None,
        metavar="FILE",
        help="Local .txt/.md file to include in retrieval (repeatable)",
    )
    parser.add_argument(
        "--retrieve-k",
        type=int,
        default=5,
        metavar="K",
        help="Max local passages to keep when --retrieve is set (1-10, default 5)",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip the live-mode cost confirmation prompt (scripts/CI)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write full JSON result to this file",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print only JSON to stdout (no rich tables)",
    )
    parser.add_argument(
        "--audit-log",
        type=Path,
        help="Append JSONL audit events (start/end/error) to this file",
    )
    parser.add_argument(
        "--audit-include-topic",
        action="store_true",
        help=(
            "Include plaintext topic in the audit log (off by default). "
            "Prefer AUDIT_LOG_KEY encryption instead when possible."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    topic = (args.topic_opt or args.topic or "").strip()
    if not topic:
        parser.error("topic is required (positional or --topic)")

    err = Console(stderr=True)
    out = Console(stderr=False)
    n = args.num_hypotheses
    dry_run = args.dry_run
    retrieve = bool(args.retrieve)
    corpus_dirs = list(args.corpus or [])
    source_files = list(args.source or [])
    retrieve_k = max(1, min(10, int(args.retrieve_k)))
    estimated = estimate_api_calls(n) if not dry_run else 0

    if retrieve and not dry_run and not corpus_dirs and not source_files:
        parser.error(
            "--retrieve requires --corpus DIR and/or --source FILE "
            "(local files only in RAG v0). Dry-run may omit them and use mocks."
        )

    try:
        topic_fields = topic_audit_fields(
            topic,
            include_plaintext=args.audit_include_topic,
        )
    except AuditEncryptionUnavailable as exc:
        # markup=False so pip extra names like [audit] are not eaten by Rich
        err.print(f"[red]Error:[/red] {exc}", markup=False)
        return 1

    if not dry_run:
        settings = get_settings()
        if not _confirm_live(
            err,
            topic=topic,
            n=n,
            estimated=estimated,
            assume_yes=args.yes,
            model=settings.xai_model,
            base_url=settings.xai_base_url,
            trusted_host=settings.uses_trusted_xai_host(),
            retrieve=retrieve,
        ):
            _audit(
                args.audit_log,
                {
                    "event": "aborted",
                    "reason": "user_declined_or_noninteractive_without_yes",
                    "dry_run": False,
                    "n_hypotheses": n,
                    "estimated_api_calls": estimated,
                    **topic_fields,
                },
            )
            return 2
        _print_live_wait_banner(err, estimated=estimated, n=n)

    _audit(
        args.audit_log,
        {
            "event": "start",
            "dry_run": dry_run,
            "n_hypotheses": n,
            "estimated_api_calls": estimated,
            "version": __version__,
            **topic_fields,
        },
    )

    def _progress(message: str) -> None:
        # stderr so --json-only stdout stays clean
        err.print(f"[cyan]…[/cyan] {message}")

    try:
        bundle = run_workflow(
            topic,
            n_hypotheses=n,
            dry_run=dry_run,
            on_progress=None if args.json_only and dry_run else _progress,
            retrieve=retrieve,
            corpus_dirs=corpus_dirs,
            source_files=source_files,
            retrieve_k=retrieve_k,
        )
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        message = _friendly_error(exc)
        err.print(f"[red]Error:[/red] {message}")
        _audit(
            args.audit_log,
            {
                "event": "error",
                "dry_run": dry_run,
                "error_type": type(exc).__name__,
                "error": message,
                **topic_fields,
            },
        )
        return 1
    else:
        if not dry_run:
            err.print("[green]Done waiting — printing results below.[/green]")

    payload = bundle_to_json(bundle)
    if args.output:
        _write_private_text(args.output, payload + "\n")

    _audit(
        args.audit_log,
        {
            "event": "complete",
            "dry_run": dry_run,
            "n_hypotheses": n,
            "hypothesis_ids": [h.id for h in bundle.hypotheses],
            "output": str(args.output) if args.output else None,
            **topic_fields,
        },
    )

    if args.json_only:
        print(payload)
        return 0

    _print_human(out, bundle)
    if args.output:
        out.print(
            f"\n[dim]Wrote JSON to {args.output} "
            f"(owner-only permissions when the OS allows)[/dim]"
        )
    if args.audit_log:
        out.print(
            f"[dim]Appended audit events to {args.audit_log} "
            f"(owner-only permissions when the OS allows)[/dim]"
        )
    mode = "dry-run" if dry_run else "live"
    out.print(f"[dim]hypothesis-engine v{__version__} · {mode}[/dim]")
    return 0


def estimate_calls_for_cli(n: int) -> int:
    """Exposed for tests; same as workflow helper."""
    return estimate_api_calls(n)


def _display_topic(topic: str, *, limit: int = _DISPLAY_TOPIC_MAX) -> str:
    """Shorten topic for panels; does not change the topic sent to the model."""
    t = topic.strip()
    if len(t) <= limit:
        return t
    return t[: limit - 1] + "…"


def _confirm_live(
    console: Console,
    *,
    topic: str,
    n: int,
    estimated: int,
    assume_yes: bool,
    model: str = "grok-4.5",
    base_url: str = "https://api.x.ai/v1",
    trusted_host: bool = True,
    retrieve: bool = False,
) -> bool:
    """Return True if live run should proceed."""
    endpoint_line = f"API endpoint: [bold]{base_url}[/bold]\n"
    if not trusted_host:
        endpoint_line += (
            "[bold yellow]Warning:[/bold yellow] XAI_BASE_URL is not the default "
            "api.x.ai host. Your API key and topic will be sent to this URL. "
            "Only continue if you trust that endpoint.\n"
        )
    retrieve_line = ""
    if retrieve:
        retrieve_line = (
            "Local retrieval: [bold]on[/bold] (files scored on your machine; "
            "snippets are still sent to the model with the topic).\n"
            "Not a web literature search.\n"
        )
    console.print(
        Panel.fit(
            "[bold red]LIVE MODE — THIS CAN COST MONEY[/bold red]\n\n"
            f"Topic: [bold]{_display_topic(topic)}[/bold]\n"
            f"Hypotheses: [bold]{n}[/bold]\n"
            f"Model: [bold]{model}[/bold]\n"
            f"{endpoint_line}"
            f"{retrieve_line}"
            f"Estimated xAI API calls: [bold]~{estimated}[/bold] "
            f"(background + generate + multi-check verify×{n} + tests×{n})\n\n"
            "[bold]Not a price quote.[/bold] Your bill depends on "
            "[bold]tokens used[/bold] and [bold]xAI’s current pricing[/bold] "
            "(see [link=https://console.x.ai]console.x.ai[/link] / xAI docs).\n"
            "Call count is only a rough estimate of how many API requests this run may make.\n\n"
            "Uses [bold]your[/bold] XAI_API_KEY and [bold]your[/bold] xAI credits.\n"
            "DagzTagz Hypothesis Engine does not pay for usage.\n"
            "Topics go to the API provider in live mode (not only local).\n"
            "Dry-run is free: [cyan]hypothesis-engine --dry-run \"…\"[/cyan]",
            title=f"Cost confirmation · v{__version__}",
            border_style="red",
        )
    )

    if assume_yes:
        console.print("[yellow]Proceeding without prompt (--yes).[/yellow]")
        return True

    if not sys.stdin.isatty():
        console.print(
            "[red]Refusing live mode in non-interactive session without --yes.[/red]\n"
            "Re-run with [cyan]-y[/cyan]/[cyan]--yes[/cyan] only if you accept API charges, "
            "or use [cyan]--dry-run[/cyan] (free)."
        )
        return False

    try:
        answer = input(
            "Type YES to spend credits on a live run (anything else aborts).\n"
            "After YES, please wait — do not type until results appear: "
        )
    except EOFError:
        console.print("[red]No input; aborting live run.[/red]")
        return False

    if answer.strip() == "YES":
        return True

    console.print("[yellow]Aborted. No API calls made. Use --dry-run for a free mock run.[/yellow]")
    return False


def _print_live_wait_banner(console: Console, *, estimated: int, n: int) -> None:
    """Tell the user a long multi-call run is in progress; discourage extra input."""
    console.print(
        Panel.fit(
            "[bold yellow]Please wait — live run in progress[/bold yellow]\n\n"
            f"About [bold]~{estimated}[/bold] xAI API calls for [bold]{n}[/bold] hypothesis(es).\n"
            "Each step can take [bold]tens of seconds[/bold] (sometimes longer).\n"
            "Progress lines will appear below as steps finish.\n\n"
            "[bold]Do not type anything[/bold] until you see results "
            "(extra keypresses will not speed this up).\n"
            "If you need to cancel, use [cyan]Ctrl+C[/cyan] once.",
            title="Working…",
            border_style="yellow",
        )
    )


def _friendly_error(exc: BaseException) -> str:
    """Map common failures to short, key-safe messages."""
    text = str(exc)
    lowered = text.lower()
    name = type(exc).__name__

    if isinstance(exc, AuditEncryptionUnavailable) or "audit_log_key is set" in lowered:
        return str(exc)

    if "missing xai_api_key" in lowered or (
        "xai_api_key" in lowered and "missing" in lowered
    ):
        return (
            "Missing XAI_API_KEY. Copy .env.example to .env, set your key, "
            "and re-run. Never put the key in the topic string. See getting-started.md."
        )

    if "authentication" in lowered or "unauthorized" in lowered or "401" in text:
        return (
            "xAI rejected the API key (unauthorized). Check XAI_API_KEY in .env, "
            "create a new key at https://console.x.ai if needed."
        )

    if "429" in text or "rate limit" in lowered:
        return "xAI rate limit hit. Wait and try again, or reduce -n."

    if "insufficient" in lowered or "quota" in lowered or "billing" in lowered:
        return (
            "xAI account may lack credits or billing. Check https://console.x.ai "
            "and use --dry-run until resolved."
        )

    if (
        name in {"LLMError", "JSONDecodeError"}
        or "could not parse json" in lowered
        or "invalid \\escape" in lowered
        or "invalid escape" in lowered
    ):
        return (
            "The model returned text that was not valid JSON "
            "(often a bad backslash in a long explanation). "
            "Please run the same command again — the client will retry once automatically. "
            f"Details: {text[:280]}"
        )

    if "validation error" in lowered or name == "ValidationError":
        return (
            "The model returned JSON that did not match the expected schema "
            "even after soft normalization. Try again, or reduce -n. "
            f"Details: {text[:280]}"
        )

    # Avoid dumping huge traces; never echo env values / key-shaped tokens
    redacted = text
    for needle in ("sk-", "xai-", "api_key", "apikey", "bearer "):
        if needle in redacted.lower():
            redacted = (
                f"{name}: [details redacted — possible secret-like text in error]"
            )
            break
    if len(redacted) > 400:
        redacted = redacted[:400] + "…"
    return f"{name}: {redacted}" if not redacted.startswith(name) else redacted


def _chmod_private(path: Path) -> None:
    """Best-effort owner-only mode (ignore if OS/filesystem disallows)."""
    try:
        os.chmod(path, _PRIVATE_FILE_MODE)
    except OSError:
        pass


def _write_private_text(path: Path, text: str) -> None:
    """Write/replace a file as mode 0600 (not group/world-readable)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(path, flags, _PRIVATE_FILE_MODE)
    # fdopen takes ownership of fd (closes it when the with-block ends).
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    # Existing files keep prior mode on open; re-tighten after write.
    _chmod_private(path)


def _audit(path: Path | None, event: dict) -> None:
    if path is None:
        return
    payload = {
        "ts": datetime.now(UTC).isoformat(),
        **event,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Create new audit files as 0600; re-tighten each append (covers old 0644/0664 logs).
    if not path.exists():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, _PRIVATE_FILE_MODE)
        os.close(fd)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    _chmod_private(path)


def _print_human(console: Console, bundle: object) -> None:
    from hypothesis_engine.models import HypothesisBundle

    assert isinstance(bundle, HypothesisBundle)
    phase = bundle.meta.get("phase", 1)
    retrieval_tag = bundle.meta.get("retrieval")
    if retrieval_tag in (None, "off"):
        retrieval_tag = None
    schema_bits = [
        s
        for s in (
            bundle.meta.get("verification"),
            bundle.meta.get("tests"),
            retrieval_tag,
        )
        if s
    ]
    title = f"DagzTagz Hypothesis Engine (Phase {phase})"
    if schema_bits:
        title += " · " + " + ".join(str(s) for s in schema_bits)
    console.print(
        Panel.fit(
            f"[bold]{bundle.topic}[/bold]\n[dim]{bundle.overall_notes}[/dim]",
            title=title,
        )
    )
    console.print("\n[bold]Background[/bold]")
    grounding = getattr(bundle.background, "grounding", "model_only")
    console.print(f"[dim]grounding: {grounding}[/dim]")
    console.print(bundle.background.summary)
    if bundle.background.known_limitations:
        console.print(
            "[dim]Limitations: " + "; ".join(bundle.background.known_limitations) + "[/dim]"
        )
    sources = getattr(bundle.background, "sources", None) or []
    if sources:
        src_table = Table(title="Local sources (RAG v0)", show_lines=False)
        src_table.add_column("Id", style="bold")
        src_table.add_column("Title")
        src_table.add_column("Backend")
        src_table.add_column("Score")
        src_table.add_column("Snippet")
        for s in sources:
            score = "" if s.score is None else f"{s.score:.3f}"
            snip = s.snippet if len(s.snippet) <= 120 else s.snippet[:119] + "…"
            src_table.add_row(s.id, s.title, s.backend, score, snip)
        console.print(src_table)

    for hyp in bundle.hypotheses:
        console.print(f"\n[bold cyan]{hyp.id}[/bold cyan]  {hyp.statement}")
        console.print(f"  [dim]Rationale:[/dim] {hyp.rationale}")
        ver = next((v for v in bundle.verifications if v.hypothesis_id == hyp.id), None)
        if ver:
            console.print(
                f"  [bold]Verdict:[/bold] {ver.verdict.value} "
                f"({ver.confidence.value}) — {ver.consistency_notes}"
            )
            if ver.checks:
                check_table = Table(
                    title=f"Multi-check for {hyp.id}",
                    show_header=True,
                    show_lines=False,
                )
                check_table.add_column("Check", style="bold")
                check_table.add_column("Status")
                check_table.add_column("Summary")
                for c in ver.checks:
                    status = c.status.value
                    if status == "pass":
                        status_disp = f"[green]{status}[/green]"
                    elif status == "fail":
                        status_disp = f"[red]{status}[/red]"
                    elif status == "warn":
                        status_disp = f"[yellow]{status}[/yellow]"
                    else:
                        status_disp = f"[dim]{status}[/dim]"
                    check_table.add_row(c.id, status_disp, c.summary)
                console.print(check_table)
        tests = [t for t in bundle.tests if t.hypothesis_id == hyp.id]
        if tests:
            table = Table(title=f"Tests for {hyp.id}", show_lines=True)
            table.add_column("Title", style="bold")
            table.add_column("Method")
            table.add_column("Measures")
            table.add_column("Falsify if…")
            table.add_column("Diff / time")
            for t in tests:
                duration = t.rough_duration or "—"
                table.add_row(
                    t.title,
                    t.method,
                    t.what_is_measured or "—",
                    t.what_would_falsify,
                    f"{t.rough_difficulty.value} / {duration}",
                )
            console.print(table)
            for t in tests:
                bits: list[str] = []
                if t.controls:
                    bits.append("controls: " + "; ".join(t.controls))
                if t.materials_or_data:
                    bits.append("materials/data: " + "; ".join(t.materials_or_data))
                if t.addresses_checks:
                    bits.append("addresses checks: " + ", ".join(t.addresses_checks))
                if t.notes:
                    bits.append("notes: " + "; ".join(t.notes))
                if bits:
                    console.print(f"  [dim]· {t.title}:[/dim] " + " | ".join(bits))

    powered = ""
    if not bundle.meta.get("dry_run"):
        powered = " Powered by Grok (xAI)."
    console.print(
        "\n[dim]DagzTagz Hypothesis Engine — experimental research aid; "
        f"not established science. Not an official xAI product.{powered}[/dim]"
    )


if __name__ == "__main__":
    sys.exit(main())
