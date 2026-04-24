from transcrb.config import Config, load_config, save_config


def test_defaults():
    c = Config()
    assert c.hotkey.combo == "ctrl+shift+space"
    assert c.asr.model == "large-v3"
    assert c.asr.compute_type == "float16"
    assert c.injection.method == "paste"
    assert c.overlay.bars == 10


def test_round_trip(tmp_path):
    p = tmp_path / "cfg.yaml"
    c = Config()
    c.hotkey.combo = "ctrl+alt+x"
    c.audio.max_duration_s = 77
    save_config(c, p)
    loaded = load_config(p)
    assert loaded.hotkey.combo == "ctrl+alt+x"
    assert loaded.audio.max_duration_s == 77


def test_missing_file_creates_default(tmp_path):
    p = tmp_path / "nope.yaml"
    c = load_config(p)
    assert p.exists()
    assert c.hotkey.combo == "ctrl+shift+space"
