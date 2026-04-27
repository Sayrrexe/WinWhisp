from transcrb.text.vocab import (
    BUILTIN_HALLUCINATIONS,
    PROMPT_PREFIX,
    TOKEN_BUDGET,
    Vocab,
    build_hotwords_string,
    build_initial_prompt,
    is_prompt_echo,
    load_vocab,
    _rough_token_count,
)
from pathlib import Path
import pytest
import yaml


# ---------------------------------------------------------------------------
# Vocab dataclass defaults & hallucinations_all
# ---------------------------------------------------------------------------


def test_vocab_defaults():
    v = Vocab()
    assert v.hotwords == []
    assert v.replacements == {}
    assert v.hallucinations == []
    assert v.case_sensitive is False
    assert v.preserve_sentence_case is True


def test_vocab_hallucinations_all_empty_user_list():
    v = Vocab()
    assert v.hallucinations_all == BUILTIN_HALLUCINATIONS


def test_vocab_hallucinations_all_appends_user():
    v = Vocab(hallucinations=["custom phrase"])
    assert v.hallucinations_all[-1] == "custom phrase"
    assert v.hallucinations_all[: len(BUILTIN_HALLUCINATIONS)] == BUILTIN_HALLUCINATIONS


def test_vocab_hallucinations_all_order():
    v = Vocab(hallucinations=["a", "b"])
    all_h = v.hallucinations_all
    assert all_h.index("a") > all_h.index(BUILTIN_HALLUCINATIONS[-1])
    assert all_h.index("a") < all_h.index("b")


def test_vocab_hallucinations_all_mutation_reflects():
    v = Vocab(hallucinations=["x"])
    v.hallucinations.append("y")
    assert "y" in v.hallucinations_all


def test_vocab_hallucinations_all_builtin_non_empty():
    assert len(BUILTIN_HALLUCINATIONS) > 0


# ---------------------------------------------------------------------------
# TOKEN_BUDGET invariant
# ---------------------------------------------------------------------------


def test_token_budget_below_whisper_hard_cap():
    assert TOKEN_BUDGET < 224


def test_token_budget_value():
    assert TOKEN_BUDGET == 220


# ---------------------------------------------------------------------------
# _rough_token_count
# ---------------------------------------------------------------------------


def test_rough_token_count_empty_returns_one():
    assert _rough_token_count("") == 1


def test_rough_token_count_short_string_minimum_one():
    assert _rough_token_count("ab") == 1


@pytest.mark.parametrize("s,expected", [
    ("abc", 1),
    ("abcd", 1),
    ("abcdef", 2),
    ("aaaaaaaaa", 3),
])
def test_rough_token_count_multiples(s, expected):
    assert _rough_token_count(s) == expected


def test_rough_token_count_cyrillic_same_as_ascii_by_length():
    assert _rough_token_count("абв") == _rough_token_count("abc")


def test_rough_token_count_long_string():
    assert _rough_token_count("x" * 300) == 100


# ---------------------------------------------------------------------------
# build_initial_prompt — basic
# ---------------------------------------------------------------------------


def test_empty_hotwords_returns_empty_prompt():
    assert build_initial_prompt([]) == ""


def test_prompt_contains_terms():
    prompt = build_initial_prompt(["gitignore", "async", "commit"])
    assert "gitignore" in prompt
    assert "async" in prompt
    assert "commit" in prompt
    assert prompt.endswith(".")


def test_prompt_ends_with_dot_not_comma():
    prompt = build_initial_prompt(["alpha", "beta"], token_counter=len, budget=10000)
    assert prompt.endswith(".")
    assert not prompt.endswith(",.")
    assert ", " not in prompt.split(".")[-1]


def test_prompt_truncates_when_first_word_too_big():
    prompt = build_initial_prompt(["x" * 1000], token_counter=len, budget=50)
    assert prompt == ""


def test_prompt_respects_budget_with_fake_tokenizer():
    calls = {"n": 0}

    def counter(s: str) -> int:
        calls["n"] += 1
        return len(s)

    prompt = build_initial_prompt(["a" * 10, "b" * 10, "c" * 1000], counter, budget=100)
    assert len(prompt) <= 101
    assert "c" * 1000 not in prompt
    assert calls["n"] > 0


def test_prompt_first_word_fits_exactly_at_budget():
    prefix = "P: "
    word = "w"
    # candidate = "P: w, " which has len 6; set budget=6
    prompt = build_initial_prompt([word], token_counter=len, budget=6, prefix=prefix)
    assert word in prompt


