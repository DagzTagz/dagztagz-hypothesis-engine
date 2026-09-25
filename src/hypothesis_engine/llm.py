"""Thin wrapper around the xAI (Grok) OpenAI-compatible API."""

from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from hypothesis_engine.config import Settings


class LLMError(RuntimeError):
    """Raised when the model response cannot be used."""


# JSON allows \" \\ \/ \b \f \n \r \t \uXXXX — models often emit bare \path or \s etc.
_JSON_SIMPLE_ESCAPES = set('"\\/bfnrt')
_JSON_HEX = set("0123456789abcdefABCDEF")


def build_client(settings: Settings) -> OpenAI:
    api_key = settings.require_api_key()
    return OpenAI(api_key=api_key, base_url=settings.xai_base_url)


def chat_json(
    client: OpenAI,
    *,
    model: str,
    system: str,
    user: str,
    temperature: float = 0.4,
    max_parse_retries: int = 1,
) -> dict[str, Any]:
    """Call chat completions and parse a JSON object from the reply.

    Retries the model once if the first reply is not parseable JSON (common with
    invalid backslash escapes in long free-text fields).
    """
    last_error: Exception | None = None
    for attempt in range(max_parse_retries + 1):
        attempt_user = user
        if attempt > 0:
            attempt_user = (
                user
                + "\n\nIMPORTANT: Your previous reply was not valid JSON. "
                "Reply again with ONLY a single JSON object. "
                "In strings, escape backslashes as \\\\ and quotes as \\\". "
                "Do not use raw LaTeX or Windows-style paths without escaping."
            )
        response = client.chat.completions.create(
            model=model,
            temperature=temperature if attempt == 0 else min(temperature, 0.2),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": attempt_user},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            last_error = LLMError("Empty model response")
            continue
        try:
            return parse_json_object(content)
        except LLMError as exc:
            last_error = exc
            continue
    assert last_error is not None
    raise last_error


def parse_json_object(text: str) -> dict[str, Any]:
    """Extract a JSON object from model text (allows fences + light repair)."""
    cleaned = _strip_fences(text.strip())
    candidates = [cleaned]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end > start:
        sliced = cleaned[start : end + 1]
        if sliced != cleaned:
            candidates.append(sliced)

    errors: list[str] = []
    for raw in candidates:
        for variant in (raw, _repair_json_text(raw)):
            try:
                data = json.loads(variant)
            except json.JSONDecodeError as exc:
                errors.append(str(exc))
                continue
            if not isinstance(data, dict):
                raise LLMError("Model JSON root must be an object")
            return data

    detail = errors[-1] if errors else "unknown parse error"
    raise LLMError(
        "Could not parse JSON from the model (often invalid \\ escapes in text). "
        f"Parser said: {detail}. Try the same command again."
    )


def _strip_fences(text: str) -> str:
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        return fence.group(1).strip()
    return text


def _repair_json_text(s: str) -> str:
    """Best-effort fixes for common LLM JSON mistakes.

    Backslash repair runs inside strings. Trailing commas are removed only
    outside strings, so a value like ``"hello, }"`` is left intact.
    """
    return _strip_trailing_commas_outside_strings(_repair_invalid_escapes_in_strings(s))


def _repair_invalid_escapes_in_strings(s: str) -> str:
    """Turn invalid ``\\x`` sequences inside JSON strings into ``\\\\x``."""
    out: list[str] = []
    in_str = False
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if not in_str:
            out.append(ch)
            if ch == '"':
                in_str = True
            i += 1
            continue
        if ch != "\\":
            out.append(ch)
            if ch == '"':
                in_str = False
            i += 1
            continue
        nxt = s[i + 1] if i + 1 < n else ""
        if nxt in _JSON_SIMPLE_ESCAPES:
            out.append(ch)
            out.append(nxt)
            i += 2
            continue
        if (
            nxt == "u"
            and i + 5 < n
            and all(c in _JSON_HEX for c in s[i + 2 : i + 6])
        ):
            out.append(s[i : i + 6])
            i += 6
            continue
        # Invalid or truncated escape: emit a literal backslash.
        out.append("\\\\")
        i += 1
    return "".join(out)


def _strip_trailing_commas_outside_strings(s: str) -> str:
    """Drop commas that sit immediately before ``}`` or ``]`` outside strings."""
    out: list[str] = []
    in_str = False
    escaped = False
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if in_str:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == ",":
            j = i + 1
            while j < n and s[j] in " \t\r\n":
                j += 1
            if j < n and s[j] in "}]":
                i += 1
                continue
        out.append(ch)
        i += 1
    return "".join(out)
