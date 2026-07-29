# Your private notes library (local retrieval)

This guide shows how to give **DagzTagz Hypothesis Engine** a folder of **your own notes** so the **background** step can use them.

You do **not** need this for a normal dry-run or live run. It is **optional**.

---

## Plain English: what this is

| Without local notes | With local notes (`--retrieve`) |
|---------------------|----------------------------------|
| Background comes only from the AI’s built-in knowledge | Background can also use text from **files on your computer** |
| Nothing is read from a library folder | Only files **you** point at are read |

Important limits (so expectations stay honest):

- This is **not** searching Google or PubMed.
- This is **not** a full literature review.
- The engine reads **`.txt` and `.md`**, and **`.pdf` if you install PDF support** (see below).
- Files/chunks must share some **words with your topic**, or they are skipped.
- Long files are **split into chunks** so one paper can contribute more than one hit.
- `--corpus` walks **subfolders** (depth-limited), not only the top level.
- Prefer keeping your library **outside** the git repo (example: `~/hypothesis-corpus`).

Full install / first run: [getting-started.md](../getting-started.md).

---

## The folder you’ll use

Think of one place on your machine for “stuff the engine can read”:

```text
~/hypothesis-corpus/
  text/     ← put .txt and .md notes HERE (this is what --corpus points at)
  pdfs/     ← optional: store original PDFs here (engine ignores them until converted)
```

On this machine that is:

```text
/home/YOUR_USERNAME/hypothesis-corpus/text
```

(or `~/hypothesis-corpus/text` — same thing)

You can use any path you like; the examples below use `~/hypothesis-corpus`.

---

## Setup in 4 steps (first time)

Do these in order.

### Step 1 — Open a terminal in the engine project

```bash
cd ~/dagztagz-hypothesis-engine
source .venv/bin/activate
```

(If you have not installed yet, follow [getting-started.md](../getting-started.md) first.)

### Step 2 — Create the library folders

```bash
mkdir -p ~/hypothesis-corpus/text
mkdir -p ~/hypothesis-corpus/pdfs
```

### Step 3 — Add a simple note

Write a short note that uses words from the topic you care about.  
Example for a photosynthesis topic:

```bash
echo "Chlorophyll absorbs light. Photosynthesis efficiency depends on the light spectrum." \
  > ~/hypothesis-corpus/text/notes.md
```

Or open an editor and write more:

```bash
nano ~/hypothesis-corpus/text/notes.md
```

Save as **`.md` or `.txt`** under **`~/hypothesis-corpus/text`**  
(subfolders are OK now — the engine walks them within a depth limit).

### Step 4 — Run a free test (dry-run + retrieve)

```bash
hypothesis-engine --dry-run --retrieve \
  --corpus ~/hypothesis-corpus/text \
  -n 1 \
  "photosynthesis efficiency"
```

What those pieces mean:

| Piece | Meaning |
|--------|---------|
| `--dry-run` | Free demo, **no** xAI charges |
| `--retrieve` | “Please look at my local notes” |
| `--corpus ~/hypothesis-corpus/text` | “Look in this folder” |
| `-n 1` | One hypothesis (faster to read) |
| `"photosynthesis efficiency"` | Your topic — put words that appear in your notes |

You should see a **Sources** table. If it lists **`notes.md`** and **Backend: local**, it worked.

---

## Did it use my notes?

### Easy check (look at the screen)

| What you see under Sources | What it means |
|----------------------------|----------------|
| Your filename (e.g. `notes.md`) and **Backend: local** | Yes — your file matched the topic |
| Names like **`mock-notes-…`** and **Backend: mock** | No real match — dry-run showed a **demo** source so the UI still works |
| No Sources table (live mode) | No match — background used AI knowledge only |

### Optional nerdy check (JSON)

```bash
hypothesis-engine --dry-run --json-only --retrieve \
  --corpus ~/hypothesis-corpus/text \
  -n 1 "photosynthesis efficiency" \
  | python -c "import json,sys; d=json.load(sys.stdin); print('status:', d['meta'].get('retrieval_status')); print('backend:', d['meta'].get('retrieval_backend')); print('files:', [s['title'] for s in d['background']['sources']])"
```

| Printed status | Meaning |
|----------------|---------|
| `ok` + `local` | Real local hits |
| `ok_mock` + `mock` | Dry-run placeholders (no real match) |
| `empty` (live) | No match, no placeholders |

**If you only get mocks:** put more of your topic words in the note file, then run the same command again.

---

## Common ways to run it

### Just the app — no library (default)

```bash
hypothesis-engine --dry-run -n 1 "your topic"
```

No files are read.

### Whole notes folder (most common)

```bash
hypothesis-engine --dry-run --retrieve \
  --corpus ~/hypothesis-corpus/text \
  -n 1 "your topic"
```

