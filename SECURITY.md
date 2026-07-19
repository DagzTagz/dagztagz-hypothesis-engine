# Security Policy

Thank you for helping keep **DagzTagz Hypothesis Engine** and its users safe. We take security seriously, even while the project is early.

This is a **DagzTagz** community project. It is **powered by Grok (xAI)** when used with the live API, and is **not** an official product of xAI.

---

## Supported versions

| Version / branch | Supported |
|------------------|-----------|
| `main` (latest)  | Yes — security fixes land here |
| Older commits / forks | Best-effort only; please report against current `main` |

During Phase 1 there are no numbered releases yet. Treat the tip of `main` as the only supported line.

---

## What is in scope

Please report vulnerabilities that affect:

- This repository’s source code, scripts, configs, and published artifacts
- Secret handling (e.g. accidental logging or exposure of API keys)
- Authentication, authorization, or access-control bugs (when those features exist)
- Injection, path traversal, unsafe deserialization, or similar code issues
- Supply-chain issues in **this** project’s dependencies or release process
- Ways to abuse the tool that create a realistic security impact (e.g. prompt injection that causes secret exfiltration from a configured environment)

## What is out of scope

Please **do not** open security reports for:

- General product bugs or bad scientific advice (use regular issues)
- Theoretical issues with no realistic exploit path
- Vulnerabilities only in third-party services (report those upstream)
- Social engineering of individual contributors outside this project
- Denial of service against public free-tier APIs you do not operate

If you are unsure, report it privately anyway — we would rather triage once than miss a real issue.

---

## How to report a vulnerability

### Preferred: GitHub Security Advisories (private)

1. Open the repository on GitHub:  
   https://github.com/DagzTagz/dagztagz-hypothesis-engine  
2. Go to **Security → Advisories → Report a vulnerability**  
   (or use: https://github.com/DagzTagz/dagztagz-hypothesis-engine/security/advisories/new )  
3. Include as much detail as you can (see “What to include” below).

This keeps the report private until we publish a fix or coordinated disclosure.

### Alternative: private email

If you cannot use GitHub Advisories, email:

**dagztagz369@proton.me**

Subject line suggestion: `[SECURITY] dagztagz-hypothesis-engine …`

Do **not** send secrets you found in a public channel. If a live key was exposed, say *that a key was exposed* and rotate it yourself if you own it; we can coordinate redaction separately.

---

## What to include

Helpful reports usually contain:

1. **Summary** — one or two sentences  
2. **Impact** — who/what is affected, and how badly  
3. **Affected component** — file, feature, commit, or release if known  
4. **Steps to reproduce** — minimal, clear steps  
5. **Proof of concept** — only what is needed to demonstrate (no mass scanning, no harm to others)  
6. **Suggested fix** — optional, appreciated  
7. **Your contact** — so we can follow up  
8. **Disclosure timeline** — if you have a preferred date (see below)

---

## Our commitments

When you report in good faith, we will aim to:

- **Acknowledge** within **72 hours** (often sooner)  
- **Triage** severity and confirm or ask clarifying questions  
- **Keep you informed** of major status changes  
- **Credit you** in the advisory or release notes if you want credit (we will ask)  
- **Not take legal action** against good-faith, non-destructive research that follows this policy

We may decline reports that are out of scope, duplicates, or not security issues. We will still try to explain why.

---

## Coordinated disclosure

We follow a **coordinated disclosure** model:

- Default expectation: give us up to **90 days** to investigate and ship a fix before public write-ups  
- We may ask for more time for complex issues; we may publish sooner if risk to users is high  
- Please **do not** post exploit details in public issues, discussions, or social media before we agree a disclosure date  
- **Never** open a public issue that contains live secrets, private keys, tokens, or personal data

If a secret was already leaked publicly, treat containment (rotation, revoke) as urgent; disclosure of *that fact* can still be handled carefully.

---

## Safe harbor (good-faith research)

We consider security research conducted under this policy to be authorized for this project when you:

- Make a good-faith effort to avoid privacy violations, service disruption, and data destruction  
- Do not access or modify data that is not yours beyond what is needed to demonstrate the issue  
- Do not exploit the finding for any purpose other than reporting it  
- Report promptly through the private channels above  

This safe harbor does **not** cover attacks on infrastructure you do not own, spam, malware distribution, or anything illegal under applicable law.

---

## Security practices (maintainers & contributors)

Contributors should:

- **Never commit secrets** (API keys, tokens, private keys, recovery codes, `.env` files with real values)  
- Use `.env.example` (or similar) with placeholders only  
- Prefer signed commits when practical  
- Open a **private** report (not a public PR description) if you accidentally committed a secret — then rotate the credential  
- Review dependency changes carefully as the project grows  

See `.gitignore` for patterns we already try to keep out of the tree.

---

## Prefer GitHub features when available

When this repository has them enabled, we prefer:

- **Private vulnerability reporting** / Security Advisories  
- **Secret scanning** and **push protection**  
- **Dependabot** (or equivalent) once dependencies exist  

Public issues remain the right place for non-security bugs and feature requests.

---

## Export controls, sanctions, and cryptography

- **Public open source:** This software is provided as publicly available open source (Apache-2.0 on this repository). Use of the **xAI API** (live mode) is subject to [xAI’s terms](https://x.ai/legal/terms-of-service) and applicable **US export and sanctions laws**. **You** are responsible for lawful use in your jurisdiction.
- **No circumvention:** Do **not** use this project to evade sanctions, export controls, or other applicable law.
- **Crypto purpose:** Optional audit-log topic encryption protects **local** audit files using **standard published algorithms** (optional extra: `pip install 'dagztagz-hypothesis-engine[audit]'`, Fernet via the `cryptography` package). It is **not** a government-certified cryptographic module. Default audit logging stores a one-way topic hash only; encryption is opt-in and fails closed if a key is configured without the extra installed. This feature is **not** intended or documented as a means of covert communication or of evading lawful process.

Local audit privacy choices are described in [getting-started.md](getting-started.md#optional-local-audit-log-privacy-choices). They are **local defense-in-depth**, not a compliance certification.

---

## Questions

For non-sensitive questions about this policy, open a normal GitHub issue.  
For anything that might be a vulnerability, use the private channels in **How to report a vulnerability**.