def test_prompt_prefix_alone_exceeds_budget_returns_empty():
    long_prefix = "x" * 200
    prompt = build_initial_prompt(["a"], token_counter=len, budget=10, prefix=long_prefix)
    assert prompt == ""


def test_prompt_one_word_fits_second_doesnt():
    def counter(s: str) -> int:
        return len(s)

    prompt = build_initial_prompt(["abc", "d" * 1000], counter, budget=50, prefix="")
    assert "abc" in prompt
    assert "d" * 1000 not in prompt
    assert prompt.endswith(".")


def test_prompt_custom_empty_prefix():
    prompt = build_initial_prompt(["alpha"], token_counter=len, budget=100, prefix="")
    assert prompt == "alpha."


def test_prompt_idempotent():
    words = ["gitignore", "async", "commit"]
    assert build_initial_prompt(words) == build_initial_prompt(words)


# ---------------------------------------------------------------------------
# build_initial_prompt — 224-token boundary tests (explicit budget=224)
# ---------------------------------------------------------------------------


def test_prompt_budget_224_exactly():
    def counter(s: str) -> int:
        return len(s)

    prefix = ""
    # word + ", " = 3 chars; 224 // 3 = 74 full words; test the last fits
    word = "ab"  # "ab, " = 4 chars each
    n_words = 224 // 4  # 56 words of 4 chars each
    words = [word] * n_words
    prompt = build_initial_prompt(words, counter, budget=224, prefix=prefix)
    assert len(prompt) <= 224


def test_prompt_budget_223_does_not_include_word_that_overflows():
    def counter(s: str) -> int:
        return len(s)

    # prefix="" + word "x"*222 + ", " = 224 chars > 223 budget
    prompt = build_initial_prompt(["x" * 222], counter, budget=223, prefix="")
    assert prompt == ""


def test_prompt_budget_225_allows_one_extra_token_vs_224():
    def counter(s: str) -> int:
        return len(s)

    # prefix="" word "xxx" → candidate "xxx, " = 5 chars ≤ 225
    prompt_225 = build_initial_prompt(["xxx"], counter, budget=225, prefix="")
    prompt_224 = build_initial_prompt(["xxx"], counter, budget=224, prefix="")
    # Both should include it; both should succeed
    assert "xxx" in prompt_225
    assert "xxx" in prompt_224


def test_prompt_budget_224_very_long_single_word():
    prompt = build_initial_prompt(["z" * 500], token_counter=len, budget=224, prefix="")
    assert prompt == ""


def test_prompt_budget_exact_boundary_word_included_not_excluded():
    def counter(s: str) -> int:
        return len(s)

    prefix = ""
    # candidate = "fit, " → len 5; budget=5 means count(candidate)=5 which is NOT > 5
    prompt = build_initial_prompt(["fit"], counter, budget=5, prefix=prefix)
    assert "fit" in prompt


def test_prompt_budget_one_over_excludes_word():
    def counter(s: str) -> int:
        return len(s)

    # "fit, " = 5 chars; budget=4 → 5 > 4 → excluded
    prompt = build_initial_prompt(["fit"], counter, budget=4, prefix="")
    assert prompt == ""


# ---------------------------------------------------------------------------
# build_hotwords_string
# ---------------------------------------------------------------------------


def test_hotwords_string_empty():
    assert build_hotwords_string([]) == ""


def test_hotwords_string_single():
    assert build_hotwords_string(["only"]) == "only"


def test_hotwords_string_joined():
    assert build_hotwords_string(["a", "b", "c"]) == "a b c"


def test_hotwords_string_unicode_preserved():
    words = ["гитхаб", "питон", "коммит"]
    assert build_hotwords_string(words) == "гитхаб питон коммит"


def test_hotwords_string_with_internal_spaces():
    assert build_hotwords_string(["git hub", "pull request"]) == "git hub pull request"


def test_hotwords_string_idempotent():
    words = ["a", "b"]
    assert build_hotwords_string(words) == build_hotwords_string(words)


# ---------------------------------------------------------------------------
# load_vocab — basic
# ---------------------------------------------------------------------------


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


def test_load_vocab_empty_file(tmp_path):
    p = tmp_path / "empty.yaml"
    p.write_text("", encoding="utf-8")
    v = load_vocab(p)
    assert v.hotwords == []
    assert v.replacements == {}
    assert v.hallucinations == []
    assert v.case_sensitive is False
    assert v.preserve_sentence_case is True