### Only certain files

```bash
hypothesis-engine --dry-run --retrieve \
  --source ~/hypothesis-corpus/text/notes.md \
  --source ~/hypothesis-corpus/text/methods.md \
  -n 1 "your topic"
```

### Folder + one extra file + more hits

```bash
hypothesis-engine --dry-run --retrieve \
  --corpus ~/hypothesis-corpus/text \
  --source ~/Desktop/extra.md \
  --retrieve-k 8 \
  -n 1 "your topic"
```

`--retrieve-k 8` means “keep up to 8 matching notes” (default is 5; max 10).

### Live mode with your library (costs money)

Only after dry-run looks good. You need a real xAI key (see getting-started).

```bash
hypothesis-engine --retrieve \
  --corpus ~/hypothesis-corpus/text \
  -n 1 "your topic"
```

Type **YES** when asked (or use `-y` only if you accept charges).

**Live rules:**

- You **must** pass `--corpus` and/or `--source` (unlike dry-run).
- Retrieval still only reads **local** files for matching.
- Before you confirm, the app states clearly that your **topic and short snippets**
  from matching files **leave this machine** for the model API.
- Prefer **`--dry-run --retrieve`** first if the notes are sensitive.
- If nothing matches: no Sources table, status `empty` — no fake mock papers.

---

## Adding PDFs (optional)

You have two options.

### Option A — Let the engine read PDFs (recommended if you install one package)

```bash
cd ~/dagztagz-hypothesis-engine
source .venv/bin/activate
pip install '.[pdf]'    # installs pypdf
```

Then put PDFs in your library and point `--corpus` at a folder that contains them
(or use `--source path/to/paper.pdf`):

```bash
mkdir -p ~/hypothesis-corpus/pdfs
# copy PDFs into pdfs/

hypothesis-engine --dry-run --retrieve \
  --corpus ~/hypothesis-corpus/pdfs \
  -n 1 "your scientific topic"
```

**Corrupt / incomplete PDFs are skipped** (you may see fewer sources).  
If a PDF fails, re-download it or use Option B.

### Option B — Convert with `pdftotext` (no Python extra)

```bash
sudo apt install poppler-utils   # if needed

mkdir -p ~/hypothesis-corpus/text
pdftotext -layout \
  "$HOME/hypothesis-corpus/pdfs/my-paper.pdf" \
  "$HOME/hypothesis-corpus/text/my-paper.txt"

# all PDFs in a folder:
cd ~/hypothesis-corpus/pdfs
for f in *.pdf; do
  [ -f "$f" ] || continue
  pdftotext -layout "$f" "../text/${f%.pdf}.txt"
done

hypothesis-engine --dry-run --retrieve \
  --corpus ~/hypothesis-corpus/text \
  -n 1 "your scientific topic"
```

**No tools?** Open the PDF → copy text → save as `~/hypothesis-corpus/text/my-paper.md`.

---

## Small flags cheat sheet

| Flag | What it does | Required? |
|------|----------------|-----------|
| `--retrieve` | Turn on local notes | Yes, to use a library |
| `--corpus FOLDER` | Use all `.txt`/`.md` in that folder | Need this **or** `--source` for live |
| `--source FILE` | Use one file (can repeat) | Need this **or** `--corpus` for live |
| `--retrieve-k N` | Max matches (1–10, default 5) | No |
| `--retrieve-full-paths` | Keep absolute paths in JSON (default uses `~/…`) | No |
| `--dry-run` | Free test, no API bill | Recommended first |
| `-n 1` | How many hypotheses | No (default 2) |

---

## Tips that save frustration

1. **Put words from your topic inside the notes** — matching is simple keyword overlap, not magic AI search of your disk.  
2. **Subfolders are OK** under `--corpus` (depth-limited).  
3. **Long papers are chunked** — you may see titles like `paper.txt#chunk2`.  
4. **Don’t put secrets or API keys in note files.**  
5. **Don’t commit your private library to GitHub** — keep it under `~/hypothesis-corpus` (outside the clone).  
6. **JSON paths default to `~/…`** (not full `/home/you/…`). Use `--retrieve-full-paths` only if you need absolutes.  
7. **Start with dry-run** every time you change the library.  
8. **Broken PDFs** (trailer/xref errors) won’t convert — re-download or paste text.  
9. **Shortcuts (symlinks)** inside a corpus folder that point *outside* that folder are skipped (you’ll see a short warning).

---

## Safety (short)

- Research aid only — not peer review, medical, or legal advice.  
- You are responsible for how you store and use PDFs and notes.  
- Local retrieval does not replace careful science.

When you are ready for the full app tour (install, live mode, audit log), go back to **[getting-started.md](../getting-started.md)**.
