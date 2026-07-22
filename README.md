# DagzTagz Hypothesis Engine

**An open-source, community-driven system for generating, verifying, and testing scientific hypotheses.**  
**Powered by Grok (xAI)** — not an official xAI product.

The goal of this project is to create a transparent, auditable AI tool that helps researchers and curious minds propose novel scientific hypotheses, act as a peer adversary to rigorously check them against existing knowledge, and suggest practical ways to test them.

This project is inspired by xAI’s mission to advance our understanding of the universe through maximally truth-seeking AI. Live model calls use the **xAI Grok API** under **your** account and terms.

> **Current Status**: **Phase 2** (in progress). Phase 1 MVP is **complete and shipping**. First Phase 2 slice: **multi-check verification** (`multi_check_v1` — consistency, testability, confounds, prior_knowledge in one verify call). Next thin slices: retrieval (RAG) and richer experiments—not a full multi-agent system yet.

---

## Vision

We want to build an AI system that acts like a thoughtful scientific collaborator:

- Proposes interesting, testable hypotheses grounded in real science
- Critically verifies those hypotheses for consistency and plausibility
- Suggests concrete experiments or simulations to personally test hypothesis against criticisms of hypothesis
- Maintains a clear, auditable record of its reasoning

The long-term vision is a multi-agent system that can assist with real scientific discovery while staying honest about what it knows and doesn’t know.

---

## What ships today

### Phase 1 MVP — complete
- Basic hypothesis generation from a topic or short description
- Structured output (hypothesis + verification + suggested tests)
- Dry-run mode, live Grok API path, CI (pytest + ruff), optional local audit logging

### Phase 2 — shipping now
- **Multi-check verification** (`meta.verification = multi_check_v1`): each hypothesis is scored on **consistency**, **testability**, **confounds**, and **prior_knowledge** (plus overall verdict). Still **one API call** per hypothesis for verify—richer JSON, not extra cost from extra round-trips.
- Human CLI table and JSON `verifications[].checks[]` for the four dimensions

**Note:** The runnable app is still a **single, well-prompted workflow** (not multi-agent). Phase 2 continues in thin slices.

---

## Phase 2 focus (current)

Landed / next:

- [x] Stronger verification (multi-check `multi_check_v1`)
- [ ] Literature-style retrieval (RAG) when ready
- [ ] Richer experiment-suggestion capabilities