def test_load_vocab_partial_fields_hotwords_only(tmp_path):
    p = tmp_path / "partial.yaml"
    p.write_text(yaml.safe_dump({"hotwords": ["alpha"]}), encoding="utf-8")
    v = load_vocab(p)
    assert v.hotwords == ["alpha"]
    assert v.replacements == {}
    assert v.hallucinations == []


def test_load_vocab_partial_fields_replacements_only(tmp_path):
    p = tmp_path / "r.yaml"
    p.write_text(
        yaml.safe_dump({"replacements": {"a": "b"}}, allow_unicode=True),
        encoding="utf-8",
    )
    v = load_vocab(p)
    assert v.replacements == {"a": "b"}
    assert v.hotwords == []


def test_load_vocab_options_null(tmp_path):
    p = tmp_path / "optnull.yaml"
    p.write_text(yaml.safe_dump({"options": None}), encoding="utf-8")
    v = load_vocab(p)
    assert v.case_sensitive is False
    assert v.preserve_sentence_case is True


def test_load_vocab_missing_options_field(tmp_path):
    p = tmp_path / "noopts.yaml"
    p.write_text(yaml.safe_dump({"hotwords": ["x"]}), encoding="utf-8")
    v = load_vocab(p)
    assert v.case_sensitive is False
    assert v.preserve_sentence_case is True


def test_load_vocab_preserve_sentence_case_false(tmp_path):
    p = tmp_path / "psc.yaml"
    p.write_text(
        yaml.safe_dump({"options": {"preserve_sentence_case": False}}),
        encoding="utf-8",
    )
    v = load_vocab(p)
    assert v.preserve_sentence_case is False


def test_load_vocab_case_sensitive_default_false(tmp_path):
    p = tmp_path / "cs.yaml"
    p.write_text(yaml.safe_dump({"options": {}}), encoding="utf-8")
    v = load_vocab(p)
    assert v.case_sensitive is False


