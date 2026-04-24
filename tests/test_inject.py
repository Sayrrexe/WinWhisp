from unittest.mock import patch


def test_inject_copies_and_pastes():
    with patch("transcrb.text.inject.pyperclip") as pc, patch(
        "transcrb.text.inject.keyboard"
    ) as kb, patch("transcrb.text.inject.time.sleep"):
        pc.paste.return_value = "old"
        from transcrb.text.inject import inject

        ok = inject("hello", pre_delay_ms=0, post_delay_ms=0, restore=True)
        assert ok
        # copy вызван дважды: один раз для вставляемого текста, второй — на восстановлении
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
