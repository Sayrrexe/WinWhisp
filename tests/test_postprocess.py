import pytest

from transcrb.text.vocab import Vocab
from transcrb.text.postprocess import (
    apply_replacements,
    is_hallucination,
    is_repetition_loop,
    normalize_whitespace,
    postprocess,
    preserve_sentence_case,
)


def test_apply_replacements_basic():
    assert apply_replacements("коммит готов", {"коммит": "commit"}) == "commit готов"


def test_longest_match_first():
    rules = {"гит": "git", "гит хаб": "GitHub"}
    assert apply_replacements("откроем гит хаб", rules) == "откроем GitHub"


def test_case_insensitive_by_default():
    assert apply_replacements("Коммит", {"коммит": "commit"}) == "commit"


def test_word_boundary_unicode():
    # "агитация" содержит "гит" но не должно трогаться
    out = apply_replacements("идёт агитация", {"гит": "git"})
    assert out == "идёт агитация"


def test_hyphenated_word():
    out = apply_replacements("гит-игнор нужен", {"гит-игнор": "gitignore"})
    assert out == "gitignore нужен"


def test_idempotent():
    rules = {"коммит": "commit"}
    once = apply_replacements("коммит", rules)
    twice = apply_replacements(once, rules)
    assert once == twice == "commit"


def test_empty_inputs():
    assert apply_replacements("", {"a": "b"}) == ""
    assert apply_replacements("hello", {}) == "hello"


def test_preserve_sentence_case():
    assert preserve_sentence_case("hello world. next line.") == "Hello world. Next line."


def test_normalize_whitespace():
    assert normalize_whitespace("  a   b\n  c  ") == "a b\nc"


def test_is_hallucination_matches():
    assert is_hallucination("Спасибо за просмотр.", ["Спасибо за просмотр."])
    assert is_hallucination("Спасибо за просмотр", ["Спасибо за просмотр."])
    assert is_hallucination("", ["x"])
    assert not is_hallucination("реальный текст", ["Спасибо за просмотр."])


def test_is_hallucination_case_insensitive():
    assert is_hallucination("СПАСИБО ЗА ПРОСМОТР", ["спасибо за просмотр"])


def test_is_hallucination_substring_anchor():
    bl = ["~DimaTorzok"]
    assert is_hallucination("Субтитры создавал DimaTorzok", bl)
    assert is_hallucination("субтитры делал dimatorzok!", bl)
    assert not is_hallucination("обычный текст", bl)


def test_postprocess_full_pipeline():
    v = Vocab(replacements={"коммит": "commit"}, preserve_sentence_case=True)
    out = postprocess("коммит готов. ребейз дальше.", v, trailing_space=True)
    assert out.startswith("Commit готов.")
    assert out.endswith(" ")


# ---------------------------------------------------------------------------
# apply_replacements — extended
# ---------------------------------------------------------------------------

import pytest


@pytest.mark.parametrize("text,expected", [
    ("AI assistant готов", "ИИ-ассистент готов"),
    ("спросим AI", "спросим ИИ"),
])
def test_apply_replacements_longest_match_latin(text, expected):
    rules = {"AI": "ИИ", "AI assistant": "ИИ-ассистент"}
    assert apply_replacements(text, rules) == expected


def test_apply_replacements_digit_boundary_no_replace():
    assert apply_replacements("AI42 работает", {"AI": "ИИ"}) == "AI42 работает"


def test_apply_replacements_digit_boundary_standalone():
    assert apply_replacements("AI работает AI42", {"AI": "ИИ"}) == "ИИ работает AI42"


def test_apply_replacements_cyrillic_boundary_no_replace():
    assert apply_replacements("аИИб текст", {"ИИ": "AI"}) == "аИИб текст"


def test_apply_replacements_cyrillic_boundary_standalone():
    assert apply_replacements("нужен ИИ сейчас", {"ИИ": "AI"}) == "нужен AI сейчас"


def test_apply_replacements_punctuation_boundary():
    assert apply_replacements("commit, push", {"commit": "коммит"}) == "коммит, push"


@pytest.mark.parametrize("text,expected", [
    ("гит хаб и гит", "GitHub и git"),
    ("гит и гит хаб", "git и GitHub"),
])
def test_apply_replacements_longest_match_cyrillic(text, expected):
    rules = {"гит": "git", "гит хаб": "GitHub"}
    assert apply_replacements(text, rules) == expected


