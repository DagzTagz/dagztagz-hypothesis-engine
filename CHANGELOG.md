# Changelog

All notable changes to **DagzTagz Hypothesis Engine** are documented here.

This project is **early, iterative open source** — not a finished product. We disclose privacy and security-relevant changes **up front** so people who already cloned, pip-installed, or downloaded a ZIP can **update and harden** their local copies.

The format is based on [Keep a Changelog](https://keepachangelog.com/).  
Versions follow [Semantic Versioning](https://semver.org/) while pre-1.0 (`0.x` = public iterations; expect breaking changes until 1.0).

---

## [0.3.1] — 2026-07-28 — local retrieval upgrade + formal 0.3 line

Builds on RAG v0 for real paper libraries. Still **local only** — not a web literature review.

### Added / improved

- **Chunking** of long notes so a full paper can contribute multiple scored passages
- **Recursive corpus walk** (depth-limited) under `--corpus`
- **Optional PDF text extract** via `pip install 'dagztagz-hypothesis-engine[pdf]'` (`pypdf`); corrupt PDFs are skipped
- **Clearer Sources table**: title, score, short path, snippet; retrieval status line
- **Privacy paths**: source `identifier` rewrites home to `~/…` by default; `--retrieve-full-paths` for absolutes
- **PDF skip warnings** on progress (filename + reason; no home paths)
- **Symlink jail**: corpus walk skips paths that resolve outside the corpus root (warn by basename)
- **Audit log**: `retrieve` true/false on events; `n_passages` on complete (no snippets/paths)
- **Live disclosure**: stronger cost-panel wording when `--retrieve` is on (topic + matched snippets leave the machine)
- Schema tag: `meta.retrieval = rag_v0_1_local`

### Docs / release

- User guide remains [docs/local-corpus.md](docs/local-corpus.md)
- Package version **0.3.1** (GitHub Release targets this line)

### Privacy

- Unchanged: no remote paper API; live mode still sends topic + snippets to xAI

---

## [0.3.0] — 2026-07-26 — RAG v0 (local files only)

Privacy-first optional retrieval for the **background** step. **Not** a web literature search.

### Added

- **`--retrieve`** with **`--corpus DIR`** and/or **`--source FILE`** (repeatable).
- **`--retrieve-k`** (1–10, default 5): max local passages.
- Local scorer over **`.txt` / `.md`** only (non-recursive corpus dirs); size/file caps; no network for retrieval.
- `RetrievedPassage` + `BackgroundBrief.sources` / `grounding`.
- Dry-run: mock passages if no files; real local scoring when files are given.
- Design note: [docs/design-rag-v0.md](docs/design-rag-v0.md).
- User guide: [docs/local-corpus.md](docs/local-corpus.md) (build a local library, convert PDFs, run `--corpus`).
- CLI **Sources** table; `meta.retrieval = rag_v0_local` when enabled.

### Privacy

- Retrieval reads **only paths you pass**. No remote paper API in v0.
- **Live mode still sends topic + snippets to xAI** when you run without `--dry-run`.
- Audit log still does not dump full file contents by default.

### Upgrade

```bash
git pull && pip install -e ".[dev]"
hypothesis-engine --version   # 0.3.0
# example:
hypothesis-engine --dry-run --retrieve --corpus ./my_notes -n 1 "your topic"
```

---

## [0.2.1] — 2026-07-24 — polish patch

Hardening and UX polish on top of **0.2.0**. No new science features. Still iterative / not a finished product.

### Fixed / hardened

- **Soft-normalize model JSON** for verify + tests: bad enums (`verdict`, `confidence`, `check status`, `rough_difficulty`) default safely instead of crashing the run; unknown test `method` → `analysis`.
- **Clip runaway text/lists** from model output (field and list caps) to limit memory/log bloat.
- **Skip unusable hypothesis rows** when one object in the batch is broken (still require at least one good hypothesis).
- **Live cost panel:** show model + API endpoint; **warn** if `XAI_BASE_URL` is not the trusted `api.x.ai` host (key + topic would leave default xAI).
- **Display-truncate** long topics in the live confirmation panel (full topic still used for the run).
- **CLI:** `-n` restricted to 1–5 at argparse; footer shows `v0.2.1` and dry-run/live; remind owner-only file modes when writing `-o` / audit log.
- **Friendlier errors** for schema validation; avoid echoing secret-like substrings in error text.
- Bundle **`meta.engine_version`** set to the package version.

### Privacy / safety notes

- No change to audit topic hashing/encryption model.
- Live mode still sends the full topic to the configured API host — the new endpoint warning makes mis-set `XAI_BASE_URL` harder to miss.
- Output/audit **`0600`** behavior from 0.2.0 unchanged.

### Upgrade

```bash
git pull   # or re-download the 0.2.1 tag/ZIP when published
pip install -e ".[dev]"
hypothesis-engine --version   # expect 0.2.1
```

No mandatory `chmod` beyond what 0.2.0 already recommended for older files.

---

## [0.2.0] — 2026-07-23 — second public iteration

**Think of this as “version 2” of the public project:** Phase 2 features plus a **local privacy fix** that matters if you still have files from older runs.

### Privacy fix (action needed if you ran older builds)

**Issue:** Before `0.2.0`, files created by `-o` / `--output` and `--audit-log` often used the default umask (commonly mode **`0644` or `0664`**). On multi-user machines that means **other local accounts** could read those files (“group/world-readable” in Unix terms — not “the whole internet,” but **any user on the same computer** who can open the path).

**What was in those files:**

| File | Typical content risk |
|------|----------------------|
| `-o out.json` | Full **plaintext** topic, hypotheses, multi-check, suggested tests |
| `--audit-log audit.jsonl` | Run metadata; topics hashed or encrypted by default, but still a local paper trail |

**What we fixed in code (0.2.0+):**

- New and rewritten `-o` outputs are created as mode **`0600`** (owner read/write only).
- `--audit-log` files are created as **`0600`**; each append **re-tightens** mode to `0600` (helps existing loose logs).

**What you should do if you used 0.1.x or an older ZIP/clone:**

```bash
cd /path/to/dagztagz-hypothesis-engine   # or wherever your files live

# 1) Pull / re-download / reinstall so you have 0.2.0+ code
git pull   # or download a fresh ZIP of main / the 0.2.0 release

# 2) Reinstall into your venv
source .venv/bin/activate
pip install -e ".[dev]"   # or pip install -e ".[audit]" as you prefer

# 3) Harden ANY existing local outputs you care about
chmod 600 .env out.json audit.jsonl 2>/dev/null || true
# add any other -o paths you used

# 4) Confirm
stat -c '%a %n' .env out.json audit.jsonl
# expect 600 for each file that exists
```

This is **local OS hygiene**, not encryption and not a cloud breach. Full-disk encryption and account lock still matter for stronger threats.

See also [SECURITY.md — Privacy notices for existing installs](SECURITY.md#privacy-notices-for-existing-installs) and [getting-started.md — File permissions](getting-started.md#file-permissions-owner-only).

### Added (Phase 2 product slices included in this iteration)

- **Multi-check verification** (`meta.verification = multi_check_v1`): consistency, testability, confounds, prior_knowledge.
- **Richer experiment suggestions** (`meta.tests = richer_tests_v1`): what is measured, controls, materials/data, addresses_checks, rough duration.

### Changed

- CLI writes private output/audit files as **`0600`**.
- Docs: README, getting-started, SECURITY privacy notice; package version **0.2.0**.

### Security / honesty notes

- Still **alpha research aid**, not established science, not an official xAI product.
- **Live mode** still sends topics to xAI under **your** key; file modes do not change that.
- Dry-run remains free and offline.

---

## [0.1.0] — 2026-07 — first public MVP iteration

- Phase 1 single workflow: background → generate → verify → suggest tests.
- Dry-run mocks, live xAI path with cost confirmation, optional audit log (hash / encrypt / plaintext opt-in).
- CI (pytest + ruff), Dependabot, SECURITY / CONTRIBUTING / getting-started.
- Default audit and `-o` file modes depended on umask (**often group/world-readable**) — **fixed in 0.2.0**.

---

## Links

- Repository: https://github.com/DagzTagz/dagztagz-hypothesis-engine  
- Security policy: [SECURITY.md](SECURITY.md)  
- ZIP of latest `main`: https://github.com/DagzTagz/dagztagz-hypothesis-engine/archive/refs/heads/main.zip  
