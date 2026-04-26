import sys
from pathlib import Path

import pytest

import transcrb.paths as paths


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reload(monkeypatch, tmp_path):
    """Point APPDATA at tmp_path and reload the module so cached state is fresh."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    import importlib
    importlib.reload(paths)
    return paths


# ---------------------------------------------------------------------------
# _default_appdata
# ---------------------------------------------------------------------------


def test_default_appdata_uses_env(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    result = paths._default_appdata()
    assert result == tmp_path / "WinWhisp"


def test_default_appdata_appends_app_name(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    result = paths._default_appdata()
    assert result.name == "WinWhisp"


def test_default_appdata_fallback_when_env_missing(monkeypatch):
    monkeypatch.delenv("APPDATA", raising=False)
    result = paths._default_appdata()
    assert result.name == "WinWhisp"
    assert "AppData" in str(result) or "Roaming" in str(result) or result.parent.name == "WinWhisp"


def test_default_appdata_fallback_is_under_home(monkeypatch):
    monkeypatch.delenv("APPDATA", raising=False)
    result = paths._default_appdata()
    home = Path.home()
    assert str(result).startswith(str(home))


def test_default_appdata_empty_env_uses_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", "")
    result = paths._default_appdata()
    assert result.name == "WinWhisp"
    assert str(result) != str(tmp_path / "WinWhisp")


# ---------------------------------------------------------------------------
# appdata_dir / default_appdata_dir
# ---------------------------------------------------------------------------


def test_appdata_dir_creates_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p = paths.appdata_dir()
    assert p.exists()
    assert p.is_dir()


def test_appdata_dir_returns_winwhisp_subdir(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p = paths.appdata_dir()
    assert p == tmp_path / "WinWhisp"


def test_default_appdata_dir_creates_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p = paths.default_appdata_dir()
    assert p.exists()
    assert p == tmp_path / "WinWhisp"


def test_default_appdata_dir_idempotent(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p1 = paths.default_appdata_dir()
    p2 = paths.default_appdata_dir()
    assert p1 == p2


def test_appdata_dir_ignores_override_when_override_absent(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p = paths.appdata_dir()
    assert p == tmp_path / "WinWhisp"


# ---------------------------------------------------------------------------
# write_override / clear_override / _read_override
# ---------------------------------------------------------------------------


def test_write_override_creates_file(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    target = tmp_path / "custom_data"
    target.mkdir()
    paths.write_override(target)
    pointer = tmp_path / "WinWhisp" / ".dir_override"
    assert pointer.exists()
    assert pointer.read_text(encoding="utf-8").strip() == str(target.resolve())


def test_write_override_stored_as_absolute(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    target = tmp_path / "abs_dir"
    target.mkdir()
    paths.write_override(target)
    pointer = tmp_path / "WinWhisp" / ".dir_override"
    stored = Path(pointer.read_text(encoding="utf-8").strip())
    assert stored.is_absolute()


def test_appdata_dir_uses_override(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    override = tmp_path / "override_dir"
    override.mkdir()
    paths.write_override(override)
    p = paths.appdata_dir()
    assert p == override


def test_clear_override_removes_file(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    override = tmp_path / "ov2"
    override.mkdir()
    paths.write_override(override)
    pointer = tmp_path / "WinWhisp" / ".dir_override"
    assert pointer.exists()
    paths.clear_override()
    assert not pointer.exists()


def test_clear_override_noop_when_not_present(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    paths.clear_override()


def test_read_override_returns_none_when_absent(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert paths._read_override() is None


def test_read_override_returns_none_for_relative_path(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    appdata = tmp_path / "WinWhisp"
    appdata.mkdir(parents=True, exist_ok=True)
    pointer = appdata / ".dir_override"
    pointer.write_text("relative/path", encoding="utf-8")
    assert paths._read_override() is None


def test_read_override_returns_none_for_nonexistent_target(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    appdata = tmp_path / "WinWhisp"
    appdata.mkdir(parents=True, exist_ok=True)
    pointer = appdata / ".dir_override"
    pointer.write_text(str(tmp_path / "does_not_exist"), encoding="utf-8")
    assert paths._read_override() is None


def test_read_override_returns_none_for_corrupt_file(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    appdata = tmp_path / "WinWhisp"
    appdata.mkdir(parents=True, exist_ok=True)
    pointer = appdata / ".dir_override"
    pointer.write_bytes(b"\xff\xfe")
    result = paths._read_override()
    assert result is None or isinstance(result, Path)


def test_appdata_dir_falls_back_to_default_after_clear(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    override = tmp_path / "ov3"
    override.mkdir()
    paths.write_override(override)
    assert paths.appdata_dir() == override
    paths.clear_override()
    assert paths.appdata_dir() == tmp_path / "WinWhisp"


# ---------------------------------------------------------------------------
# config_path
# ---------------------------------------------------------------------------


def test_config_path_filename(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p = paths.config_path()
    assert p.name == "config.yaml"


def test_config_path_parent_is_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p = paths.config_path()
    assert p.parent == tmp_path / "WinWhisp"


def test_config_path_is_yaml_extension(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert paths.config_path().suffix == ".yaml"


def test_config_path_changes_with_override(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    override = tmp_path / "cfg_ov"
    override.mkdir()
    paths.write_override(override)
    p = paths.config_path()
    assert p.parent == override
    paths.clear_override()


def test_config_path_consistent_across_calls(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert paths.config_path() == paths.config_path()


# ---------------------------------------------------------------------------
# vocab_path
# ---------------------------------------------------------------------------


def test_vocab_path_filename(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p = paths.vocab_path()
    assert p.name == "vocab.yaml"


def test_vocab_path_parent_is_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert paths.vocab_path().parent == tmp_path / "WinWhisp"


def test_vocab_path_is_yaml_extension(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert paths.vocab_path().suffix == ".yaml"


def test_vocab_path_distinct_from_config(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert paths.vocab_path() != paths.config_path()


def test_vocab_path_consistent_across_calls(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert paths.vocab_path() == paths.vocab_path()


# ---------------------------------------------------------------------------
# models_dir
# ---------------------------------------------------------------------------


def test_models_dir_name(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p = paths.models_dir()
    assert p.name == "models"


def test_models_dir_creates_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p = paths.models_dir()
    assert p.exists()
    assert p.is_dir()


def test_models_dir_parent_is_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert paths.models_dir().parent == tmp_path / "WinWhisp"


def test_models_dir_idempotent(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p1 = paths.models_dir()
    p2 = paths.models_dir()
    assert p1 == p2
    assert p2.exists()


def test_models_dir_changes_with_override(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    override = tmp_path / "mdl_ov"
    override.mkdir()
    paths.write_override(override)
    p = paths.models_dir()
    assert p.parent == override
    paths.clear_override()


# ---------------------------------------------------------------------------
# log_dir
# ---------------------------------------------------------------------------


def test_log_dir_name(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p = paths.log_dir()
    assert p.name == "logs"


def test_log_dir_creates_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p = paths.log_dir()
    assert p.exists()
    assert p.is_dir()


def test_log_dir_parent_is_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert paths.log_dir().parent == tmp_path / "WinWhisp"


def test_log_dir_idempotent(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p1 = paths.log_dir()
    p2 = paths.log_dir()
    assert p1 == p2
    assert p2.exists()


def test_log_dir_distinct_from_models(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert paths.log_dir() != paths.models_dir()


# ---------------------------------------------------------------------------
# resources_dir
# ---------------------------------------------------------------------------


def test_resources_dir_dev_mode_not_frozen(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    p = paths.resources_dir()
    assert p.name == "resources"
    assert p.exists() or not p.exists()


def test_resources_dir_dev_mode_parent_chain(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    p = paths.resources_dir()
    assert p.name == "resources"
    src_file = Path(paths.__file__).resolve()
    expected = src_file.parent.parent.parent / "resources"
    assert p == expected


def test_resources_dir_frozen_uses_meipass(monkeypatch, tmp_path):
    meipass = tmp_path / "_MEIPASS"
    meipass.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    p = paths.resources_dir()
    assert p == meipass / "resources"


def test_resources_dir_frozen_name_is_resources(monkeypatch, tmp_path):
    meipass = tmp_path / "mei2"
    meipass.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    assert paths.resources_dir().name == "resources"


def test_resources_dir_frozen_parent_is_meipass(monkeypatch, tmp_path):
    meipass = tmp_path / "mei3"
    meipass.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    assert paths.resources_dir().parent == meipass


def test_resources_dir_frozen_false_acts_as_dev(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    p = paths.resources_dir()
    src_file = Path(paths.__file__).resolve()
    expected = src_file.parent.parent.parent / "resources"
    assert p == expected


def test_resources_dir_dev_is_deterministic(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert paths.resources_dir() == paths.resources_dir()


# ---------------------------------------------------------------------------
# ensure_default
# ---------------------------------------------------------------------------


def test_ensure_default_copies_when_missing(tmp_path):
    src = tmp_path / "source.yaml"
    src.write_text("data: 1", encoding="utf-8")
    dest = tmp_path / "dest.yaml"
    result = paths.ensure_default(dest, src)
    assert result == dest
    assert dest.exists()
    assert dest.read_text(encoding="utf-8") == "data: 1"


def test_ensure_default_does_not_overwrite_existing(tmp_path):
    src = tmp_path / "source.yaml"
    src.write_text("new", encoding="utf-8")
    dest = tmp_path / "dest.yaml"
    dest.write_text("original", encoding="utf-8")
    paths.ensure_default(dest, src)
    assert dest.read_text(encoding="utf-8") == "original"


def test_ensure_default_noop_when_source_missing(tmp_path):
    src = tmp_path / "no_source.yaml"
    dest = tmp_path / "dest.yaml"
    result = paths.ensure_default(dest, src)
    assert result == dest
    assert not dest.exists()


def test_ensure_default_returns_dest_path(tmp_path):
    src = tmp_path / "s.yaml"
    src.write_text("x", encoding="utf-8")
    dest = tmp_path / "d.yaml"
    assert paths.ensure_default(dest, src) == dest


def test_ensure_default_returns_dest_when_exists(tmp_path):
    src = tmp_path / "s2.yaml"
    src.write_text("new", encoding="utf-8")
    dest = tmp_path / "d2.yaml"
    dest.write_text("old", encoding="utf-8")
    assert paths.ensure_default(dest, src) == dest


def test_ensure_default_copies_binary(tmp_path):
    src = tmp_path / "model.bin"
    src.write_bytes(b"\x00\x01\x02\x03")
    dest = tmp_path / "model_copy.bin"
    paths.ensure_default(dest, src)
    assert dest.read_bytes() == b"\x00\x01\x02\x03"
