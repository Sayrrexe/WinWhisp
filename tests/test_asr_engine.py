from __future__ import annotations

import gc
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest

from transcrb.config import AsrCfg


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_cfg(**overrides) -> AsrCfg:
    return AsrCfg(**overrides)


def _transcribe_result(*texts: str):
    segs = [SimpleNamespace(text=t) for t in texts]
    info = SimpleNamespace(language="ru", language_probability=0.99)
    return iter(segs), info


def _mock_model(*texts: str) -> MagicMock:
    m = MagicMock()
    m.transcribe.return_value = _transcribe_result(*texts)
    return m


# ---------------------------------------------------------------------------
# ensure_model
# ---------------------------------------------------------------------------

class TestEnsureModel:
    def test_returns_path_when_model_bin_exists(self, tmp_path):
        model_dir = tmp_path / "large-v3"
        model_dir.mkdir()
        (model_dir / "model.bin").write_bytes(b"")
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path):
            from transcrb.asr.engine import ensure_model
            result = ensure_model("large-v3")
        assert result == model_dir

    def test_skips_download_when_model_bin_exists(self, tmp_path):
        model_dir = tmp_path / "base"
        model_dir.mkdir()
        (model_dir / "model.bin").write_bytes(b"")
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download") as dl:
            from transcrb.asr.engine import ensure_model
            ensure_model("base")
        dl.assert_not_called()

    def test_triggers_download_when_no_model_bin(self, tmp_path):
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download") as dl:
            from transcrb.asr.engine import ensure_model
            ensure_model("tiny")
        dl.assert_called_once()

    def test_download_uses_correct_repo_id(self, tmp_path):
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download") as dl:
            from transcrb.asr.engine import ensure_model
            ensure_model("medium")
        assert dl.call_args.kwargs["repo_id"] == "Systran/faster-whisper-medium"

    def test_download_local_dir_is_models_dir_slash_name(self, tmp_path):
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download") as dl:
            from transcrb.asr.engine import ensure_model
            ensure_model("small")
        assert dl.call_args.kwargs["local_dir"] == str(tmp_path / "small")

    def test_download_no_symlinks(self, tmp_path):
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download") as dl:
            from transcrb.asr.engine import ensure_model
            ensure_model("tiny")
        assert dl.call_args.kwargs["local_dir_use_symlinks"] is False

    def test_progress_cb_called_with_1_after_download(self, tmp_path):
        cb = MagicMock()
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"):
            from transcrb.asr.engine import ensure_model
            ensure_model("tiny", progress_cb=cb)
        cb.assert_called_once_with(1.0)

    def test_progress_cb_none_does_not_raise(self, tmp_path):
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"):
            from transcrb.asr.engine import ensure_model
            ensure_model("tiny", progress_cb=None)


# ---------------------------------------------------------------------------
# WhisperEngine.is_loaded / __init__
# ---------------------------------------------------------------------------

class TestIsLoaded:
    def test_false_on_init(self):
        from transcrb.asr.engine import WhisperEngine
        e = WhisperEngine(_make_cfg())
        assert e.is_loaded() is False

    def test_true_after_load(self, tmp_path):
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"), \
             patch("faster_whisper.WhisperModel", return_value=_mock_model()):
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(_make_cfg())
            e.load()
        assert e.is_loaded() is True

    def test_false_after_unload(self, tmp_path):
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"), \
             patch("faster_whisper.WhisperModel", return_value=_mock_model()):
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(_make_cfg())
            e.load()
            e.unload()
        assert e.is_loaded() is False

    def test_true_after_reload(self, tmp_path):
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"), \
             patch("faster_whisper.WhisperModel", return_value=_mock_model()):
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(_make_cfg())
            e.load()
            e.unload()
            e.load()
        assert e.is_loaded() is True

    def test_cfg_stored_on_engine(self):
        from transcrb.asr.engine import WhisperEngine
        cfg = _make_cfg(model="tiny", language="en")
        e = WhisperEngine(cfg)
        assert e.cfg is cfg


# ---------------------------------------------------------------------------
# WhisperEngine.unload
# ---------------------------------------------------------------------------

