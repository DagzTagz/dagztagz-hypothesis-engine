# Getting Started — DagzTagz Hypothesis Engine (Phase 1 MVP)

This guide runs the **DagzTagz Hypothesis Engine** Phase 1 CLI: a single workflow that
proposes hypotheses, checks them adversarially, and suggests tests.

**Powered by Grok (xAI)** in live mode. **Not** an official xAI product.

## Requirements

- Python **3.11+**
- An [xAI API key](https://console.x.ai) for live runs (`XAI_API_KEY`)
- Git (to clone the repo)

Live calls use the **xAI OpenAI-compatible API** (`https://api.x.ai/v1`) with model
`grok-4.5` by default (**powered by Grok (xAI)**).

## Install (editable)

### 1. Get the code

Clone with Git (recommended — easy to update later with `git pull`):

```bash
git clone https://github.com/DagzTagz/dagztagz-hypothesis-engine.git
cd dagztagz-hypothesis-engine
```

If the GitHub repo was recently renamed, the old URL may redirect; prefer the name above.

If you downloaded a **ZIP** from GitHub instead: unzip it, then `cd` into the unzipped folder
(it may be named `dagztagz-hypothesis-engine-main` or similar).

### 2. Create a virtual environment and install

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

If `hypothesis-engine` is not found after install, confirm the venv is active and re-run `pip install -e ".[dev]"`. The command name is **`hypothesis-engine`** (not `hypothesis`).

## Configure secrets

Your secret keys go in a small private file named **`.env`** in the project folder.  
Think of it as a **password file only on your computer** — never upload it to GitHub or paste it into chat.

### Step 1 — create the file from the template

In the project folder (with your terminal open there):

```bash
cp .env.example .env
```

### Step 2 — put your xAI key in `.env`

#### Option A — nano (recommended for Linux / Terminal)

**nano** is a simple text editor that runs in the terminal. Great default on Ubuntu and similar systems.

```bash
nano .env
```

1. Find the line that looks like `XAI_API_KEY=` (or add it if missing).  
2. Paste your key so the line looks like:

```text
XAI_API_KEY=paste_your_key_here
```

3. **Save and quit nano** (important — these keys are for nano, not the shell):
   - Hold **Ctrl** and press **O** (letter O = “write Out” / save)  
   - Press **Enter** to confirm the filename  
   - Hold **Ctrl** and press **X** (exit)

You should be back at the normal terminal prompt.

#### Option B — not using Linux Terminal? (backup)

Use **any** normal text editor:

| System | Easy options |
|--------|----------------|
| **Windows** | Open the project folder in File Explorer → right‑click `.env` → Open with **Notepad** (or VS Code) |
| **Mac** | Open `.env` in **TextEdit**, or VS Code |
| **Linux desktop** | Double‑click `.env` / open with **Text Editor** (Gedit), or VS Code (`code .env`) |

Make the same line as above (`XAI_API_KEY=...`), save the file, then return to the terminal.

### Step 3 — rules (read once)

- No spaces around `=`  
- Prefer **no quotes** around the key  
- **Never commit** `.env` (git already ignores it)  
- On Linux/macOS, optional lock-down so only you can read it:

```bash
chmod 600 .env
```

### Alternative (one terminal session only — less ideal)

```bash
export XAI_API_KEY=your_key_here
```

Prefer `.env` so the key is less likely to stick around in shell history.

## Run (offline dry-run — no API key, $0 cost)

Useful to verify install and output shape:

```bash
hypothesis-engine --dry-run "photosynthesis under low light"
# or
python -m hypothesis_engine --dry-run "photosynthesis under low light"
```

JSON only:

```bash
hypothesis-engine --dry-run --json-only -n 1 "coral bleaching" -o out.json
```

## Optional: ground background on local notes (RAG v0)

By default the background brief uses **model knowledge only**.  
You can opt in to use **your own files** on disk (privacy-first — **not** a web literature search).

| Need | Flag |
|------|------|
| Turn retrieval on | `--retrieve` |
| Folder of notes | `--corpus DIR` (direct `.txt`/`.md` files only) |
| Specific files | `--source FILE` (repeatable) |
| How many hits | `--retrieve-k N` (1–10, default 5) |

**1 — free dry-run with a tiny note**

```bash
mkdir -p ~/hypothesis-corpus/text
echo "Chlorophyll and light spectrum affect photosynthesis efficiency." \
  > ~/hypothesis-corpus/text/notes.md

hypothesis-engine --dry-run --retrieve --corpus ~/hypothesis-corpus/text \
  -n 1 "photosynthesis efficiency"
```

**2 — did it use your file or a dry-run mock?**

| You see | Meaning |
|---------|---------|
| Sources **Backend `local`**, your filename, status **`ok`** | Real keyword match |
| Sources **Backend `mock`**, titles like `mock-…`, status **`ok_mock`** | No usable match (dry-run demo fill) |

```bash
hypothesis-engine --dry-run --json-only --retrieve --corpus ~/hypothesis-corpus/text \
  -n 1 "photosynthesis efficiency" \
  | python -c "import json,sys; d=json.load(sys.stdin); print(d['meta'].get('retrieval_status'), d['meta'].get('retrieval_backend')); print([s['title'] for s in d['background']['sources']])"
```

**PDFs, folder layout, more options:** [docs/local-corpus.md](docs/local-corpus.md)

## Run (live — powered by Grok (xAI), **costs money**)

```bash
hypothesis-engine "effects of microplastics on soil microbiomes" -n 2
```

You will be asked to type **`YES`** to confirm charges (an estimated API call count is shown).

- That estimate is **not a dollar price quote**. Your bill depends on **tokens used** and **xAI’s current pricing** (see [console.x.ai](https://console.x.ai)).
- Skip the prompt only if you accept charges in scripts: add `-y` / `--yes`
- Non-interactive sessions **refuse** live mode without `--yes` (use `--dry-run` instead)

**Live + local notes** (still only *your* files for retrieval; **topic + snippets go to xAI**).  
Requires `--corpus` and/or `--source`:

```bash
hypothesis-engine --retrieve --corpus ~/hypothesis-corpus/text \
  -n 1 "photosynthesis efficiency"
# scripts (after you accept cost): add -y
```

If nothing matches: no Sources table, `retrieval_status=empty`, background stays model-only (no mock fill in live).

**After you type YES — please wait:**

- Live mode makes **several** xAI calls (background → generate → verify each → tests). This often takes **a while** (sometimes minutes).
- You will see progress lines such as `[1/6] …` as steps finish.
- **Do not type anything** while it runs (typing will not make it faster). Use **Ctrl+C** only if you need to cancel.
- When finished, you will see a short “Done waiting” message, then the report.

**Warning:** live mode bills **your** xAI account (multiple API calls per run). Dry-run first.

## Optional local audit log (privacy choices)

An audit log is **optional**. If you never pass `--audit-log`, no audit file is written.

### File permissions (owner-only)

The CLI writes **`--audit-log`** and **`-o` / `--output`** files as mode **`0600`** (owner read/write only — not group or “world” readable). That reduces casual reads by other accounts on a shared machine or multi-user VM.

If you already have older files from before this behavior:

```bash
chmod 600 audit.jsonl out.json   # only the files you care about
```

Same idea as `chmod 600 .env`. This is local OS hygiene, not encryption.

### Important: this is a **local privacy policy choice**

- The audit file stays **on your computer** (unless **you** copy or upload it).
- **You** choose whether to log at all, and how private topics are in that file.
- This is **not** a cloud compliance product, **not** HIPAA/SOC2 certification, and **not** a guarantee against every risk (e.g. someone with access to your machine, backups, or a stolen disk).
- **Live mode still sends the full topic to xAI** for the model call — audit settings do **not** hide the topic from xAI. They only control what is written into **your local** log file.
- **API keys are never written** into the audit log.
- Treat sensitive research topics carefully: free dry-run keeps topics off xAI; live mode does not.

### Why local hash / encrypt still matters (even without a “certification”)

These controls are **defense-in-depth for your laptop and shared workspaces**, not a badge from an auditor. They still reduce real, common failure modes:

| Situation | How hash / optional encryption helps |
|-----------|--------------------------------------|
| **Accidental sharing** | You paste `audit.jsonl` into a ticket, Discord, or public gist. Hash-only (or encrypted) topics are far less damaging than full plaintext research questions. |
| **Git mistakes** | Someone force-adds a log file or copies it into a repo. Default storage avoids committing readable topics. |
| **Shared / multi-user machines** | Lab PC, family computer, or VM snapshots: other local accounts or casual browsers of your home directory see less sensitive text in logs. |
| **Support & screenshots** | You show a teammate a log line for debugging timestamps/errors without exposing the full topic string. |
| **Developer hygiene** | Contributors can keep run history for “what failed / when” while treating topic text as sensitive by default (least privilege for logs). |
| **Mild adversarial local access** | Curious roommate, opportunistic malware that scrapes `*.jsonl`, or a lost unlocked session: hashed topics are not immediately readable; encryption needs `AUDIT_LOG_KEY`. |
| **Separation of duties** | You can store audit metadata (dry-run vs live, call estimates, exit status) without building a second copy of every prompt on disk. |

**What this is not claiming:** that a sophisticated attacker with your user account, your encryption passphrase, disk encryption off, or full root access is fully stopped. Full-disk encryption, OS lock screen, and not using live mode for secrets remain essential.

**Bottom line:** certification answers “can we sell this as regulated compliance?” Local hash/encrypt answers “do we avoid needlessly writing sensitive strings into files that leak more easily than we think?” — **yes**, and that is still a meaningful privacy enhancement for developers and careful users.

### Mode A — Hash only (default privacy, no extra packages)

Best default if you want a paper trail without storing the topic in clear text.

```bash
cd dagztagz-hypothesis-engine
source .venv/bin/activate
hypothesis-engine --dry-run "my topic" --audit-log audit.jsonl
```

What you get in `audit.jsonl`: events like `start` / `complete` with `topic_sha256` (one-way fingerprint).  
You **cannot** turn that hash back into the original words.

### Mode B — Encrypted topic (optional extra install)

Use this if you want the topic recoverable later **only** with a secret you control.

**Step 1 — install encryption support** (one-time):

```bash
cd dagztagz-hypothesis-engine
source .venv/bin/activate
pip install -e ".[audit]"
```

(Developers using `pip install -e ".[dev]"` already get this.)

**Step 2 — set a secret in `.env`** (never commit this file)

Same idea as [Configure secrets](#configure-secrets).

**Linux / Terminal (nano — recommended):**

```bash
nano .env
```

Add a long random passphrase **on its own line** (this is **not** your xAI API key):

```text
AUDIT_LOG_KEY=replace-with-a-long-random-passphrase
```

Save and exit nano: **Ctrl+O**, **Enter**, **Ctrl+X**.

**Windows / Mac / desktop editors:** open `.env` in Notepad, TextEdit, or VS Code and add the same line, then save.

The CLI loads `.env` automatically for `AUDIT_LOG_KEY`.  
If the key is missing or blank, the log stays **hash-only**.

**Step 3 — run with audit log** (from the project directory, venv on):

```bash
# optional: start a fresh log file for a clean test
rm -f audit.jsonl

hypothesis-engine --dry-run "my topic" -n 1 --audit-log audit.jsonl
cat audit.jsonl
```

**Success looks like:** `"topic_storage": "encrypted"` and a `"topic_encrypted": "gAAAA..."` field.  
**Hash-only** (`"topic_storage": "hash_only"`) means `AUDIT_LOG_KEY` was not set/loaded — fix `.env` and re-run.

Optional quick checks (do **not** print your key):

```bash
# plaintext topic should NOT appear in the file
grep -F "my topic" audit.jsonl || echo "Good: plaintext topic not in log"

# storage mode should say encrypted
grep -F 'topic_storage' audit.jsonl
```

**Fail closed:** if `AUDIT_LOG_KEY` is set but `[audit]` is **not** installed, the CLI **exits with install instructions**. It will **not** silently write hash-only while you thought encryption was on.

**Step 4 — test decryption** (proves you can recover the topic with the same key)

This is a small **Python** script. Paste the **whole block** into the terminal (not line-by-line as bash).  
`load_dotenv(...)` is **Python**, not a bash command.

```bash
cd dagztagz-hypothesis-engine
source .venv/bin/activate
python - <<'PY'
from hypothesis_engine.audit import decrypt_topic
import json, os
from dotenv import load_dotenv

# Use an explicit path so this works with "python - <<'PY'" (stdin scripts).
load_dotenv(".env")

secret = os.environ["AUDIT_LOG_KEY"]
row = json.loads(open("audit.jsonl").readline())
print(decrypt_topic(row["topic_encrypted"], secret))
PY
```

**Success:** the terminal prints your original topic (e.g. `my topic` or whatever you used in Step 3).  
**This does not write the key into the repo** — it only prints the decrypted topic. Keep `.env` private (`chmod 600 .env` recommended).

If you see `AssertionError` from `load_dotenv`, you likely ran `load_dotenv(...)` alone in bash, or need `load_dotenv(".env")` with an explicit path as above.

### Mode C — Plaintext topic (explicit opt-in, least private)

Only if you accept the topic sitting in clear text on disk:

```bash
hypothesis-engine --dry-run "my topic" --audit-log audit.jsonl --audit-include-topic
```

Avoid this for sensitive topics.

### Live run + audit (costs money; still local log only)

```bash
# interactive: type YES when asked
hypothesis-engine "my topic" -n 2 --audit-log audit.jsonl

# scripts only if you accept charges:
hypothesis-engine -y "my topic" -n 1 --audit-log audit.jsonl
```

### Keep audit files private

```bash
# audit.jsonl is gitignored — still do not force-add it
ls -la audit.jsonl
```

Do not upload audit files to public GitHub, tickets, or chat if they might contain sensitive material (especially if you used `--audit-include-topic`).

Optional env overrides:

- `XAI_MODEL` (default `grok-4.5`)
- `XAI_BASE_URL` (default `https://api.x.ai/v1`)

Live users must follow [xAI’s terms](https://x.ai/legal/terms-of-service) and [Acceptable Use Policy](https://x.ai/legal/acceptable-use-policy).

## What the pipeline does

1. **Background brief** — model knowledge by default; optional **local-file** retrieval (`--retrieve`)
2. **Generate** N hypotheses (default 2)
3. **Verify** each adversarially (multi-check: consistency, testability, confounds, prior_knowledge)
4. **Suggest tests** (richer fields + falsification criteria)
5. Print a readable report and optional JSON

Deep dive on building a private note/PDF library: **[docs/local-corpus.md](docs/local-corpus.md)**.

## Tests

```bash
pytest
```

## Security notes

- Keep keys out of the shell history when you can (prefer `.env`)
- Audit logging is a **local** privacy choice — see [Optional local audit log](#optional-local-audit-log-privacy-choices)
- Live mode privacy toward **xAI** is separate: the topic still goes to their API when you run without `--dry-run`
- See [SECURITY.md](SECURITY.md) for vulnerability reporting
- See [CONTRIBUTING.md](CONTRIBUTING.md) for PR workflow

## Disclaimer

**DagzTagz Hypothesis Engine** is an experimental research aid only. Not established science.  
**Powered by Grok (xAI)** when used live — **not** an official xAI product.
