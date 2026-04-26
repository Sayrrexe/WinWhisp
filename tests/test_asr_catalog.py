import pytest

from transcrb.asr.catalog import DEFAULT_MODEL, MODELS, model_label

EXPECTED_KEYS = {"tiny", "small", "medium", "large-v3"}


# --- MODELS list structure ---

def test_models_is_list_of_five_tuples():
    for entry in MODELS:
        assert isinstance(entry, tuple)
        assert len(entry) == 5


def test_models_field_types():
    for key, name, desc, size_bytes, vram in MODELS:
        assert isinstance(key, str)
        assert isinstance(name, str)
        assert isinstance(desc, str)
        assert isinstance(size_bytes, int)
        assert isinstance(vram, str)


def test_models_size_bytes_positive():
    for _, _, _, size_bytes, _ in MODELS:
        assert size_bytes > 0


def test_models_no_empty_strings():
    for key, name, desc, _, vram in MODELS:
        assert key.strip()
        assert name.strip()
        assert desc.strip()
        assert vram.strip()


def test_models_contains_all_expected_keys():
    keys = {entry[0] for entry in MODELS}
    assert keys == EXPECTED_KEYS


def test_models_no_duplicate_keys():
    keys = [entry[0] for entry in MODELS]
    assert len(keys) == len(set(keys))


def test_models_no_duplicate_names():
    names = [entry[1] for entry in MODELS]
    assert len(names) == len(set(names))


def test_models_sizes_strictly_increasing():
    sizes = [entry[3] for entry in MODELS]
    assert sizes == sorted(sizes)


def test_models_vram_contains_gb():
    for _, _, _, _, vram in MODELS:
        assert "GB" in vram


@pytest.mark.parametrize("key,min_mb,max_mb", [
    ("tiny",     50,   200),
    ("small",    400,  600),
    ("medium",  1000, 2000),
    ("large-v3", 2000, 5000),
])
def test_models_size_bytes_plausible(key, min_mb, max_mb):
    row = next(r for r in MODELS if r[0] == key)
    size_mb = row[3] / (1024 * 1024)
    assert min_mb <= size_mb <= max_mb


# --- DEFAULT_MODEL ---

def test_default_model_is_string():
    assert isinstance(DEFAULT_MODEL, str)


def test_default_model_exists_in_catalog():
    keys = {entry[0] for entry in MODELS}
    assert DEFAULT_MODEL in keys


def test_default_model_value():
    assert DEFAULT_MODEL == "large-v3"


# --- model_label ---

@pytest.mark.parametrize("key,expected_label", [
    ("tiny",     "Tiny"),
    ("small",    "Small"),
    ("medium",   "Medium"),
    ("large-v3", "Large-v3"),
])
def test_model_label_known_keys(key, expected_label):
    assert model_label(key) == expected_label


def test_model_label_unknown_key_returns_key():
    assert model_label("nonexistent") == "nonexistent"


def test_model_label_empty_string_returns_empty():
    assert model_label("") == ""


def test_model_label_case_sensitive():
    assert model_label("Tiny") == "Tiny"
    assert model_label("TINY") == "TINY"


def test_model_label_default_model():
    assert model_label(DEFAULT_MODEL) == "Large-v3"


def test_model_label_all_catalog_keys_resolve_non_empty():
    for key, _, _, _, _ in MODELS:
        label = model_label(key)
        assert label
        assert label != key or key == label
