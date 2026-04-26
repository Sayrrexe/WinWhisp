from __future__ import annotations

import re

from transcrb.text.vocab import Vocab


_SENTENCE_START = re.compile(r"(^|[.!?]\s+)([^\s])")
_HORIZONTAL_WS = re.compile(r"[ \t]+")
_NEWLINE_WS = re.compile(r" *\n *")
_HALLUCINATION_TRAILING = ".!?…"


def _compile_rules(rules: dict[str, str], case_sensitive: bool) -> tuple[re.Pattern, dict[str, str]]:
    ordered = sorted(rules.keys(), key=len, reverse=True)
    flags = 0 if case_sensitive else re.IGNORECASE
    alt = "|".join(re.escape(k) for k in ordered)
    pattern = re.compile(rf"(?<!\w)({alt})(?!\w)", flags)
    lookup = rules if case_sensitive else {k.lower(): v for k, v in rules.items()}
    return pattern, lookup


def apply_replacements(text: str, rules: dict[str, str], case_sensitive: bool = False) -> str:
    if not text or not rules:
        return text
    pattern, lookup = _compile_rules(rules, case_sensitive)

    def sub(m: re.Match) -> str:
        key = m.group(1) if case_sensitive else m.group(1).lower()
        return lookup.get(key, m.group(0))

    return pattern.sub(sub, text)


def preserve_sentence_case(text: str) -> str:
    return _SENTENCE_START.sub(lambda m: m.group(1) + m.group(2).upper(), text)


def normalize_whitespace(text: str) -> str:
    text = _HORIZONTAL_WS.sub(" ", text)
    text = _NEWLINE_WS.sub("\n", text)
    return text.strip()


def _normalize_hallucination(s: str) -> str:
    return s.rstrip(_HALLUCINATION_TRAILING).strip().lower()


def is_hallucination(text: str, blocklist: list[str]) -> bool:
    t = text.strip()
    if not t:
        return True
    t_norm = _normalize_hallucination(t)
    for entry in blocklist:
        h = (entry or "").strip()
        if not h:
            continue
        if h.startswith("~"):
            needle = h[1:].strip().lower()
            if needle and needle in t_norm:
                return True
            continue
        if t_norm == _normalize_hallucination(h):
            return True
    return False


def postprocess(text: str, vocab: Vocab, trailing_space: bool = True) -> str:
    text = apply_replacements(text, vocab.replacements, vocab.case_sensitive)
    if vocab.preserve_sentence_case:
        text = preserve_sentence_case(text)
    text = normalize_whitespace(text)
    if trailing_space and text and not text.endswith(" "):
        text += " "
    return text
