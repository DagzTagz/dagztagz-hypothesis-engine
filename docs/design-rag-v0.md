# Design: RAG v0 — local files only (privacy-first)

**Status:** implementing with engine **0.3.0**  
**Decision:** Option **A — local corpus / files only**. No literature API, no remote URL fetch in v0.

---

## Goals

1. Opt-in retrieval from **files on the user’s machine** to ground the **background brief**.
2. Fail closed on honesty: **do not invent** papers, DOIs, or quotes not present in retrieved text.
3. Default path unchanged when retrieval is off (model-only background, same as ≤0.2.1).
4. Dry-run works **offline** with mock passages (and can score real local files if provided).
5. Clear metadata: `meta.retrieval`, backend, status, passage count.

## Non-goals (v0)

- OpenAlex / Semantic Scholar / web search  
- Fetching arbitrary URLs  
- Vector DB product or embeddings dependency  
- Grounding every pipeline step (verify/tests stay as-is)  
- Claiming a full literature review  

## User interface

```bash
# Opt-in local retrieval
hypothesis-engine --retrieve --corpus ./my_notes -n 1 "topic"
hypothesis-engine --retrieve --source a.md --source b.txt "topic"

# Dry-run (no xAI); mock sources if no files, or score local files if given
hypothesis-engine --dry-run --retrieve --corpus ./notes "topic"
```

| Flag | Meaning |
|------|---------|
| `--retrieve` | Enable local retrieval |
| `--corpus DIR` | Directory of `.txt` / `.md` (non-recursive in v0, or shallow — see impl) |
| `--source PATH` | Single file (repeatable) |
| `--retrieve-k N` | Max passages (1–10, default 5) |

If `--retrieve` is set with **no** `--corpus` / `--source`: **error** (except dry-run may use mocks only).

## Privacy

| Concern | Rule |
|---------|------|
| Query / files | Stay **local** for retrieval scoring |
| Live mode | Topic + **snippets** still go to **xAI** (user opt-in to live) |
| Audit log | Do **not** dump full file contents; topic rules unchanged |
| Paths | Only user-supplied paths; skip unreadable / oversized files |

## Data model

- `RetrievedPassage`: id, title, identifier (path), snippet, year (optional/null), backend=`local`|`mock`, score  
- `BackgroundBrief.sources`, `BackgroundBrief.grounding` = `model_only` | `retrieved` | `mixed`  
- `meta.retrieval` = `off` | `rag_v0_local`  
- `meta.retrieval_backend`, `meta.retrieval_status`, `meta.n_passages`

## Retrieval algorithm (v0 — intentionally simple)

1. Collect candidate files (`.txt`, `.md` only).  
2. Read text with size cap; build one passage per file (title = filename).  
3. Score by **keyword overlap** with the topic (token set intersection / simple TF).  
4. Return top‑k passages with clipped snippets.  

No embeddings dependency in v0 (keeps install light and offline-friendly).

## Pipeline

```
topic → [optional local retrieve] → background (prompt ± passages)
      → generate → multi-check → richer tests
```

xAI call count unchanged (`2+2N`); local I/O is extra free work on disk.

## Failure modes

| Case | Behavior |
|------|----------|
| Retrieve off | Identical to pre-0.3 (sources empty, grounding model_only) |
| Retrieve on, zero usable files / zero score (live) | Empty passages; background model-only + limitation text; `retrieval_status=empty` |
| Dry-run, zero usable files | Synthetic mock passages; `retrieval_status=ok_mock`, `retrieval_backend=mock` (demo only) |
| Unreadable file | Skip file; continue |
| Dry-run, no files | Same as zero usable: mock + `ok_mock` |

## Later (not v0)

- Recursive corpus walk, PDF, OpenAlex plugin, embeddings, cite-checker on model output  

## Success criteria

User can point at a private folder of notes, run dry-run or live, see **Sources** from those files, and trust that nothing was scraped from the public web for retrieval.

## User guide

How to build a private PDF/notes reservoir and convert files for v0:

→ **[local-corpus.md](local-corpus.md)**
