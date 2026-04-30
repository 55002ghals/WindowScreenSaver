"""Integration tests for src/scheduler.py — calls real schtasks.exe.

Run with:
    pytest tests/integration/test_scheduler_real.py -m integration -v --tb=short

Each test cleans up after itself via scheduler.unregister().
"""
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from src import scheduler

ROLLBACK_PY = Path(__file__).parent.parent.parent / "cli" / "rollback.py"


@pytest.fixture(autouse=True)
def _cleanup_task():
    """Ensure the scheduler task is removed before and after each test."""
    subprocess.run(
        ["schtasks.exe", "/Delete", "/TN", scheduler.TASK_NAME, "/F"],
        capture_output=True,
    )
    yield
    subprocess.run(
        ["schtasks.exe", "/Delete", "/TN", scheduler.TASK_NAME, "/F"],
        capture_output=True,
    )


@pytest.mark.integration
def test_its1_register_creates_task():
    """register() succeeds and task appears in /Query output."""
    result = scheduler.register(script_path=str(ROLLBACK_PY), delay_seconds=10)
    assert result is True, "register() returned False — check schtasks stderr in logs"

    query = subprocess.run(
        ["schtasks.exe", "/Query", "/TN", scheduler.TASK_NAME],
        capture_output=True,
    )
    assert query.returncode == 0, "task was not found after register()"


@pytest.mark.integration
def test_its2_unregister_removes_task():
    """After register() + unregister(), /Query no longer finds the task."""
    scheduler.register(script_path=str(ROLLBACK_PY), delay_seconds=10)

    result = scheduler.unregister()
    assert result is True, "unregister() returned False"

    query = subprocess.run(
        ["schtasks.exe", "/Query", "/TN", scheduler.TASK_NAME],
        capture_output=True,
    )
    assert query.returncode != 0, "task still exists after unregister()"


@pytest.mark.integration
def test_its3_unregister_when_not_registered():
    """unregister() returns True when the task doesn't exist (idempotent)."""
    # _cleanup_task fixture already deleted it; confirm absence
    query = subprocess.run(
        ["schtasks.exe", "/Query", "/TN", scheduler.TASK_NAME],
        capture_output=True,
    )
    assert query.returncode != 0, "task unexpectedly exists before test"

    result = scheduler.unregister()
    assert result is True, "unregister() should return True when task is absent"


@pytest.mark.integration
def test_its4_register_ps_command_contains_script_path():
    """The PowerShell -EncodedCommand must reference the correct script_path."""
    import base64
    captured = {}
    orig_run = subprocess.run

    def intercept(cmd, **kw):
        if isinstance(cmd, list) and "powershell" in str(cmd[0]).lower():
            captured["cmd"] = cmd
        return orig_run(cmd, **kw)

    with patch("subprocess.run", side_effect=intercept):
        scheduler.register(script_path=str(ROLLBACK_PY), delay_seconds=10)

    assert "cmd" in captured, "powershell.exe was never called by register()"

    cmd = captured["cmd"]
    enc_idx = next((i for i, v in enumerate(cmd) if v == "-EncodedCommand"), None)
    assert enc_idx is not None, "-EncodedCommand not found in powershell command"
    ps = base64.b64decode(cmd[enc_idx + 1]).decode("utf-16-le")

    assert str(ROLLBACK_PY) in ps, f"script_path not found in PS command: {ps[:200]}"
    assert "Register-ScheduledTask" in ps
    assert "AtLogOn" in ps
