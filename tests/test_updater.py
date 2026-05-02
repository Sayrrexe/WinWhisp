from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from transcrb.config import UpdaterCfg
from transcrb.updater import (
    UpdateChecker,
    _parse_version,
    fetch_latest_release,
    is_newer,
)


class TestParseVersion:
    def test_basic_three_parts(self):
        assert _parse_version("1.2.3") == (1, 2, 3)

    def test_strip_v_prefix(self):
        assert _parse_version("v1.2.3") == (1, 2, 3)

    def test_strip_pre_release_suffix(self):
        assert _parse_version("1.2.3-rc1") == (1, 2, 3)

    def test_strip_build_metadata(self):
        assert _parse_version("1.2.3+build.4") == (1, 2, 3)

    def test_pads_short_version(self):
        assert _parse_version("1.2") == (1, 2, 0)

    def test_pads_single(self):
        assert _parse_version("1") == (1, 0, 0)

    def test_dev_suffix_truncated(self):
        assert _parse_version("0.0.0-dev") == (0, 0, 0)

    def test_non_numeric_part_zero(self):
        assert _parse_version("1.x.3") == (1, 0, 3)


class TestIsNewer:
    def test_higher_patch(self):
        assert is_newer("1.2.4", "1.2.3") is True

    def test_higher_minor(self):
        assert is_newer("1.3.0", "1.2.5") is True

    def test_higher_major(self):
        assert is_newer("2.0.0", "1.99.99") is True

    def test_equal_returns_false(self):
        assert is_newer("1.2.3", "1.2.3") is False

    def test_lower_returns_false(self):
        assert is_newer("1.2.2", "1.2.3") is False

    def test_v_prefix_handled(self):
        assert is_newer("v1.2.4", "1.2.3") is True

    def test_dev_current_lower_than_release(self):
        assert is_newer("0.1.0", "0.0.0-dev") is True


class TestFetchLatestRelease:
    def test_success_returns_dict(self):
        payload = json.dumps({"tag_name": "v0.2.0", "html_url": "https://x"}).encode()
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=None)
        mock_resp.read.return_value = payload
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = fetch_latest_release("owner/repo")
        assert result == {"tag_name": "v0.2.0", "html_url": "https://x"}

    def test_404_returns_none(self):
        err = urllib.error.HTTPError("u", 404, "Not Found", {}, None)
        with patch("urllib.request.urlopen", side_effect=err):
            assert fetch_latest_release("owner/repo") is None

    def test_500_returns_none(self):
        err = urllib.error.HTTPError("u", 500, "Server Error", {}, None)
        with patch("urllib.request.urlopen", side_effect=err):
            assert fetch_latest_release("owner/repo") is None

    def test_network_error_returns_none(self):
        with patch("urllib.request.urlopen", side_effect=OSError("no net")):
            assert fetch_latest_release("owner/repo") is None

    def test_invalid_json_returns_none(self):
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=None)
        mock_resp.read.return_value = b"not json"
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert fetch_latest_release("owner/repo") is None


