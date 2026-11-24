# State-machine audit, November 2026: dagztagz-hypothesis-engine

This page is the dagztagz-hypothesis-engine part of the full disclosure for the
November 2026 implicit-state-machine audit of the DagzTagz repositories. The
complete report, with every finding and its reproduction, is in
[Dagz-Scaffold/docs/audits/2026-11-state-machine-audit.md](https://github.com/DagzTagz/Dagz-Scaffold/blob/main/docs/audits/2026-11-state-machine-audit.md).
It also has the remediation status of all 13 findings across the four repositories.

Audited commit: [`f786e92`](https://github.com/DagzTagz/dagztagz-hypothesis-engine/tree/f786e9263ba73d83548bf0a4e90b19e2e22c96c6).

Neither finding here was a security vulnerability. Neither exposed a topic, a key or a file.
F6 made the audit log incomplete. F10 was a maintainability risk with no observed wrong output.

| Finding | Priority | What was wrong | Fix |
|---|---|---|---|
| F6 | Med | A run's audit log could end with `start` and nothing after it. This happened when `-o` could not be written, and on Ctrl-C. Progress could also stop at `[4/6]` when the model returned an unusable hypothesis. **Reproduced.** | [`8c052ce`](https://github.com/DagzTagz/dagztagz-hypothesis-engine/commit/8c052ce) |
| F10 | Low | The six retrieval fields in `meta` were free strings, built separately by the live and dry-run paths. vesper-bind matches those strings. | [`8239421`](https://github.com/DagzTagz/dagztagz-hypothesis-engine/commit/8239421) |
| (side bug) | Low | Three error paths printed the literal text `[red]Error:[/red]`. | [`a255b6a`](https://github.com/DagzTagz/dagztagz-hypothesis-engine/commit/a255b6a) |

## What changed

- **F6.** `cli.Outcome` has four values: `complete`, `error`, `output_failed` and `interrupted`.
  - The terminal audit event is written from a single `finally` block, so every `start` is followed by exactly one of them.
  - `output_failed` and `interrupted` are new event names. A tool that reads the audit log should accept them.
  - Ctrl-C still exits the way it did before. The `interrupted` event is written first.
  - The progress total is recomputed after generation from the hypotheses that survived.
- **F10.** Two StrEnums replace the free strings:
  - `models.Retrieval`: `skipped`, `empty`, `ok`, `ok_mock`.
  - `models.Grounding`: `model_only`, `retrieved`, `mixed`.
  - `workflow.retrieval_meta()` is now the only place that builds the retrieval fields.
  - Every string value is unchanged. Dry-run JSON is byte-for-byte the same as before, and vesper-bind needs no change.
  - The values are documented as a stable contract in [docs/design-rag-v0.md](../design-rag-v0.md).
- **Side bug.** The `[audit]` install hint is now escaped, and the red label renders as colour instead of as text.

## Do I need to do anything?

No action is needed. If you parse `audit.jsonl`, accept the two new terminal event names.
