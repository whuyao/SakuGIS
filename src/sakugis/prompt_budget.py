"""Deterministic prompt compaction without breaking structured JSON."""

from __future__ import annotations

import json
from typing import Any, Iterable, List


QUERY_CHAR_LIMIT = 4000
EVIDENCE_PROMPT_CHAR_LIMIT = 12000
CANDIDATE_PROMPT_CHAR_LIMIT = 18000
VERIFY_PROMPT_CHAR_LIMIT = 32000
QWEN_TOTAL_PROMPT_CHAR_LIMIT = 48000


class PromptBudgetError(ValueError):
    """Raised locally when a valid structured prompt cannot fit its budget."""


def shorten_text(value: Any, max_chars: int) -> str:
    text = str(value or "").strip()
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars < 24:
        return text[:max_chars]
    marker = " …[truncated]… "
    remaining = max_chars - len(marker)
    head = max(1, int(remaining * 0.7))
    tail = max(1, remaining - head)
    return text[:head] + marker + text[-tail:]


def compact_text_list(
    values: Iterable[Any],
    max_items: int = 4,
    max_chars: int = 96,
) -> List[str]:
    result: List[str] = []
    for value in values or ():
        compacted = shorten_text(value, max_chars)
        if compacted and compacted not in result:
            result.append(compacted)
        if len(result) >= max_items:
            break
    return result


def compact_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def build_bounded_prompt(
    prefix: str,
    query: str,
    suffix: str,
    max_chars: int,
) -> str:
    """Fit the free-text query around an already valid structured suffix."""

    fixed_size = len(prefix) + len(suffix)
    if fixed_size > max_chars:
        raise PromptBudgetError(
            f"Structured prompt requires {fixed_size} characters; "
            f"budget is {max_chars}."
        )
    query_budget = min(
        QUERY_CHAR_LIMIT,
        max(0, max_chars - fixed_size),
    )
    prompt = prefix + shorten_text(query, query_budget) + suffix
    if len(prompt) > max_chars:
        raise PromptBudgetError(
            f"Prompt requires {len(prompt)} characters; budget is {max_chars}."
        )
    return prompt
