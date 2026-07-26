# Building a local library for retrieval (RAG v0)

**DagzTagz Hypothesis Engine** can optionally ground its **background brief** on files that live **on your machine** (`--retrieve`). That is **privacy-first**: no remote paper API and no automatic web scrape in v0.

This guide explains how to build a simple **local reservoir** (corpus) of notes and papers, and how to point the engine at it.

> **Not a finished product.** Local retrieval is **not** a full literature review. Always verify science with experts and proper methods.

Related: [design-rag-v0.md](design-rag-v0.md) · [CHANGELOG](../CHANGELOG.md) · [getting-started.md](../getting-started.md)

---

## What the engine can read today (v0)

| Supported | Not supported (yet) |
|-----------|---------------------|
| `.txt` | `.pdf` (convert first — see below) |
| `.md` / `.markdown` | `.docx`, images, arbitrary binary |
| Files you pass with `--source` | Nested folders inside `--corpus` (v0 is **non-recursive**) |
| Direct children of `--corpus DIR` | Remote URLs / OpenAlex / “search the web” |

**PDFs are fine to *keep* on disk** — you just convert them to text/markdown before retrieval.

---

## Recommended folder layout

Keep the library **outside** the public git repo if it contains private notes or licensed PDFs:

```text
~/hypothesis-corpus/          # your private library (example path)
  pdfs/                       # original PDFs (engine ignores these in v0)
    smith2020-bleaching.pdf
    my-preprint.pdf
  text/                       # ← point --corpus here
    smith2020-bleaching.txt
    my-preprint.txt
    lab-notes-2026.md
```

Do **not** commit copyrighted PDFs or sensitive lab data to GitHub unless you intend them to be public.

If you place a library **inside** the clone, common folder names (`hypothesis-corpus/`, `corpus/`, `local-corpus/`, `my_notes/`) are listed in **`.gitignore`** so they are not committed by accident. Prefer a path **outside** the repo when material is private or licensed.

---

## Step-by-step: create the reservoir

### 1. Create the folders

```bash
mkdir -p ~/hypothesis-corpus/pdfs
mkdir -p ~/hypothesis-corpus/text
```

Use any path you like; these commands use `~/hypothesis-corpus` as an example.

### 2. Collect material you are allowed to keep

Examples of legitimate sources:

- Open-access papers you may download  
- Your own notes, drafts, and preprints  
- PDFs available under your institutional / personal license  

Save downloads into `pdfs/` (or export from Zotero/Mendeley/etc. into that folder).

### 3. Convert PDFs → `.txt` or `.md`

The engine does **not** parse PDF binary in v0. Convert first.

**Using `pdftotext` (Poppler)** — common on Linux:

```bash
# Debian/Ubuntu (if needed):
# sudo apt install poppler-utils

pdftotext -layout \
  ~/hypothesis-corpus/pdfs/smith2020-bleaching.pdf \
  ~/hypothesis-corpus/text/smith2020-bleaching.txt
```

**Batch-convert a folder of PDFs:**

```bash
cd ~/hypothesis-corpus/pdfs
for f in *.pdf; do
  [ -f "$f" ] || continue
  pdftotext -layout "$f" "../text/${f%.pdf}.txt"
done
```

**Without `pdftotext`:** open the PDF, copy text into a new file such as  
`~/hypothesis-corpus/text/my-paper.md`, or use another offline export tool.

### 4. Add plain notes (optional but useful)

Write or paste your own markdown notes:

```bash
nano ~/hypothesis-corpus/text/lab-notes.md
```

Clear filenames show up as **Title** in the engine’s Sources table.

### 5. Run the engine against the text folder

From your engine checkout (with venv active):

```bash
cd ~/dagztagz-hypothesis-engine
source .venv/bin/activate

# Free dry-run — no xAI, no charges
hypothesis-engine --dry-run --retrieve \
  --corpus ~/hypothesis-corpus/text \
  -n 1 \
  "coral bleaching under heat stress"
```

**Single files instead of a directory:**

```bash
hypothesis-engine --dry-run --retrieve \
  --source ~/hypothesis-corpus/text/smith2020-bleaching.txt \
  --source ~/hypothesis-corpus/text/lab-notes.md \
  "your topic"
```

**Live mode** (costs xAI credits; still only *local* files for retrieval, but **topic + snippets go to xAI**):

```bash
hypothesis-engine --retrieve \
  --corpus ~/hypothesis-corpus/text \
  -n 1 \
  "your topic"
```

---

## CLI flags (quick reference)

| Flag | Meaning |
|------|---------|
| `--retrieve` | Turn on local-file retrieval for the background step |
| `--corpus DIR` | Search **direct** `.txt`/`.md` children of `DIR` (repeatable) |
| `--source FILE` | Include one file (repeatable) |
| `--retrieve-k N` | Max passages to keep (1–10, default 5) |
| `--dry-run` | No API calls; free mock/path demo |

Live + `--retrieve` **requires** at least one `--corpus` or `--source`.  
Dry-run + `--retrieve` without files uses **mock** passages so you can demo the feature.

---

## Limits and tips (v0)

| Topic | Detail |
|--------|--------|
| File types | `.txt`, `.md`, `.markdown` only |
| Corpus depth | **Non-recursive** — put files directly in the corpus folder |
| Size | Very large files are skipped (see implementation caps) |
| How ranking works | Simple keyword overlap with your topic (not embeddings) |
| Empty hits | Background may fall back to model-only style limits; check `meta.retrieval_status` |
| Privacy | Retrieval is local; **live** mode still sends topic + snippets to the model provider |
| Secrets | Never put API keys in note files |
| Git | Prefer keeping `hypothesis-corpus/` **out of** the public repository |

---

## Example: check that a file is found

```bash
# Should list your converted notes
ls ~/hypothesis-corpus/text

hypothesis-engine --dry-run --json-only --retrieve \
  --corpus ~/hypothesis-corpus/text \
  -n 1 "photosynthesis" \
  | python -c "import json,sys; d=json.load(sys.stdin); print(d['meta']); print([(s['id'], s['title']) for s in d['background']['sources']])"
```

You want `meta.retrieval` like `rag_v0_local` and at least one source title matching your files (or mock sources if the folder was empty).

---

## What we might add later (not promised)

- Native PDF text extraction inside the engine  
- Recursive corpus folders  
- Optional remote literature APIs (separate opt-in, not the privacy-first default)  

Until then: **PDF → text/markdown → `--corpus` / `--source`**.

---

## Safety reminder

- Prefer **`--dry-run`** while building your library.  
- Local retrieval is a **research aid**, not peer review or medical/legal advice.  
- You are responsible for lawful use of any PDFs and notes you store and convert.