def test_apply_replacements_case_sensitive_no_match():
    assert apply_replacements("Коммит", {"Коммит": "commit"}, case_sensitive=False) == "commit"
    assert apply_replacements("коммит", {"Коммит": "commit"}, case_sensitive=True) == "коммит"


def test_apply_replacements_case_sensitive_exact_match():
    assert apply_replacements("Коммит", {"Коммит": "commit"}, case_sensitive=True) == "commit"


def test_apply_replacements_multiple_occurrences():
    out = apply_replacements("гит гит гит", {"гит": "git"})
    assert out == "git git git"


def test_apply_replacements_single_pass_no_reapply():
    out = apply_replacements("a", {"a": "aa"})
    assert out == "aa"


def test_apply_replacements_underscore_boundary():
    out = apply_replacements("my_AI_module", {"AI": "ИИ"})
    assert out == "my_AI_module"


def test_apply_replacements_hyphenated_boundary():
    out = apply_replacements("pre-AI-post", {"AI": "ИИ"})
    assert out == "pre-ИИ-post"


# ---------------------------------------------------------------------------
# preserve_sentence_case — extended
# ---------------------------------------------------------------------------

def test_preserve_sentence_case_start_of_string():
    assert preserve_sentence_case("hello") == "Hello"


def test_preserve_sentence_case_already_upper():
    assert preserve_sentence_case("Hello world") == "Hello world"


def test_preserve_sentence_case_after_exclamation():
    assert preserve_sentence_case("стоп! иди") == "Стоп! Иди"


def test_preserve_sentence_case_after_question():
    assert preserve_sentence_case("где? там") == "Где? Там"


def test_preserve_sentence_case_multiple_sentences():
    out = preserve_sentence_case("раз. два. три.")
    assert out == "Раз. Два. Три."


def test_preserve_sentence_case_empty():
    assert preserve_sentence_case("") == ""


def test_preserve_sentence_case_newline_not_triggered():
    out = preserve_sentence_case("первый\nвторой")
    assert out == "Первый\nвторой"


def test_preserve_sentence_case_requires_space_after_punctuation():
    assert preserve_sentence_case("end.begin") == "End.begin"


@pytest.mark.parametrize("text,expected", [
    ("нет.", "Нет."),
    ("один. два! три? четыре.", "Один. Два! Три? Четыре."),
])
def test_preserve_sentence_case_parametrized(text, expected):
    assert preserve_sentence_case(text) == expected


# ---------------------------------------------------------------------------
# normalize_whitespace — extended
# ---------------------------------------------------------------------------

def test_normalize_whitespace_tabs():
    assert normalize_whitespace("a\tb") == "a b"


def test_normalize_whitespace_leading_trailing():
    assert normalize_whitespace("  hello  ") == "hello"


def test_normalize_whitespace_mixed_spaces_tabs():
    assert normalize_whitespace("a \t b") == "a b"


def test_normalize_whitespace_newline_preserved():
    assert normalize_whitespace("a\nb") == "a\nb"


def test_normalize_whitespace_spaces_around_newline():
    assert normalize_whitespace("a  \n  b") == "a\nb"


def test_normalize_whitespace_only_spaces():
    assert normalize_whitespace("   ") == ""


def test_normalize_whitespace_only_newline():
    assert normalize_whitespace("\n") == ""


def test_normalize_whitespace_multiple_newlines():
    assert normalize_whitespace("a\n\nb") == "a\n\nb"


def test_normalize_whitespace_empty():
    assert normalize_whitespace("") == ""


# ---------------------------------------------------------------------------
# is_hallucination — extended
# ---------------------------------------------------------------------------

def test_is_hallucination_only_whitespace():
    assert is_hallucination("   ", ["anything"])


def test_is_hallucination_tilde_case_insensitive():
    assert is_hallucination("ПОДПИШИСЬ НА КАНАЛ пожалуйста", ["~подпишись на канал"])


def test_is_hallucination_tilde_empty_needle_skipped():
    assert not is_hallucination("реальный текст", ["~"])


def test_is_hallucination_exact_with_ellipsis_stripped():
    assert is_hallucination("Спасибо за просмотр…", ["Спасибо за просмотр"])


def test_is_hallucination_exact_mismatch():
    assert not is_hallucination("Спасибо за внимание", ["Спасибо за просмотр"])


def test_is_hallucination_empty_entry_in_blocklist_skipped():
    assert not is_hallucination("нормальный текст", ["", "   "])


