from transcrb.text.vocab import Vocab
from transcrb.text.postprocess import (
    apply_replacements,
    is_hallucination,
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
