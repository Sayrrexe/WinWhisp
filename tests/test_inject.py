from unittest.mock import MagicMock, call, patch

import pytest


def test_inject_copies_and_pastes():
    with patch("transcrb.text.inject.pyperclip") as pc, patch(
        "transcrb.text.inject.keyboard"
    ) as kb, patch("transcrb.text.inject.time.sleep"):
        pc.paste.return_value = "old"
        from transcrb.text.inject import inject

        ok = inject("hello", pre_delay_ms=0, post_delay_ms=0, restore=True)
        assert ok
        copy_calls = [c.args[0] for c in pc.copy.call_args_list]
        assert "hello" in copy_calls
        assert "old" in copy_calls
        kb.send.assert_called_once_with("ctrl+v")


def test_inject_no_restore():
    with patch("transcrb.text.inject.pyperclip") as pc, patch(
        "transcrb.text.inject.keyboard"
    ) as kb, patch("transcrb.text.inject.time.sleep"):
        from transcrb.text.inject import inject

        ok = inject("x", pre_delay_ms=0, post_delay_ms=0, restore=False)
        assert ok
        pc.paste.assert_not_called()
        assert pc.copy.call_count == 1


def test_inject_empty_text_noop():
    with patch("transcrb.text.inject.pyperclip") as pc, patch(
        "transcrb.text.inject.keyboard"
    ) as kb:
        from transcrb.text.inject import inject

        assert inject("") is False
        pc.copy.assert_not_called()
        kb.send.assert_not_called()


# ── _safe_get_clipboard ────────────────────────────────────────────────────────


def test_safe_get_clipboard_returns_text():
    with patch("transcrb.text.inject.pyperclip") as pc:
        pc.paste.return_value = "clipboard content"
        from transcrb.text.inject import _safe_get_clipboard

        assert _safe_get_clipboard() == "clipboard content"


def test_safe_get_clipboard_returns_empty_string():
    with patch("transcrb.text.inject.pyperclip") as pc:
        pc.paste.return_value = ""
        from transcrb.text.inject import _safe_get_clipboard

        assert _safe_get_clipboard() == ""


def test_safe_get_clipboard_exception_returns_none():
    with patch("transcrb.text.inject.pyperclip") as pc:
        pc.paste.side_effect = Exception("no clipboard")
        from transcrb.text.inject import _safe_get_clipboard

        assert _safe_get_clipboard() is None


def test_safe_get_clipboard_unicode():
    with patch("transcrb.text.inject.pyperclip") as pc:
        pc.paste.return_value = "привет мир 🎉"
        from transcrb.text.inject import _safe_get_clipboard

        assert _safe_get_clipboard() == "привет мир 🎉"


def test_safe_get_clipboard_os_error_returns_none():
    with patch("transcrb.text.inject.pyperclip") as pc:
        pc.paste.side_effect = OSError("access denied")
        from transcrb.text.inject import _safe_get_clipboard

        assert _safe_get_clipboard() is None


# ── _safe_set_clipboard ────────────────────────────────────────────────────────


def test_safe_set_clipboard_returns_true_on_success():
    with patch("transcrb.text.inject.pyperclip") as pc:
        from transcrb.text.inject import _safe_set_clipboard

        assert _safe_set_clipboard("hello") is True
        pc.copy.assert_called_once_with("hello")


def test_safe_set_clipboard_exception_returns_false():
    with patch("transcrb.text.inject.pyperclip") as pc:
        pc.copy.side_effect = Exception("clipboard locked")
        from transcrb.text.inject import _safe_set_clipboard

        assert _safe_set_clipboard("hello") is False


def test_safe_set_clipboard_empty_string():
    with patch("transcrb.text.inject.pyperclip") as pc:
        from transcrb.text.inject import _safe_set_clipboard

        assert _safe_set_clipboard("") is True
        pc.copy.assert_called_once_with("")