@pytest.mark.parametrize("text,blocklist,expected", [
    ("Thanks for watching!", ["~thanks for watching"], True),
    ("Please subscribe to our channel", ["~please subscribe"], True),
    ("Hello everyone", ["~thanks for watching"], False),
    ("Субтитры создавал DimaTorzok", ["~DimaTorzok"], True),
])
def test_is_hallucination_parametrized(text, blocklist, expected):
    assert is_hallucination(text, blocklist) == expected


def test_is_hallucination_exact_no_tilde_no_partial():
    assert not is_hallucination("Спасибо за просмотр и подписку", ["Спасибо за просмотр"])


# ---------------------------------------------------------------------------
# postprocess — extended
# ---------------------------------------------------------------------------

def test_postprocess_trailing_space_false():
    v = Vocab(replacements={}, preserve_sentence_case=False)
    out = postprocess("hello world", v, trailing_space=False)
    assert not out.endswith(" ")
    assert out == "hello world"


def test_postprocess_empty_text_no_trailing_space():
    v = Vocab(replacements={})
    out = postprocess("", v, trailing_space=True)
    assert out == ""


def test_postprocess_already_trailing_space_not_doubled():
    v = Vocab(replacements={}, preserve_sentence_case=False)
    out = postprocess("hello ", v, trailing_space=True)
    assert out == "hello "


def test_postprocess_replacements_before_case():
    v = Vocab(replacements={"коммит": "commit"}, preserve_sentence_case=True)
    out = postprocess("коммит сделан", v, trailing_space=False)
    assert out == "Commit сделан"


def test_postprocess_whitespace_normalized():
    v = Vocab(replacements={}, preserve_sentence_case=False)
    out = postprocess("  много   пробелов  ", v, trailing_space=False)
    assert out == "много пробелов"


def test_postprocess_preserve_case_disabled():
    v = Vocab(replacements={}, preserve_sentence_case=False)
    out = postprocess("первый. второй.", v, trailing_space=False)
    assert out == "первый. второй."


def test_postprocess_empty_rules_passthrough():
    v = Vocab(replacements={}, preserve_sentence_case=True)
    out = postprocess("hello world", v, trailing_space=False)
    assert out == "Hello world"


# ---------------------------------------------------------------------------
# is_repetition_loop
# ---------------------------------------------------------------------------

def test_is_repetition_loop_single_word_spammed():
    assert is_repetition_loop("Vmware vmware vmware vmware vmware")


def test_is_repetition_loop_punctuated_repeats():
    assert is_repetition_loop("Vmware. Vmware. Vmware. Vmware.")


def test_is_repetition_loop_bigram_repeats():
    assert is_repetition_loop(
        "iPhone X, iPhone X, iPhone X, iPhone X, iPhone X"
    )


def test_is_repetition_loop_trigram_repeats():
    assert is_repetition_loop(
        "ха ха ха ха ха ха ха ха ха ха ха ха"
    )


def test_is_repetition_loop_normal_speech_false():
    assert not is_repetition_loop(
        "Заголовки, разница заголовков и так далее, всё нормально."
    )


def test_is_repetition_loop_short_text_false():
    assert not is_repetition_loop("vmware vmware")
    assert not is_repetition_loop("")
    assert not is_repetition_loop("привет")


def test_is_repetition_loop_three_repeats_under_threshold():
    assert not is_repetition_loop("vmware vmware vmware")


def test_is_repetition_loop_mixed_filler_breaks_run():
    assert not is_repetition_loop(
        "vmware и потом vmware а после vmware а ещё vmware"
    )


def test_is_repetition_loop_case_insensitive():
    assert is_repetition_loop("VMware VMWARE vmware Vmware vmware")


@pytest.mark.parametrize("text", [
    "Спасибо. Спасибо. Спасибо. Спасибо.",
    "Да да да да да да",
    "Hello hello hello hello hello",
])
def test_is_repetition_loop_parametrized_true(text):
    assert is_repetition_loop(text)


# ---------------------------------------------------------------------------
# extended hallucinations entries
# ---------------------------------------------------------------------------

def test_is_hallucination_prodolzhenie_v_sleduyuschey_chasti():
    from transcrb.text.vocab import BUILTIN_HALLUCINATIONS

    assert is_hallucination(
        "ПРОДОЛЖЕНИЕ В СЛЕДУЮЩЕЙ ЧАСТИ", BUILTIN_HALLUCINATIONS
    )
