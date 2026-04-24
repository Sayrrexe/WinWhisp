from transcrb.text.vocab import Vocab, build_initial_prompt, build_hotwords_string, load_vocab
from pathlib import Path
import yaml


def test_empty_hotwords_returns_empty_prompt():
    assert build_initial_prompt([]) == ""


def test_prompt_contains_terms():
    prompt = build_initial_prompt(["gitignore", "async", "commit"])
    assert "gitignore" in prompt
    assert "async" in prompt
    assert "commit" in prompt
    assert prompt.endswith(".")


def test_prompt_respects_budget_with_fake_tokenizer():
    calls = {"n": 0}

    def counter(s: str) -> int:
        calls["n"] += 1
        return len(s)  # 1 символ = 1 токен

    prompt = build_initial_prompt(["a" * 10, "b" * 10, "c" * 1000], counter, budget=100)
    assert len(prompt) <= 101
    assert "c" * 1000 not in prompt
    assert calls["n"] > 0


def test_prompt_truncates_when_first_word_too_big():
    def counter(s: str) -> int:
        return len(s)

    prompt = build_initial_prompt(["x" * 1000], counter, budget=50)
    assert prompt == ""


def test_hotwords_string_joined():
    assert build_hotwords_string(["a", "b", "c"]) == "a b c"


def test_load_vocab_missing_file(tmp_path):
    v = load_vocab(tmp_path / "nope.yaml")
    assert v.hotwords == []
    assert v.replacements == {}


def test_load_vocab_full(tmp_path):
    p = tmp_path / "v.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "hotwords": ["gitignore", "async"],
                "replacements": {"коммит": "commit"},
                "hallucinations": ["Спасибо за просмотр"],
                "options": {"case_sensitive": True, "preserve_sentence_case": False},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    v = load_vocab(p)
    assert v.hotwords == ["gitignore", "async"]
    assert v.replacements == {"коммит": "commit"}
    assert v.hallucinations == ["Спасибо за просмотр"]
    assert v.case_sensitive is True
    assert v.preserve_sentence_case is False