Track detail in [Roadmap](#roadmap).

---

## How It Works (High Level)

1. You give the system a scientific topic or research area
2. It builds a short **background brief** (Phase 1: model knowledge only — not a live literature search)
3. It generates one or more hypotheses
4. It verifies each hypothesis for scientific consistency (thinking adversarially)
5. It suggests ways to test the hypothesis (experiments or code simulations)
6. Everything is output in a clear, structured format with reasoning (avoids black box reasoning)

---

## Getting Started

> ### Start with `--dry-run` (recommended for everyone)
>
> **Before** you add an API key or make live calls, install the project and run a **dry-run**.
> Dry-run uses **mock output only**: no xAI network request, no API key, no model charges.
>
> ```bash
> git clone https://github.com/DagzTagz/dagztagz-hypothesis-engine.git
> cd dagztagz-hypothesis-engine
> python3 -m venv .venv
> source .venv/bin/activate   # Windows: .venv\Scripts\activate
> pip install -e ".[dev]"
> hypothesis-engine --dry-run "photosynthesis under low light"
> ```
>
> You should see labeled mock hypotheses and: *“Dry-run mock output; no API calls were made.”*  
> Full walkthrough: **[getting-started.md](getting-started.md)**.

### Why dry-run first?

| Dry-run (`--dry-run`) | Live run (no flag) |
|----------------------|--------------------|
| No `XAI_API_KEY` needed | Requires your xAI key |
| No call to `api.x.ai` | Sends prompts + topic to xAI (Grok) |
| **$0 — no model charges** | **Bills your xAI account (real money/credits)** |
| Safe way to verify install | Real Grok generations (powered by xAI) |
| Mock text only | Model-generated science aid |

### Disclosures (please read)

- **Not malware, but not magic:** this repo is ordinary open-source Python. Clone and `pip install` do **not** by themselves call xAI. Live mode **does** use the network when **you** run it without `--dry-run`.
- **Your API key is your secret:** put it in a local `.env` (see `.env.example`). **Never commit** `.env` or paste keys into issues, PRs, or the topic string.
- **Live mode leaves your machine:** topic text and prompts are sent to **xAI** under **your** account/terms (including xAI’s terms and Acceptable Use Policy). Do not put passwords, private data, or keys in the topic.
- **Local audit logs are a privacy choice you control:** optional `--audit-log` files stay local; default topic storage is a one-way hash. That does **not** stop live topics from going to xAI. See [audit log](#optional-local-audit-log-privacy-is-your-local-choice).
- **Not established science:** outputs are experimental research aids. Always verify with experts and real methods.
- **Not an official xAI product:** **DagzTagz Hypothesis Engine** is a community project. **Powered by Grok (xAI)** means we call the public Grok API — it does **not** mean endorsement, partnership, or sponsorship by xAI. See [Disclaimer](#disclaimer) and [SECURITY.md](SECURITY.md).

---

### ⚠️ COST WARNING — LIVE MODE SPENDS REAL MONEY

> ## LIVE MODE IS NOT FREE
>
> Running **without** `--dry-run` calls the **xAI paid API** (Grok) with **your** `XAI_API_KEY`.
>
> - **You** pay for tokens / credits on **your** xAI account ([console.x.ai](https://console.x.ai) / xAI pricing).
> - This project does **not** pay for your usage and cannot cap your bill for you.
> - Phase 1 makes **multiple** model calls per run (background + generate + verify each hypothesis + tests). Costs scale with `-n` / `--num-hypotheses` and topic length.
> - The CLI may show an **estimated API call count** — that is **not a dollar price quote**. Your bill depends on **tokens used** and **xAI’s current pricing**.
> - Repeating live runs, automation, or large `-n` values can **add up quickly**.
> - **Dry-run costs $0.** Use it until you deliberately accept live charges.
>
> **Only use live mode if you understand and accept API billing on your account.**
> Check your xAI balance/limits before running live. This community project is **not responsible** for unexpected API charges.

---

### Live mode (only after dry-run works — **costs money**)

**1. Create a private secrets file** (once):

```bash
cp .env.example .env
```

**2. Add your xAI key to `.env`**

**Linux / Terminal (nano — recommended):**

```bash
nano .env
```

Make sure you have this line (paste your real key only on your machine):

```text
XAI_API_KEY=paste_your_key_here
```

Save and exit nano: **Ctrl+O**, then **Enter**, then **Ctrl+X**.

**Windows / Mac (backup if you don’t use nano):** open `.env` in Notepad, TextEdit, or VS Code, add the same line, save the file.

- No spaces around `=` · prefer no quotes · never commit `.env`  
- Optional: `chmod 600 .env`  
- Full detail: **[getting-started.md — Configure secrets](getting-started.md#configure-secrets)**

**3. Run live** (bills your xAI account; type `YES` unless you pass `-y`):

```bash
hypothesis-engine "effects of microplastics on soil microbiomes" -n 2
```

After **YES**, **wait** — the tool makes multiple xAI calls and prints progress (`[1/6] …`).  
**Do not type** until results appear (use Ctrl+C only to cancel).

Live runs are **powered by Grok (xAI)**. Output is attributed accordingly; still not an official xAI product.

### Optional local audit log (privacy is **your** local choice)

Full step-by-step: **[getting-started.md — Optional local audit log](getting-started.md#optional-local-audit-log-privacy-choices)**.

**This is a local policy choice for serious privacy considerations — not a compliance certification.**

It is still a **real privacy enhancement at the local layer**: it reduces how often sensitive topic text ends up in cleartext files that are easy to overshare (tickets, git, screenshots, shared machines), supports **developer least-privilege logging**, and raises the bar against **casual or opportunistic** local exposure. It does **not** replace OS disk encryption, account lock, or the fact that **live** mode still sends topics to xAI.

| Point | Meaning |
|-------|---------|
| Optional | No `--audit-log` → no audit file |
| Local only | File stays on **your** machine unless **you** share it |
| Not a cloud DLP product | Does not replace legal/compliance programs (HIPAA, etc.) |
| Does not hide topics from xAI | **Live** mode still sends the full topic to xAI for generation |
| Default topic protection | One-way `topic_sha256` hash only (no plaintext topic in the log) |
| Optional encryption | `AUDIT_LOG_KEY` + `pip install -e '.[audit]'` → `topic_encrypted` |
| Fail closed | If `AUDIT_LOG_KEY` is set without `[audit]` installed → **error + install instructions** |
| Plaintext opt-in | `--audit-include-topic` (least private) |
| API keys | **Never** written to the audit log |
| Why bother without a cert? | Limits blast radius of leaked logs, shared PCs, bad git adds, and debug paste; keeps audit **metadata** without a second plaintext prompt archive — see [getting-started](getting-started.md#why-local-hash--encrypt-still-matters-even-without-a-certification) |

Quick examples:

```bash
# A) Hash-only (default privacy, no extra packages)
hypothesis-engine --dry-run "my topic" --audit-log audit.jsonl

# B) Encryption (one-time install + secret in .env)
pip install -e ".[audit]"
# add AUDIT_LOG_KEY=... to .env  (never commit .env)
hypothesis-engine --dry-run "my topic" --audit-log audit.jsonl
# expect topic_storage=encrypted and topic_encrypted=... in audit.jsonl
# full encrypt + decrypt test steps: getting-started.md (Mode B, Steps 1–4)

# C) Explicit plaintext in the log (avoid for sensitive topics)
hypothesis-engine --dry-run "my topic" --audit-log audit.jsonl --audit-include-topic
```

`audit.jsonl` / `*.jsonl` are gitignored — still do not force-add or publish them.

### Option 2: Using Grok Build (for faster development)

Since Grok Build (xAI’s open-source coding agent) is available, contributors may use it to help build and extend **DagzTagz Hypothesis Engine**. Still prefer **`--dry-run` first** when checking a local checkout.

---

## Development & Attribution

This project is being developed as an **open community effort** under the **DagzTagz** brand.

**Powered by Grok (xAI):**
- Live inference uses the **xAI Grok API** (OpenAI-compatible endpoint). You need your own `XAI_API_KEY` and must follow xAI’s terms.
- We attribute model-backed results to Grok/xAI as the **API provider**, not as the product owner.

**Pair programming with Grok:**
- Much of the initial architecture, prompt design, code scaffolding, and iterative development has been done through close collaboration with **Grok**, an AI built by xAI.
- Grok has served as a pair programmer — helping with ideas, code, explanations, and problem-solving.
- All final code, design decisions, and responsibility for the project belong to the human contributors (**DagzTagz** and community).

We believe in being transparent about AI assistance.

Special thanks to **xAI** for open-sourcing models/tools and offering an API that community projects can build on.

---

## Contributing

We warmly welcome contributors of all backgrounds and skill levels.

You don’t need to be a professional programmer to help. Contributions can include:
- Testing the current version and giving feedback
- Improving prompts and verification logic
- Adding better documentation
- Suggesting new features
- Helping with scientific domain knowledge
- Writing examples and test cases

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Even if you just want to follow along or ask questions, feel free to open an issue.

---

## Roadmap

### Phase 1 — complete
- Simple working MVP (single workflow)
- Basic hypothesis generation + verification
- Clear structured output
- Safety/docs foundation, CI (pytest + ruff), optional audit log

### Phase 2 — current
- Multi-check verification (`multi_check_v1`) — shipping
- Add literature retrieval (RAG)
- Expand experiment-suggestion capabilities
- Thin, reviewable slices preferred over big-bang rewrites

### Phase 3
- Multi-agent architecture (Generator + Verifier + Experiment Designer)
- Better audit logging and transparency
- Web interface

### Long-term
- Domain-specific modes (Physics, Biology, Materials Science, etc.)
- Integration with real scientific tools and simulators
- Community-curated knowledge base

---

## Export controls, sanctions, and cryptography

- **Public open source:** This software is provided as publicly available open source (Apache-2.0). Use of the **xAI API** is subject to [xAI’s terms](https://x.ai/legal/terms-of-service) and applicable **US export and sanctions laws**. **You** are responsible for lawful use in your jurisdiction.
- **No circumvention:** Do **not** use this project to evade sanctions, export controls, or other applicable law.
- **Crypto purpose:** Optional audit-log encryption protects **local** log files using **standard published algorithms** (via optional dependency `cryptography` / Fernet). It is **not** a government-certified cryptographic module and is **not** marketed as a tool for covert communications or law-enforcement evasion.

See also [SECURITY.md](SECURITY.md) and local audit privacy notes in [getting-started.md](getting-started.md#optional-local-audit-log-privacy-choices).

---

## License

This project is licensed under the **Apache License 2.0**.

You are free to use, modify, and distribute this software under that license.

---

## Acknowledgments

- **DagzTagz** community and contributors
- **xAI / Grok** — API and pair-programming assistance (**powered by Grok (xAI)**; not an official product)
- The broader open-source AI and scientific community (especially projects like Open Coscientist and related research on AI hypothesis generation)

---

## Disclaimer

**DagzTagz Hypothesis Engine** is a community project and is **not** an official product of xAI.  
It is **powered by Grok (xAI)** when used in live mode: that means the project calls the Grok API; it does **not** mean xAI endorses, sponsors, or operates this software.

It is an experimental tool meant to assist scientific thinking. Always verify any hypotheses or suggestions with real experts and proper scientific methods.

**Safety defaults:** prefer `hypothesis-engine --dry-run "…"` until you intentionally enable live API use. Dry-run does not contact xAI and costs **$0**. **Live mode bills your xAI account** (real money/credits); see [COST WARNING](#️-cost-warning--live-mode-spends-real-money).

---

**Let’s build something useful together.**

If you’re interested in contributing, have feedback, or just want to follow the project, feel free to star the repo, open an issue, or reach out.