def test_safe_set_clipboard_unicode():
    with patch("transcrb.text.inject.pyperclip") as pc:
        from transcrb.text.inject import _safe_set_clipboard

        assert _safe_set_clipboard("Привет 🔥") is True
        pc.copy.assert_called_once_with("Привет 🔥")


def test_safe_set_clipboard_os_error_returns_false():
    with patch("transcrb.text.inject.pyperclip") as pc:
        pc.copy.side_effect = OSError("write failed")
        from transcrb.text.inject import _safe_set_clipboard

        assert _safe_set_clipboard("text") is False


# ── inject – stash / restore ──────────────────────────────────────────────────


def test_inject_restores_old_clipboard_after_paste():
    with patch("transcrb.text.inject.pyperclip") as pc, patch(
        "transcrb.text.inject.keyboard"
    ), patch("transcrb.text.inject.time.sleep"):
        pc.paste.return_value = "previous"
        from transcrb.text.inject import inject

        inject("new text", pre_delay_ms=0, post_delay_ms=0, restore=True)
        copy_calls = [c.args[0] for c in pc.copy.call_args_list]
        assert copy_calls[-1] == "previous"


def test_inject_restore_skipped_when_old_is_none():
    with patch("transcrb.text.inject.pyperclip") as pc, patch(
        "transcrb.text.inject.keyboard"
    ), patch("transcrb.text.inject.time.sleep"):
        pc.paste.side_effect = Exception("no clipboard")
        from transcrb.text.inject import inject

        ok = inject("hi", pre_delay_ms=0, post_delay_ms=0, restore=True)
        assert ok
        assert pc.copy.call_count == 1
        pc.copy.assert_called_once_with("hi")


def test_inject_set_clipboard_fail_returns_false():
    with patch("transcrb.text.inject.pyperclip") as pc, patch(
        "transcrb.text.inject.keyboard"
    ) as kb, patch("transcrb.text.inject.time.sleep"):
        pc.paste.return_value = "old"
        pc.copy.side_effect = Exception("locked")
        from transcrb.text.inject import inject

        result = inject("text", pre_delay_ms=0, post_delay_ms=0, restore=True)
        assert result is False
        kb.send.assert_not_called()


def test_inject_restore_happens_even_if_keyboard_raises():
    with patch("transcrb.text.inject.pyperclip") as pc, patch(
        "transcrb.text.inject.keyboard"
    ) as kb, patch("transcrb.text.inject.time.sleep"):
        pc.paste.return_value = "saved"
        kb.send.side_effect = Exception("keyboard error")
        from transcrb.text.inject import inject

        with pytest.raises(Exception, match="keyboard error"):
            inject("hello", pre_delay_ms=0, post_delay_ms=0, restore=True)

        copy_calls = [c.args[0] for c in pc.copy.call_args_list]
        assert "saved" in copy_calls


# ── inject – paste_combo ──────────────────────────────────────────────────────


def test_inject_custom_paste_combo():
    with patch("transcrb.text.inject.pyperclip") as pc, patch(
        "transcrb.text.inject.keyboard"
    ) as kb, patch("transcrb.text.inject.time.sleep"):
        pc.paste.return_value = ""
        from transcrb.text.inject import inject

        inject("x", paste_combo="ctrl+shift+v", pre_delay_ms=0, post_delay_ms=0)
        kb.send.assert_called_once_with("ctrl+shift+v")


def test_inject_default_combo_is_ctrl_v():
    with patch("transcrb.text.inject.pyperclip") as pc, patch(
        "transcrb.text.inject.keyboard"
    ) as kb, patch("transcrb.text.inject.time.sleep"):
        pc.paste.return_value = ""
        from transcrb.text.inject import inject

        inject("x", pre_delay_ms=0, post_delay_ms=0)
        kb.send.assert_called_once_with("ctrl+v")


# ── inject – sleep / timing ───────────────────────────────────────────────────