def test_load_vocab_malformed_yaml_raises(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("key: [unclosed", encoding="utf-8")
    with pytest.raises(yaml.YAMLError):
        load_vocab(p)


def test_load_vocab_idempotent(tmp_path):
    p = tmp_path / "idem.yaml"
    p.write_text(
        yaml.safe_dump(
            {"hotwords": ["x"], "replacements": {"a": "b"}},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    v1 = load_vocab(p)
    v2 = load_vocab(p)
    assert v1.hotwords == v2.hotwords
    assert v1.replacements == v2.replacements
    assert v1.hallucinations == v2.hallucinations
    assert v1.case_sensitive == v2.case_sensitive
    assert v1.preserve_sentence_case == v2.preserve_sentence_case


# ---------------------------------------------------------------------------
# load_vocab — Unicode in hotwords / replacements
# ---------------------------------------------------------------------------


def test_load_vocab_cyrillic_hotwords(tmp_path):
    p = tmp_path / "ru.yaml"
    words = ["питон", "гитхаб", "коммит"]
    p.write_text(yaml.safe_dump({"hotwords": words}, allow_unicode=True), encoding="utf-8")
    v = load_vocab(p)
    assert v.hotwords == words


def test_load_vocab_chinese_hotwords(tmp_path):
    p = tmp_path / "zh.yaml"
    words = ["代码", "提交"]
    p.write_text(yaml.safe_dump({"hotwords": words}, allow_unicode=True), encoding="utf-8")
    v = load_vocab(p)
    assert v.hotwords == words


def test_load_vocab_emoji_in_hotwords(tmp_path):
    p = tmp_path / "emoji.yaml"
    words = ["python🐍", "git🔀"]
    p.write_text(yaml.safe_dump({"hotwords": words}, allow_unicode=True), encoding="utf-8")
    v = load_vocab(p)
    assert v.hotwords == words


def test_load_vocab_unicode_replacements_roundtrip(tmp_path):
    p = tmp_path / "uni_repl.yaml"
    repl = {"коммит": "commit", "ветка": "branch"}
    p.write_text(yaml.safe_dump({"replacements": repl}, allow_unicode=True), encoding="utf-8")
    v = load_vocab(p)
    assert v.replacements == repl


# ---------------------------------------------------------------------------
# load_vocab — hallucinations field
# ---------------------------------------------------------------------------


def test_load_vocab_hallucinations_loaded(tmp_path):
    p = tmp_path / "hall.yaml"
    p.write_text(
        yaml.safe_dump({"hallucinations": ["Продолжение следует", "Конец видео"]},
                       allow_unicode=True),
        encoding="utf-8",
    )
    v = load_vocab(p)
    assert "Продолжение следует" in v.hallucinations
    assert "Конец видео" in v.hallucinations


def test_load_vocab_hallucinations_appear_in_hallucinations_all(tmp_path):
    p = tmp_path / "hall2.yaml"
    p.write_text(
        yaml.safe_dump({"hallucinations": ["custom"]}, allow_unicode=True),
        encoding="utf-8",
    )
    v = load_vocab(p)
    assert "custom" in v.hallucinations_all


def test_load_vocab_empty_hallucinations_list(tmp_path):
    p = tmp_path / "hall3.yaml"
    p.write_text(yaml.safe_dump({"hallucinations": []}), encoding="utf-8")
    v = load_vocab(p)
    assert v.hallucinations == []
    assert v.hallucinations_all == BUILTIN_HALLUCINATIONS


# ---------------------------------------------------------------------------
# load_vocab — null / missing list fields
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["hotwords", "hallucinations"])
def test_load_vocab_null_list_field_defaults_to_empty(tmp_path, field):
    p = tmp_path / f"null_{field}.yaml"
    p.write_text(yaml.safe_dump({field: None}), encoding="utf-8")
    v = load_vocab(p)
    assert getattr(v, field) == []


def test_load_vocab_null_replacements_defaults_to_empty(tmp_path):
    p = tmp_path / "null_repl.yaml"
    p.write_text(yaml.safe_dump({"replacements": None}), encoding="utf-8")
    v = load_vocab(p)
    assert v.replacements == {}


# ---------------------------------------------------------------------------
# is_prompt_echo
# ---------------------------------------------------------------------------


def test_is_prompt_echo_empty_text():
    assert not is_prompt_echo("")


def test_is_prompt_echo_empty_prefix():
    assert not is_prompt_echo("any text", prompt_prefix="")


def test_is_prompt_echo_real_speech_passes():
    assert not is_prompt_echo("Сделай рефакторинг этой функции, она слишком длинная.")


def test_is_prompt_echo_short_text_no_overlap():
    # Биграмма не пересекается с префиксом → не echo.
    assert not is_prompt_echo("Привет мир")


def test_is_prompt_echo_exact_prefix_match():
    assert is_prompt_echo("Это техническая диктовка по программированию.")


def test_is_prompt_echo_log_artifact_strings_152():
    # Якорь из winwhisp.log:152 — Whisper склеил два куска префикса.
    raw = (
        "Используются термины по программированию. "
        "Используются термины по программированию."
    )
    assert is_prompt_echo(raw)


def test_is_prompt_echo_partial_phrase_used_in_speech():
    # «Это техническая» в обычной речи маловероятно, но триграмму "это техническая диктовка" ловим.
    assert is_prompt_echo("Это техническая диктовка, я записываю.")


@pytest.mark.parametrize("text", [
    "Используются термины по программированию.",  # склейка двух предложений префикса
    "Это техническая диктовка по программированию",
    "по программированию используются термины — продолжаем.",
])
def test_is_prompt_echo_known_artifacts(text):
    assert is_prompt_echo(text)


@pytest.mark.parametrize("text", [
    "Сегодня я зарегистрировался на сайте.",
    "Поставь чекбокс рядом с кнопкой.",
    "Создать аккаунт.",
    "График нелогичный, сделай его живым.",
])
def test_is_prompt_echo_normal_speech_not_flagged(text):
    assert not is_prompt_echo(text)


def test_is_prompt_echo_case_insensitive():
    assert is_prompt_echo("ИСПОЛЬЗУЮТСЯ ТЕРМИНЫ ПО ПРОГРАММИРОВАНИЮ")


def test_is_prompt_echo_punctuation_ignored():
    assert is_prompt_echo("используются! термины? по... программированию—")


def test_is_prompt_echo_custom_prefix():
    assert is_prompt_echo("alpha beta gamma delta", prompt_prefix="alpha beta gamma")


def test_is_prompt_echo_one_bigram_overlap_not_enough():
    # Только (используются, термины) совпадает — одной биграммы мало.
    assert not is_prompt_echo("Используются термины коммит и пуш сделаны.")


def test_is_prompt_echo_threshold_param():
    text = "Используются термины коммита."
    # Пересекается ровно одна биграмма (используются, термины).
    assert not is_prompt_echo(text, min_bigram_overlap=2)
    assert is_prompt_echo(text, min_bigram_overlap=1)


def test_is_prompt_echo_uses_default_prefix():
    assert is_prompt_echo("по программированию используются термины")
