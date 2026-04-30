"""tests/test_rollback_shell_wait.py — wait_for_shell_ready 단위 테스트."""
import sys
import importlib


def _import_rollback():
    sys.modules.pop("cli.rollback", None)
    return importlib.import_module("cli.rollback")


def test_returns_count_immediately_when_windows_present():
    rb = _import_rollback()
    n = rb.wait_for_shell_ready(
        list_windows_fn=lambda: [{"hwnd": 1}, {"hwnd": 2}],
        interval_s=0.0, max_tries=5,
        sleep_fn=lambda s: None,
    )
    assert n == 2


def test_polls_until_nonzero():
    rb = _import_rollback()
    counter = {"n": 0}
    def fake_list():
        counter["n"] += 1
        return [] if counter["n"] < 3 else [{"hwnd": 1}]
    slept = []
    n = rb.wait_for_shell_ready(
        list_windows_fn=fake_list,
        interval_s=5.0, max_tries=10,
        sleep_fn=lambda s: slept.append(s),
    )
    assert n == 1
    assert counter["n"] == 3
    assert slept == [5.0, 5.0]


def test_returns_zero_after_max_tries():
    rb = _import_rollback()
    slept = []
    n = rb.wait_for_shell_ready(
        list_windows_fn=lambda: [],
        interval_s=5.0, max_tries=4,
        sleep_fn=lambda s: slept.append(s),
    )
    assert n == 0
    assert len(slept) == 3
