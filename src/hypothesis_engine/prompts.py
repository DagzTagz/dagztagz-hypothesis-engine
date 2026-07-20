"""Prompt templates for the single Phase 1 workflow.

Prompts are kept in one place so contributors can improve them without
touching plumbing. Phase 1 is intentionally one linear pipeline, not agents.
"""

from __future__ import annotations

SYSTEM_SCIENTIST = """\
You are a careful scientific collaborator working inside DagzTagz Hypothesis \
Engine (powered by Grok / xAI for live inference).
Goals:
- Prefer testable, falsifiable claims over vague speculation.
- Think adversarially: look for contradictions, missing controls, and confounds.
- Be honest about uncertainty and the limits of your knowledge.
- Do NOT invent citations or claim you searched the live literature unless told tools were used.
- Phase 1 background is model knowledge only, not a RAG literature review.
- Output MUST be valid JSON matching the schema instructions in the user message.
- In JSON strings, escape backslashes as \\\\ and double quotes as \\". Avoid raw \\
  sequences from LaTeX or file paths unless properly escaped.
- Never request or echo API keys or other secrets.
"""

BACKGROUND_USER = """\
Topic or research area:
{topic}

Produce a short BACKGROUND BRIEF as JSON with keys:
- topic (string)
- summary (string, 1-3 paragraphs of useful background)
- key_concepts (array of strings)
- known_limitations (array of strings; include that this is NOT a literature search)
- caveats (array of strings; uncertainty, domain limits)

Return ONLY JSON.
"""

GENERATE_USER = """\
Topic:
{topic}

Background brief (JSON):
{background_json}

Generate {n} distinct, testable scientific hypotheses related to the topic.
Return ONLY JSON with key "hypotheses": an array of objects, each with:
- id (string, H1..Hn)
- statement (string, clear and falsifiable)
- rationale (string)
- assumptions (array of strings)
- domain (string or null)

Avoid duplicates. Prefer specific mechanisms or measurable claims over slogans.
Return ONLY JSON.
"""

VERIFY_USER = """\
Topic:
{topic}

Background brief (JSON):
{background_json}

Hypothesis to verify (JSON):
{hypothesis_json}

Act as a peer adversary. Check scientific consistency, testability, and obvious
contradictions with well-established knowledge (without inventing fake papers).

Return ONLY JSON with keys:
- hypothesis_id (string)
- verdict: one of "plausible" | "needs_revision" | "contradicted" | "not_testable"
- confidence: one of "low" | "medium" | "high"
- consistency_notes (string)
- critiques: array of {{claim, severity (low|medium|high), evidence_or_reasoning}}
- contradictions: array of strings
- revision_suggestions: array of strings

Return ONLY JSON.
"""

TESTS_USER = """\
Topic:
{topic}

Hypothesis (JSON):
{hypothesis_json}

Verification (JSON):
{verification_json}

Suggest 1-3 concrete ways to TEST this hypothesis (lab experiment, field study,
computational simulation, data analysis, etc.). Each suggestion should say what
result would FALSIFY the hypothesis.

Return ONLY JSON with key "tests": array of objects with:
- hypothesis_id (string)
- title (string)
- method (string: experiment | simulation | analysis | observation)
- description (string)
- what_would_falsify (string)
- rough_difficulty (low|medium|high)
- notes (array of strings)

Return ONLY JSON.
"""
