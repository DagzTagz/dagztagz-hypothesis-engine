# Local library for retrieval (RAG v0)

Use **your files** to ground the **background** step. Privacy-first: **no remote paper API**, no automatic web search.

> **Not a finished product** and **not** a full literature review.

Also see: [getting-started.md](../getting-started.md) · [design-rag-v0.md](design-rag-v0.md)

---

## What works in v0

| Supported | Not supported |
|-----------|----------------|
| `.txt`, `.md`, `.markdown` | Raw `.pdf` (convert first) |
| `--corpus DIR` (files **directly** in that folder) | Nested subfolders |
| `--source FILE` (repeatable) | URLs / OpenAlex / “search the web” |

Keep private notes **outside** the git clone when you can.  
In-repo names `hypothesis-corpus/`, `corpus/`, `local-corpus/`, `my_notes/` are **gitignored**.

---

## Quick path (notes only)

```bash
# 0) engine ready
cd ~/dagztagz-hypothesis-engine
source .venv/bin/activate

# 1) library folders
mkdir -p ~/hypothesis-corpus/pdfs
mkdir -p ~/hypothesis-corpus/text

# 2) add a note that uses words from your topic
echo "Coral bleaching increases with sea surface temperature stress." \
  > ~/hypothesis-corpus/text/coral-notes.md

# 3) free dry-run with retrieval
hypothesis-engine --dry-run --retrieve \
  --corpus ~/hypothesis-corpus/text \
  -n 1 \
  "coral bleaching temperature"
```

**Check real hit vs dry-run mock:**

```bash
hypothesis-engine --dry-run --json-only --retrieve \
  --corpus ~/hypothesis-corpus/text \
  -n 1 "coral bleaching temperature" \
  | python -c "import json,sys; d=json.load(sys.stdin); print(d['meta'].get('retrieval_status'), d['meta'].get('retrieval_backend')); print([(s['title'], s['backend']) for s in d['background']['sources']])"
```

| Result | Meaning |
|--------|---------|
| `ok` + `local` + your filename | Keyword match — your file was used |
| `ok_mock` + `mock` + `mock-…` | No usable match; dry-run filled demo sources |
| Live only: `empty` | No match; no Sources table; model-only background |

---

## Configuration & optionality (step by step)

### A — Retrieval off (default)

```bash
hypothesis-engine --dry-run -n 1 "your topic"
# live:
# hypothesis-engine -n 1 "your topic"
```

No local files read. Background = model knowledge only.

### B — Retrieval on + one folder

```bash
hypothesis-engine --dry-run --retrieve \
  --corpus ~/hypothesis-corpus/text \
  -n 1 "your topic"
```

- Scans **only top-level** `.txt`/`.md` in that directory  
- Keeps up to **5** passages by default  
- Files with **no topic-word overlap** are dropped (score 0)

### C — Specific files only

```bash
hypothesis-engine --dry-run --retrieve \
  --source ~/hypothesis-corpus/text/coral-notes.md \
  --source ~/hypothesis-corpus/text/methods.md \
  -n 1 "your topic"
```

### D — Folder + extra files + more hits

```bash
hypothesis-engine --dry-run --retrieve \
  --corpus ~/hypothesis-corpus/text \
  --source ~/Desktop/extra-note.md \
  --retrieve-k 8 \
  -n 2 "your topic"
```

| Flag | Optional? | Role |
|------|-----------|------|
| `--retrieve` | required to enable | Turns local retrieval on |
| `--corpus DIR` | optional* | Directory of notes (repeatable) |
| `--source FILE` | optional* | One file (repeatable) |
| `--retrieve-k N` | optional | Max passages, **1–10** (default **5**) |
| `--dry-run` | optional | Free, no xAI |
| `-n 1..5` | optional | Hypothesis count (default 2) |
| `-o out.json` | optional | Write full JSON (owner-only mode when possible) |
| `--json-only` | optional | JSON on stdout (good for scripts) |

\*Live + `--retrieve` needs **at least one** `--corpus` or `--source`.  
Dry-run may omit both and will use **mock** sources (`ok_mock`).

### E — Live + library (costs money)

```bash
# interactive YES prompt
hypothesis-engine --retrieve \
  --corpus ~/hypothesis-corpus/text \
  -n 1 "your topic"

# non-interactive (only if you accept xAI charges)
hypothesis-engine -y --retrieve \
  --corpus ~/hypothesis-corpus/text \
  -n 1 "your topic"
```

- Retrieval still uses **only local files**  
- **Topic + chosen snippets** are sent to **xAI** in live mode  
- No match → `retrieval_status=empty` (no mock sources)

### F — JSON / scripting

```bash
hypothesis-engine --dry-run --json-only --retrieve \
  --corpus ~/hypothesis-corpus/text \
  -n 1 "your topic" -o /tmp/he-out.json

# key fields
python -c "import json; d=json.load(open('/tmp/he-out.json')); print(d['meta']['retrieval_status'], d['meta']['n_passages']); print(d['background']['grounding'])"
```

---

## Add PDFs to the library

Engine does **not** read PDF binary in v0. Convert → `text/`.

### 1. Save PDFs

```bash
mkdir -p ~/hypothesis-corpus/pdfs
# download or copy papers into pdfs/ (only material you may keep)
```

### 2. Install converter (Linux example)

```bash
# Debian/Ubuntu
sudo apt install poppler-utils   # provides pdftotext
```

### 3. Convert one file

```bash
pdftotext -layout \
  ~/hypothesis-corpus/pdfs/smith2020.pdf \
  ~/hypothesis-corpus/text/smith2020.txt
```

### 4. Convert a whole folder

```bash
cd ~/hypothesis-corpus/pdfs
for f in *.pdf; do
  [ -f "$f" ] || continue
  pdftotext -layout "$f" "../text/${f%.pdf}.txt"
done
ls ~/hypothesis-corpus/text
```

### 5. Run retrieve as usual

```bash
hypothesis-engine --dry-run --retrieve \
  --corpus ~/hypothesis-corpus/text \
  -n 1 "your scientific topic"
```

No `pdftotext`? Open the PDF → copy text → save as `~/hypothesis-corpus/text/name.md`.

---

## Suggested folder layout

```text
~/hypothesis-corpus/
  pdfs/          # originals (ignored by the engine)
  text/          # ← point --corpus here
    paper1.txt
    lab-notes.md
```

---

## Flag cheat sheet

| Flag | Meaning |
|------|---------|
| `--retrieve` | Enable local-file retrieval for background |
| `--corpus DIR` | Non-recursive directory of `.txt`/`.md` |
| `--source FILE` | Explicit file (repeatable) |
| `--retrieve-k N` | Max passages (1–10, default 5) |

---

## Limits (v0)

| Topic | Detail |
|--------|--------|
| Ranking | Keyword overlap with the topic (not embeddings) |
| Zero score | File ignored if it shares **no** topic words |
| Size / count | Oversized files skipped; scan cap applies |
| Privacy | Retrieve is local; **live** still sends topic + snippets to xAI |
| Secrets | Never put API keys in note files |

---

## Safety

- Prefer **`--dry-run`** while building the library  
- Research aid only — not peer review or professional advice  
- You are responsible for lawful use of PDFs and notes you store  
