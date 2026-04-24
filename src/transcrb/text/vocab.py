from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yaml


PROMPT_PREFIX = "Это техническая диктовка по программированию. Используются термины: "
TOKEN_BUDGET = 220  # небольшой запас от 224


@dataclass
class Vocab:
    hotwords: list[str] = field(default_factory=list)
    replacements: dict[str, str] = field(default_factory=dict)
    hallucinations: list[str] = field(default_factory=list)
    case_sensitive: bool = False
    preserve_sentence_case: bool = True


def load_vocab(path: Path) -> Vocab:
    if not path.exists():
        return Vocab()
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    opts = raw.get("options") or {}
    return Vocab(
        hotwords=list(raw.get("hotwords") or []),
        replacements=dict(raw.get("replacements") or {}),
        hallucinations=list(raw.get("hallucinations") or []),
        case_sensitive=bool(opts.get("case_sensitive", False)),
        preserve_sentence_case=bool(opts.get("preserve_sentence_case", True)),
    )


def _rough_token_count(s: str) -> int:
    # грубая эвристика: 1 токен ~ 3 символа (кириллица дороже) — используется только как запасной вариант
    return max(1, len(s) // 3)


def build_initial_prompt(
    hotwords: list[str],
    token_counter: Callable[[str], int] | None = None,
    budget: int = TOKEN_BUDGET,
    prefix: str = PROMPT_PREFIX,
) -> str:
    if not hotwords:
        return ""
    count = token_counter or _rough_token_count
    acc = prefix
    added = 0
    for w in hotwords:
        candidate = acc + w + ", "
        if count(candidate) > budget:
            break
        acc = candidate
        added += 1
    if added == 0:
        return ""
    return acc.rstrip(", ") + "."


def build_hotwords_string(hotwords: list[str]) -> str:
    return " ".join(hotwords)
