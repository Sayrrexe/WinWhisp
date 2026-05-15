from unittest.mock import patch

import pytest


def test_inject_copies_and_pastes():
    with patch("transcrb.text.inject.pyperclip") as pc, patch(
        "transcrb.text.inject.keyboard"
    ) as kb, patch("transcrb.text.inject.time.sleep"):
        from transcrb.text.inject import inject

        ok = inject("hello", pre_delay_ms=0, post_delay_ms=0)
        assert ok
        pc.copy.assert_called_once_with("hello")
        kb.send.assert_called_once_with("ctrl+v")


def test_inject_does_not_read_old_clipboard():
    with patch("transcrb.text.inject.pyperclip") as pc, patch(
        "transcrb.text.inject.keyboard"
    ), patch("transcrb.text.inject.time.sleep"):
        from transcrb.text.inject import inject

        inject("x", pre_delay_ms=0, post_delay_ms=0)
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


def test_inject_none_text_noop():
    from transcrb.text.inject import inject

    assert inject(None) is False


def test_inject_set_clipboard_fail_returns_false():
    with patch("transcrb.text.inject.pyperclip") as pc, patch(
        "transcrb.text.inject.keyboard"
    ) as kb, patch("transcrb.text.inject.time.sleep"):
        pc.copy.side_effect = Exception("locked")
        from transcrb.text.inject import inject

        assert inject("text", pre_delay_ms=0, post_delay_ms=0) is False
        kb.send.assert_not_called()


def test_inject_custom_paste_combo():
    with patch("transcrb.text.inject.pyperclip"), patch(
        "transcrb.text.inject.keyboard"
    ) as kb, patch("transcrb.text.inject.time.sleep"):
        from transcrb.text.inject import inject

        inject("x", paste_combo="ctrl+shift+v", pre_delay_ms=0, post_delay_ms=0)
        kb.send.assert_called_once_with("ctrl+shift+v")


def test_inject_default_combo_is_ctrl_v():
    with patch("transcrb.text.inject.pyperclip"), patch(
        "transcrb.text.inject.keyboard"
    ) as kb, patch("transcrb.text.inject.time.sleep"):
        from transcrb.text.inject import inject

        inject("x", pre_delay_ms=0, post_delay_ms=0)
        kb.send.assert_called_once_with("ctrl+v")


def test_inject_sleeps_pre_and_post():
    with patch("transcrb.text.inject.pyperclip"), patch(
        "transcrb.text.inject.keyboard"
    ), patch("transcrb.text.inject.time.sleep") as slp:
        from transcrb.text.inject import inject

        inject("text", pre_delay_ms=20, post_delay_ms=250)
        assert slp.call_count == 2
        slp.assert_any_call(0.02)
        slp.assert_any_call(0.25)


def test_inject_pre_delay_before_keyboard_send():
    events = []
    with patch("transcrb.text.inject.pyperclip"), patch(
        "transcrb.text.inject.keyboard"
    ) as kb, patch(
        "transcrb.text.inject.time.sleep",
        side_effect=lambda s: events.append(("sleep", s)),
    ):
        kb.send.side_effect = lambda c: events.append(("send", c))
        from transcrb.text.inject import inject

        inject("text", pre_delay_ms=10, post_delay_ms=5)

    sleep_indices = [i for i, e in enumerate(events) if e[0] == "sleep"]
    send_index = next(i for i, e in enumerate(events) if e[0] == "send")
    assert sleep_indices[0] < send_index < sleep_indices[1]


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


# ── type_unicode (SendInput) ──────────────────────────────────────────────────


def test_type_unicode_empty_returns_false():
    from transcrb.text.inject import type_unicode

    assert type_unicode("") is False


def test_type_unicode_calls_sendinput_with_unicode_events():
    with patch("transcrb.text.inject._SendInput") as si:
        si.side_effect = lambda n, arr, sz: n
        from transcrb.text.inject import type_unicode

        ok = type_unicode("Hi")
        assert ok
        # 2 chars × 2 events (down+up) = 4 inputs
        n_arg = si.call_args.args[0]
        assert n_arg == 4


def test_type_unicode_does_not_touch_clipboard():
    with patch("transcrb.text.inject.pyperclip") as pc, patch(
        "transcrb.text.inject._SendInput"
    ) as si:
        si.side_effect = lambda n, arr, sz: n
        from transcrb.text.inject import type_unicode

        type_unicode("hello мир")
        pc.copy.assert_not_called()
        pc.paste.assert_not_called()


def test_type_unicode_handles_surrogate_pairs():
    with patch("transcrb.text.inject._SendInput") as si:
        si.side_effect = lambda n, arr, sz: n
        from transcrb.text.inject import type_unicode

        type_unicode("🎉")
        # surrogate pair = 2 code units × 2 events = 4 inputs
        assert si.call_args.args[0] == 4


@pytest.mark.parametrize("text", ["Привет", "日本語", "abc"])
def test_type_unicode_returns_true_on_partial_send(text):
    with patch("transcrb.text.inject._SendInput") as si:
        si.side_effect = lambda n, arr, sz: max(1, n - 1)
        from transcrb.text.inject import type_unicode

        assert type_unicode(text) is True


def test_type_unicode_sendinput_unavailable_returns_false():
    with patch("transcrb.text.inject._SendInput", None):
        from transcrb.text.inject import type_unicode

        assert type_unicode("hi") is False


def test_type_unicode_sleeps_around_send():
    with patch("transcrb.text.inject._SendInput") as si, patch(
        "transcrb.text.inject.time.sleep"
    ) as slp:
        si.side_effect = lambda n, arr, sz: n
        from transcrb.text.inject import type_unicode

        type_unicode("x", pre_delay_ms=10, post_delay_ms=20)
        slp.assert_any_call(0.01)
        slp.assert_any_call(0.02)


def test_type_unicode_zero_delays_no_sleep():
    with patch("transcrb.text.inject._SendInput") as si, patch(
        "transcrb.text.inject.time.sleep"
    ) as slp:
        si.side_effect = lambda n, arr, sz: n
        from transcrb.text.inject import type_unicode

        type_unicode("x")
        slp.assert_not_called()