class TestUpdateChecker:
    @pytest.fixture()
    def cfg(self):
        return UpdaterCfg(enabled=True, check_interval_hours=6, repo="o/r", initial_delay_s=30)

    def test_disabled_does_not_start_timer(self, qapp, cfg):
        cfg = cfg.model_copy(update={"enabled": False})
        ch = UpdateChecker(cfg)
        ch.start()
        assert not ch._timer.isActive()

    def test_zero_interval_does_not_start_timer(self, qapp, cfg):
        cfg = cfg.model_copy(update={"check_interval_hours": 0})
        ch = UpdateChecker(cfg)
        ch.start()
        assert not ch._timer.isActive()

    def test_enabled_starts_timer(self, qapp, cfg):
        ch = UpdateChecker(cfg)
        ch.start()
        try:
            assert ch._timer.isActive()
        finally:
            ch.stop()

    def test_do_check_emits_signal_when_newer(self, qapp, cfg, tmp_path):
        ch = UpdateChecker(cfg)
        emitted = []
        ch.update_available.connect(lambda v, r: emitted.append((v, r)))
        release = {"tag_name": "v999.0.0", "html_url": "https://x"}
        with patch(
            "transcrb.updater.fetch_latest_release",
            return_value=release,
        ), patch("transcrb.updater._load_state", return_value={}), \
             patch("transcrb.updater._save_state"):
            ch._do_check(False)
        assert emitted == [("v999.0.0", release)]

    def test_do_check_skips_when_already_notified(self, qapp, cfg):
        ch = UpdateChecker(cfg)
        emitted = []
        ch.update_available.connect(lambda v, r: emitted.append((v, r)))
        with patch(
            "transcrb.updater.fetch_latest_release",
            return_value={"tag_name": "v999.0.0", "html_url": "https://x"},
        ), patch("transcrb.updater._load_state", return_value={"last_notified": "v999.0.0"}), \
             patch("transcrb.updater._save_state"):
            ch._do_check(False)
        assert emitted == []

    def test_do_check_force_notify_emits_even_if_already_notified(self, qapp, cfg):
        ch = UpdateChecker(cfg)
        emitted = []
        ch.update_available.connect(lambda v, r: emitted.append((v, r)))
        with patch(
            "transcrb.updater.fetch_latest_release",
            return_value={"tag_name": "v999.0.0", "html_url": "https://x"},
        ), patch("transcrb.updater._load_state", return_value={"last_notified": "v999.0.0"}), \
             patch("transcrb.updater._save_state"):
            ch._do_check(True)
        assert len(emitted) == 1

    def test_do_check_skips_when_not_newer(self, qapp, cfg):
        ch = UpdateChecker(cfg)
        emitted = []
        no_update = []
        ch.update_available.connect(lambda v, r: emitted.append((v, r)))
        ch.no_update.connect(lambda t: no_update.append(t))
        with patch(
            "transcrb.updater.fetch_latest_release",
            return_value={"tag_name": "v0.0.0", "html_url": "https://x"},
        ):
            ch._do_check(False)
        assert emitted == []
        assert no_update == ["v0.0.0"]

    def test_do_check_handles_no_release(self, qapp, cfg):
        ch = UpdateChecker(cfg)
        emitted = []
        failed = []
        ch.update_available.connect(lambda v, r: emitted.append((v, r)))
        ch.check_failed.connect(lambda m: failed.append(m))
        with patch("transcrb.updater.fetch_latest_release", return_value=None):
            ch._do_check(False)
        assert emitted == []
        assert len(failed) == 1

    def test_do_check_handles_empty_tag(self, qapp, cfg):
        ch = UpdateChecker(cfg)
        emitted = []
        failed = []
        ch.update_available.connect(lambda v, r: emitted.append((v, r)))
        ch.check_failed.connect(lambda m: failed.append(m))
        with patch(
            "transcrb.updater.fetch_latest_release",
            return_value={"tag_name": "", "html_url": "x"},
        ):
            ch._do_check(False)
        assert emitted == []
        assert len(failed) == 1

    def test_busy_prevents_concurrent_check(self, qapp, cfg):
        ch = UpdateChecker(cfg)
        ch._busy = True
        with patch("threading.Thread") as mock_thread:
            ch._spawn_check()
        mock_thread.assert_not_called()

    def test_latest_release_updated_on_new_release(self, qapp, cfg):
        ch = UpdateChecker(cfg)
        release = {"tag_name": "v999.0.0", "html_url": "https://x"}
        with patch(
            "transcrb.updater.fetch_latest_release",
            return_value=release,
        ), patch("transcrb.updater._load_state", return_value={}), \
             patch("transcrb.updater._save_state"):
            ch._do_check(False)
        assert ch.latest_release() == release