class TestUnload:
    def test_noop_when_not_loaded(self):
        from transcrb.asr.engine import WhisperEngine
        e = WhisperEngine(_make_cfg())
        e.unload()
        assert e._model is None

    def test_sets_model_to_none(self, tmp_path):
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"), \
             patch("faster_whisper.WhisperModel", return_value=_mock_model()):
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(_make_cfg())
            e.load()
            e.unload()
        assert e._model is None

    def test_gc_collect_called_on_unload(self, tmp_path):
        import gc as _gc
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"), \
             patch("faster_whisper.WhisperModel", return_value=_mock_model()), \
             patch.object(_gc, "collect") as mock_collect:
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(_make_cfg())
            e.load()
            e.unload()
        mock_collect.assert_called_once()

    def test_gc_not_called_when_already_unloaded(self):
        import gc as _gc
        with patch.object(_gc, "collect") as mock_collect:
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(_make_cfg())
            e.unload()
        mock_collect.assert_not_called()

    def test_idempotent_double_unload(self, tmp_path):
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"), \
             patch("faster_whisper.WhisperModel", return_value=_mock_model()):
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(_make_cfg())
            e.load()
            e.unload()
            e.unload()
        assert e._model is None

    def test_is_loaded_false_after_unload(self, tmp_path):
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"), \
             patch("faster_whisper.WhisperModel", return_value=_mock_model()):
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(_make_cfg())
            e.load()
            e.unload()
        assert not e.is_loaded()


# ---------------------------------------------------------------------------
# WhisperEngine.load
# ---------------------------------------------------------------------------