def test_inject_sleeps_pre_and_post():
    with patch("transcrb.text.inject.pyperclip") as pc, patch(
        "transcrb.text.inject.keyboard"
    ), patch("transcrb.text.inject.time.sleep") as slp:
        pc.paste.return_value = ""
        from transcrb.text.inject import inject

        inject("text", pre_delay_ms=20, post_delay_ms=250, restore=False)
        assert slp.call_count == 2
        slp.assert_any_call(0.02)
        slp.assert_any_call(0.25)


def test_inject_zero_delays_no_sleep_duration():
    with patch("transcrb.text.inject.pyperclip") as pc, patch(
        "transcrb.text.inject.keyboard"
    ), patch("transcrb.text.inject.time.sleep") as slp:
        pc.paste.return_value = ""
        from transcrb.text.inject import inject

        inject("text", pre_delay_ms=0, post_delay_ms=0, restore=False)
        slp.assert_any_call(0.0)


def test_inject_pre_delay_before_keyboard_send():
    events = []
    with patch("transcrb.text.inject.pyperclip") as pc, patch(
        "transcrb.text.inject.keyboard"
    ) as kb, patch(
        "transcrb.text.inject.time.sleep", side_effect=lambda s: events.append(("sleep", s))
    ):
        kb.send.side_effect = lambda c: events.append(("send", c))
        pc.paste.return_value = ""
        from transcrb.text.inject import inject

        inject("text", pre_delay_ms=10, post_delay_ms=5, restore=False)

    sleep_indices = [i for i, e in enumerate(events) if e[0] == "sleep"]
    send_index = next(i for i, e in enumerate(events) if e[0] == "send")
    assert sleep_indices[0] < send_index < sleep_indices[1]


# ── inject – Unicode ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "Привет мир",
        "日本語テスト",
        "emoji 🎉🔥💯",
        "mixed: commit коммит 提交",
    ],
)
def test_inject_unicode_text(text):
    with patch("transcrb.text.inject.pyperclip") as pc, patch(
        "transcrb.text.inject.keyboard"
    ) as kb, patch("transcrb.text.inject.time.sleep"):
        pc.paste.return_value = ""
        from transcrb.text.inject import inject

        ok = inject(text, pre_delay_ms=0, post_delay_ms=0, restore=False)
        assert ok
        pc.copy.assert_called_once_with(text)
        kb.send.assert_called_once_with("ctrl+v")


# ── inject – whitespace-only text ─────────────────────────────────────────────


def test_inject_whitespace_only_is_not_noop():
    with patch("transcrb.text.inject.pyperclip") as pc, patch(
        "transcrb.text.inject.keyboard"
    ) as kb, patch("transcrb.text.inject.time.sleep"):
        pc.paste.return_value = ""
        from transcrb.text.inject import inject

        ok = inject("   ", pre_delay_ms=0, post_delay_ms=0, restore=False)
        assert ok is True
        kb.send.assert_called_once()


# ── inject – restore=True with empty old clipboard ────────────────────────────


def test_inject_restores_empty_string_old_clipboard():
    with patch("transcrb.text.inject.pyperclip") as pc, patch(
        "transcrb.text.inject.keyboard"
    ), patch("transcrb.text.inject.time.sleep"):
        pc.paste.return_value = ""
        from transcrb.text.inject import inject

        inject("hello", pre_delay_ms=0, post_delay_ms=0, restore=True)
        copy_calls = [c.args[0] for c in pc.copy.call_args_list]
        assert copy_calls == ["hello", ""]


# ── inject – return value semantics ───────────────────────────────────────────


def test_inject_returns_true_on_success():
    with patch("transcrb.text.inject.pyperclip") as pc, patch(
        "transcrb.text.inject.keyboard"
    ), patch("transcrb.text.inject.time.sleep"):
        pc.paste.return_value = ""
        from transcrb.text.inject import inject

        assert inject("ok", pre_delay_ms=0, post_delay_ms=0) is True


def test_inject_returns_false_for_empty():
    with patch("transcrb.text.inject.pyperclip"), patch("transcrb.text.inject.keyboard"):
        from transcrb.text.inject import inject

        assert inject("") is False
        assert inject(None) is False