class TestLoad:
    def _engine_with_mocks(self, tmp_path, *, model_instance=None, side_effect=None):
        if model_instance is None:
            model_instance = _mock_model()
        factory = MagicMock(side_effect=side_effect, return_value=model_instance)
        return factory

    def test_happy_path_passes_cfg_params(self, tmp_path):
        cfg = _make_cfg(device="cuda", device_index=1, compute_type="float16")
        factory = MagicMock(return_value=_mock_model())
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"), \
             patch("faster_whisper.WhisperModel", factory):
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(cfg)
            e.load()
        factory.assert_called_once_with(
            str(tmp_path / cfg.model),
            device="cuda",
            device_index=1,
            compute_type="float16",
        )

    def test_fallback_on_runtime_error(self, tmp_path):
        cfg = _make_cfg(device="cuda", compute_type="float16")
        fallback_model = _mock_model()
        call_count = 0

        def factory_se(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("CUDA out of memory")
            return fallback_model

        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"), \
             patch("faster_whisper.WhisperModel", side_effect=factory_se):
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(cfg)
            e.load()

        assert e._model is fallback_model

    def test_fallback_uses_cpu_int8(self, tmp_path):
        calls = []

        def factory_se(*args, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise OSError("libcuda not found")
            return _mock_model()

        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"), \
             patch("faster_whisper.WhisperModel", side_effect=factory_se):
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(_make_cfg(device="cuda"))
            e.load()

        assert calls[1]["device"] == "cpu"
        assert calls[1]["compute_type"] == "int8"

    def test_fallback_on_os_error(self, tmp_path):
        def factory_se(*args, **kwargs):
            if kwargs.get("device") == "cuda":
                raise OSError("cublas64_12.dll not found")
            return _mock_model()

        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"), \
             patch("faster_whisper.WhisperModel", side_effect=factory_se):
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(_make_cfg(device="cuda"))
            e.load()

        assert e.is_loaded()

    def test_fallback_on_value_error(self, tmp_path):
        def factory_se(*args, **kwargs):
            if kwargs.get("device") == "cuda":
                raise ValueError("Unexpected compute type")
            return _mock_model()

        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"), \
             patch("faster_whisper.WhisperModel", side_effect=factory_se):
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(_make_cfg(device="cuda"))
            e.load()

        assert e.is_loaded()

    def test_calls_ensure_model(self, tmp_path):
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download") as dl, \
             patch("faster_whisper.WhisperModel", return_value=_mock_model()):
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(_make_cfg(model="tiny"))
            e.load()
        # snapshot_download called because model.bin not present
        dl.assert_called_once()

    def test_second_load_replaces_model(self, tmp_path):
        model1 = _mock_model()
        model2 = _mock_model()
        factory = MagicMock(side_effect=[model1, model2])
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"), \
             patch("faster_whisper.WhisperModel", factory):
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(_make_cfg())
            e.load()
            e.load()
        assert e._model is model2

    def test_fallback_no_device_index_kwarg(self, tmp_path):
        calls = []

        def factory_se(*args, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise RuntimeError("CUDA error")
            return _mock_model()

        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"), \
             patch("faster_whisper.WhisperModel", side_effect=factory_se):
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(_make_cfg())
            e.load()

        assert "device_index" not in calls[1]


# ---------------------------------------------------------------------------
# WhisperEngine.warmup
# ---------------------------------------------------------------------------

class TestWarmup:
    def test_noop_when_not_loaded(self):
        from transcrb.asr.engine import WhisperEngine
        e = WhisperEngine(_make_cfg())
        e.warmup()  # must not raise

    def test_calls_transcribe_on_model(self, tmp_path):
        m = _mock_model()
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"), \
             patch("faster_whisper.WhisperModel", return_value=m):
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(_make_cfg(language="ru"))
            e.load()
            e.warmup()
        m.transcribe.assert_called_once()

    def test_warmup_uses_16000_zeros(self, tmp_path):
        m = _mock_model()
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"), \
             patch("faster_whisper.WhisperModel", return_value=m):
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(_make_cfg())
            e.load()
            e.warmup()
        audio_arg = m.transcribe.call_args[0][0]
        assert isinstance(audio_arg, np.ndarray)
        assert audio_arg.dtype == np.float32
        assert audio_arg.shape == (16000,)
        assert np.all(audio_arg == 0)

    def test_warmup_passes_beam_size_1(self, tmp_path):
        m = _mock_model()
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"), \
             patch("faster_whisper.WhisperModel", return_value=m):
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(_make_cfg())
            e.load()
            e.warmup()
        assert m.transcribe.call_args.kwargs["beam_size"] == 1

    def test_warmup_passes_cfg_language(self, tmp_path):
        m = _mock_model()
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"), \
             patch("faster_whisper.WhisperModel", return_value=m):
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(_make_cfg(language="en"))
            e.load()
            e.warmup()
        assert m.transcribe.call_args.kwargs["language"] == "en"

    def test_warmup_drains_segment_generator(self, tmp_path):
        drained = []

        def fake_transcribe(*a, **kw):
            def gen():
                for t in ["a", "b", "c"]:
                    drained.append(t)
                    yield SimpleNamespace(text=t)
            return gen(), SimpleNamespace(language="ru", language_probability=0.9)

        m = MagicMock()
        m.transcribe.side_effect = fake_transcribe
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"), \
             patch("faster_whisper.WhisperModel", return_value=m):
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(_make_cfg())
            e.load()
            e.warmup()
        assert drained == ["a", "b", "c"]

    @pytest.mark.parametrize("exc", [RuntimeError("fail"), OSError("fail"), ValueError("v")])
    def test_warmup_swallows_exceptions(self, tmp_path, exc):
        m = MagicMock()
        m.transcribe.side_effect = exc
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"), \
             patch("faster_whisper.WhisperModel", return_value=m):
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(_make_cfg())
            e.load()
            e.warmup()  # must not propagate


# ---------------------------------------------------------------------------
# WhisperEngine.transcribe
# ---------------------------------------------------------------------------

class TestTranscribe:
    def _loaded_engine(self, tmp_path, model, **cfg_overrides) -> object:
        with patch("transcrb.asr.engine.models_dir", return_value=tmp_path), \
             patch("huggingface_hub.snapshot_download"), \
             patch("faster_whisper.WhisperModel", return_value=model):
            from transcrb.asr.engine import WhisperEngine
            e = WhisperEngine(_make_cfg(**cfg_overrides))
            e.load()
        return e

    def test_raises_when_not_loaded(self):
        from transcrb.asr.engine import WhisperEngine
        e = WhisperEngine(_make_cfg())
        with pytest.raises(RuntimeError, match="engine not loaded"):
            e.transcribe(np.zeros(16000, dtype=np.float32))

    def test_returns_joined_segment_text(self, tmp_path):
        m = MagicMock()
        m.transcribe.return_value = _transcribe_result("hello ", "world")
        e = self._loaded_engine(tmp_path, m)
        result = e.transcribe(np.zeros(16000, dtype=np.float32))
        assert result == "hello world"

    def test_result_is_stripped(self, tmp_path):
        m = MagicMock()
        m.transcribe.return_value = _transcribe_result("  some text  ")
        e = self._loaded_engine(tmp_path, m)
        result = e.transcribe(np.zeros(16000, dtype=np.float32))
        assert result == "some text"

    def test_int16_audio_converted_to_float32(self, tmp_path):
        m = MagicMock()
        m.transcribe.return_value = _transcribe_result("x")
        e = self._loaded_engine(tmp_path, m)
        audio_int16 = np.zeros(16000, dtype=np.int16)
        e.transcribe(audio_int16)
        passed_audio = m.transcribe.call_args[0][0]
        assert passed_audio.dtype == np.float32

    def test_float32_not_reconverted(self, tmp_path):
        m = MagicMock()
        m.transcribe.return_value = _transcribe_result("x")
        e = self._loaded_engine(tmp_path, m)
        audio = np.zeros(16000, dtype=np.float32)
        original_id = id(audio)
        e.transcribe(audio)
        passed_audio = m.transcribe.call_args[0][0]
        assert passed_audio.dtype == np.float32

    def test_initial_prompt_included_when_provided(self, tmp_path):
        m = MagicMock()
        m.transcribe.return_value = _transcribe_result("hi")
        e = self._loaded_engine(tmp_path, m)
        e.transcribe(np.zeros(32000, dtype=np.float32), initial_prompt="ctx")
        assert "initial_prompt" in m.transcribe.call_args.kwargs
        assert m.transcribe.call_args.kwargs["initial_prompt"] == "ctx"

    def test_initial_prompt_dropped_for_short_audio(self, tmp_path):
        m = MagicMock()
        m.transcribe.return_value = _transcribe_result("hi")
        e = self._loaded_engine(tmp_path, m)
        e.transcribe(np.zeros(16000, dtype=np.float32), initial_prompt="ctx")
        assert "initial_prompt" not in m.transcribe.call_args.kwargs

    def test_condition_on_previous_text_false_for_short_audio(self, tmp_path):
        m = MagicMock()
        m.transcribe.return_value = _transcribe_result("hi")
        e = self._loaded_engine(tmp_path, m, cfg_overrides={"condition_on_previous_text": True})
        e.transcribe(np.zeros(16000, dtype=np.float32))
        assert m.transcribe.call_args.kwargs["condition_on_previous_text"] is False

    def test_initial_prompt_absent_when_empty(self, tmp_path):
        m = MagicMock()
        m.transcribe.return_value = _transcribe_result("hi")
        e = self._loaded_engine(tmp_path, m)
        e.transcribe(np.zeros(16000, dtype=np.float32), initial_prompt="")
        assert "initial_prompt" not in m.transcribe.call_args.kwargs

    def test_hotwords_included_when_provided(self, tmp_path):
        m = MagicMock()
        m.transcribe.return_value = _transcribe_result("hi")
        e = self._loaded_engine(tmp_path, m)
        e.transcribe(np.zeros(16000, dtype=np.float32), hotwords="Kubernetes")
        assert m.transcribe.call_args.kwargs["hotwords"] == "Kubernetes"

    def test_hotwords_absent_when_empty(self, tmp_path):
        m = MagicMock()
        m.transcribe.return_value = _transcribe_result("hi")
        e = self._loaded_engine(tmp_path, m)
        e.transcribe(np.zeros(16000, dtype=np.float32), hotwords="")
        assert "hotwords" not in m.transcribe.call_args.kwargs

    def test_vad_parameters_present_when_vad_filter_true(self, tmp_path):
        m = MagicMock()
        m.transcribe.return_value = _transcribe_result("hi")
        e = self._loaded_engine(tmp_path, m, vad_filter=True, vad_min_silence_ms=300)
        e.transcribe(np.zeros(16000, dtype=np.float32))
        kwargs = m.transcribe.call_args.kwargs
        assert kwargs["vad_filter"] is True
        assert kwargs["vad_parameters"] == {"min_silence_duration_ms": 300}

    def test_vad_parameters_none_when_vad_filter_false(self, tmp_path):
        m = MagicMock()
        m.transcribe.return_value = _transcribe_result("hi")
        e = self._loaded_engine(tmp_path, m, vad_filter=False)
        e.transcribe(np.zeros(16000, dtype=np.float32))
        kwargs = m.transcribe.call_args.kwargs
        assert kwargs["vad_filter"] is False
        assert kwargs["vad_parameters"] is None

    def test_cfg_beam_size_passed(self, tmp_path):
        m = MagicMock()
        m.transcribe.return_value = _transcribe_result("hi")
        e = self._loaded_engine(tmp_path, m, beam_size=3)
        e.transcribe(np.zeros(16000, dtype=np.float32))
        assert m.transcribe.call_args.kwargs["beam_size"] == 3

    def test_cfg_language_passed(self, tmp_path):
        m = MagicMock()
        m.transcribe.return_value = _transcribe_result("hi")
        e = self._loaded_engine(tmp_path, m, language="en")
        e.transcribe(np.zeros(16000, dtype=np.float32))
        assert m.transcribe.call_args.kwargs["language"] == "en"

    def test_condition_on_previous_text_passed(self, tmp_path):
        m = MagicMock()
        m.transcribe.return_value = _transcribe_result("hi")
        e = self._loaded_engine(tmp_path, m, condition_on_previous_text=False)
        e.transcribe(np.zeros(16000, dtype=np.float32))
        assert m.transcribe.call_args.kwargs["condition_on_previous_text"] is False

    def test_empty_segments_returns_empty_string(self, tmp_path):
        m = MagicMock()
        m.transcribe.return_value = (iter([]), SimpleNamespace(language="ru", language_probability=0.5))
        e = self._loaded_engine(tmp_path, m)
        result = e.transcribe(np.zeros(16000, dtype=np.float32))
        assert result == ""

    def test_temperature_passed(self, tmp_path):
        m = MagicMock()
        m.transcribe.return_value = _transcribe_result("hi")
        e = self._loaded_engine(tmp_path, m, temperature=0.5)
        e.transcribe(np.zeros(16000, dtype=np.float32))
        assert m.transcribe.call_args.kwargs["temperature"] == 0.5

    def test_multiple_segments_joined_without_separator(self, tmp_path):
        m = MagicMock()
        m.transcribe.return_value = _transcribe_result("foo", "bar", "baz")
        e = self._loaded_engine(tmp_path, m)
        result = e.transcribe(np.zeros(16000, dtype=np.float32))
        assert result == "foobarbaz"

    def test_short_audio_uses_scalar_temperature(self, tmp_path):
        m = MagicMock()
        m.transcribe.return_value = _transcribe_result("hi")
        e = self._loaded_engine(tmp_path, m, temperature=0.3, short_audio_s=1.5)
        e.transcribe(np.zeros(16000, dtype=np.float32))
        passed = m.transcribe.call_args.kwargs["temperature"]
        assert isinstance(passed, float)
        assert passed == pytest.approx(0.3)

    def test_long_audio_uses_temperature_fallback_tuple(self, tmp_path):
        m = MagicMock()
        m.transcribe.return_value = _transcribe_result("hi")
        e = self._loaded_engine(tmp_path, m, short_audio_s=1.0)
        e.transcribe(np.zeros(32000, dtype=np.float32))
        passed = m.transcribe.call_args.kwargs["temperature"]
        assert isinstance(passed, tuple)
        assert len(passed) > 1

    def test_short_audio_uses_higher_no_speech_threshold(self, tmp_path):
        m = MagicMock()
        m.transcribe.return_value = _transcribe_result("hi")
        e = self._loaded_engine(
            tmp_path,
            m,
            short_audio_s=1.5,
            no_speech_threshold=0.6,
            short_audio_no_speech_threshold=0.85,
        )
        e.transcribe(np.zeros(16000, dtype=np.float32))
        passed = m.transcribe.call_args.kwargs["no_speech_threshold"]
        assert passed == pytest.approx(0.85)

    def test_long_audio_keeps_base_no_speech_threshold(self, tmp_path):
        m = MagicMock()
        m.transcribe.return_value = _transcribe_result("hi")
        e = self._loaded_engine(
            tmp_path,
            m,
            short_audio_s=1.0,
            no_speech_threshold=0.45,
            short_audio_no_speech_threshold=0.85,
        )
        e.transcribe(np.zeros(32000, dtype=np.float32))
        passed = m.transcribe.call_args.kwargs["no_speech_threshold"]
        assert passed == pytest.approx(0.45)
