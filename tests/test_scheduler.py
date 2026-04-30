import logging
import pytest
from unittest.mock import patch, MagicMock


def make_ok_result(stdout="", returncode=0):
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = ""
    return r


def _decode_ps(mock_run) -> str:
    """Decode the base64-encoded PowerShell command from a mocked subprocess.run call."""
    import base64
    cmd = mock_run.call_args[0][0]
    enc_idx = next(i for i, v in enumerate(cmd) if v == "-EncodedCommand")
    return base64.b64decode(cmd[enc_idx + 1]).decode("utf-16-le")


class TestRegister:
    def test_register_calls_powershell(self):
        """register() must invoke powershell.exe with Register-ScheduledTask."""
        with patch("subprocess.run", return_value=make_ok_result()) as mock_run:
            from src import scheduler
            scheduler.register(script_path="C:\\path\\to\\rollback.py", delay_seconds=20)
            assert mock_run.called
            cmd = mock_run.call_args[0][0]
            assert "powershell.exe" in cmd[0].lower()
            ps = _decode_ps(mock_run)
            assert "Register-ScheduledTask" in ps
            assert "WinLayoutSaver_Rollback" in ps

    def test_register_includes_delay(self):
        """register() must encode delay_seconds as ISO 8601 duration in the PS command."""
        with patch("subprocess.run", return_value=make_ok_result()) as mock_run:
            from src import scheduler
            scheduler.register(script_path="C:\\path\\to\\rollback.py", delay_seconds=90)
            ps = _decode_ps(mock_run)
            assert "PT90S" in ps

    def test_register_delay_20_seconds(self):
        """20 seconds → PT20S."""
        with patch("subprocess.run", return_value=make_ok_result()) as mock_run:
            from src import scheduler
            scheduler.register(script_path="C:\\path\\to\\rollback.py", delay_seconds=20)
            ps = _decode_ps(mock_run)
            assert "PT20S" in ps

    def test_register_uses_rl_limited(self):
        """RunLevel must be Limited — no admin rights required."""
        with patch("subprocess.run", return_value=make_ok_result()) as mock_run:
            from src import scheduler
            scheduler.register(script_path="C:\\path\\to\\rollback.py", delay_seconds=20)
            ps = _decode_ps(mock_run)
            assert "Limited" in ps

    def test_register_returns_true_on_success(self):
        with patch("subprocess.run", return_value=make_ok_result(returncode=0)):
            from src import scheduler
            result = scheduler.register(script_path="C:\\path\\rollback.py", delay_seconds=20)
            assert result is True

    def test_register_returns_false_on_failure(self):
        with patch("subprocess.run", return_value=make_ok_result(returncode=1)):
            from src import scheduler
            result = scheduler.register(script_path="C:\\path\\rollback.py", delay_seconds=20)
            assert result is False

    def test_register_uses_hidden_setting(self):
        """Register-ScheduledTask 설정에 -Hidden이 포함되어야 한다."""
        with patch("subprocess.run", return_value=make_ok_result()) as mock_run:
            from src import scheduler
            scheduler.register(script_path="C:\\path\\rollback.py", delay_seconds=20)
            ps = _decode_ps(mock_run)
            assert "-Hidden" in ps


class TestUnregister:
    def test_unregister_calls_schtasks_delete(self):
        with patch("subprocess.run", return_value=make_ok_result()) as mock_run:
            from src.scheduler import unregister
            unregister()
            args = mock_run.call_args[0][0]
            cmd_str = " ".join(str(a) for a in args)
            assert "/Delete" in cmd_str or "/delete" in cmd_str.lower()
            assert "WinLayoutSaver_Rollback" in cmd_str

    def test_unregister_uses_force_flag(self):
        with patch("subprocess.run", return_value=make_ok_result()) as mock_run:
            from src.scheduler import unregister
            unregister()
            args = mock_run.call_args[0][0]
            cmd_str = " ".join(str(a) for a in args)
            assert "/F" in cmd_str

    def test_unregister_returns_true_on_success(self):
        with patch("subprocess.run", return_value=make_ok_result(returncode=0)):
            from src.scheduler import unregister
            assert unregister() is True

    def test_unregister_returns_false_on_failure(self):
        # Delete fails AND Query confirms task still exists → False
        with patch("subprocess.run", side_effect=[
            make_ok_result(returncode=1),  # /Delete → fail
            make_ok_result(returncode=0),  # /Query → task exists
        ]):
            from src.scheduler import unregister
            assert unregister() is False


# ──────────────────────────────────────────────────────────────────────────────
# New tests: UT-S1 to UT-S9
# ──────────────────────────────────────────────────────────────────────────────

class TestRegisterRU:
    def test_register_includes_current_user(self, monkeypatch):
        """register() PS command must include the current USERNAME for per-user logon trigger."""
        monkeypatch.setenv("USERNAME", "testuser")
        with patch("subprocess.run", return_value=make_ok_result()) as mock_run:
            from src import scheduler
            scheduler.register(script_path="C:\\path\\rollback.py", delay_seconds=20)
            ps = _decode_ps(mock_run)
            assert "AtLogOn" in ps
            assert "testuser" in ps

    def test_register_uses_atlogon_trigger(self):
        """register() PS command must use AtLogOn trigger (replaces schtasks /RU+/NP)."""
        with patch("subprocess.run", return_value=make_ok_result()) as mock_run:
            from src import scheduler
            scheduler.register(script_path="C:\\path\\rollback.py", delay_seconds=20)
            ps = _decode_ps(mock_run)
            assert "AtLogOn" in ps


class TestFindExecutableForScheduler:
    def test_non_store_path_returned_as_is(self):
        """Non-WindowsApps path is returned unchanged."""
        from src.scheduler import _find_executable_for_scheduler
        path = "C:\\Python313\\pythonw.exe"
        assert _find_executable_for_scheduler(path) == path

    def test_store_path_uses_py_launcher(self, monkeypatch):
        """WindowsApps alias + py.exe found → returns py.exe path."""
        import shutil as _shutil
        monkeypatch.setattr(_shutil, "which", lambda x: "C:\\Windows\\py.exe" if x == "py" else None)
        import src.scheduler as sched
        monkeypatch.setattr(sched, "glob", lambda p: [])
        from src.scheduler import _find_executable_for_scheduler
        result = _find_executable_for_scheduler(
            "C:\\Users\\user\\AppData\\Local\\Microsoft\\WindowsApps\\pythonw.exe"
        )
        assert result == "C:\\Windows\\py.exe"

    def test_store_path_uses_packages_when_no_py_launcher(self, monkeypatch, tmp_path):
        """WindowsApps alias + no py.exe + Packages path found → returns Packages path."""
        import shutil as _shutil
        monkeypatch.setattr(_shutil, "which", lambda x: None)
        fake_pythonw = tmp_path / "pythonw.exe"
        fake_pythonw.write_text("")
        import src.scheduler as sched
        monkeypatch.setattr(sched, "glob", lambda p: [str(fake_pythonw)])
        from src.scheduler import _find_executable_for_scheduler
        result = _find_executable_for_scheduler(
            "C:\\Users\\user\\AppData\\Local\\Microsoft\\WindowsApps\\pythonw.exe"
        )
        assert result == str(fake_pythonw)

    def test_store_path_fallback_returns_original_with_warning(self, monkeypatch, caplog):
        """WindowsApps alias + no alternatives → original path returned with WARNING."""
        import shutil as _shutil
        monkeypatch.setattr(_shutil, "which", lambda x: None)
        import src.scheduler as sched
        monkeypatch.setattr(sched, "glob", lambda p: [])
        from src.scheduler import _find_executable_for_scheduler
        original = "C:\\Users\\user\\AppData\\Local\\Microsoft\\WindowsApps\\pythonw.exe"
        with caplog.at_level(logging.WARNING, logger="scheduler"):
            result = _find_executable_for_scheduler(original)
        assert result == original
        assert "Windows Store Python alias" in caplog.text


    def test_store_path_prefers_pyw_over_py(self, monkeypatch):
        """pyw.exe와 py.exe 모두 있으면 pyw.exe를 선호."""
        import shutil as _shutil
        def which(x):
            if x == "pyw":
                return "C:\\Windows\\pyw.exe"
            if x == "py":
                return "C:\\Windows\\py.exe"
            return None
        monkeypatch.setattr(_shutil, "which", which)
        import src.scheduler as sched
        monkeypatch.setattr(sched, "glob", lambda p: [])
        from src.scheduler import _find_executable_for_scheduler
        result = _find_executable_for_scheduler(
            "C:\\Users\\u\\AppData\\Local\\Microsoft\\WindowsApps\\pythonw.exe"
        )
        assert result == "C:\\Windows\\pyw.exe"

    def test_python_exe_path_swapped_to_pythonw(self, monkeypatch, tmp_path):
        """python.exe를 받았는데 같은 폴더에 pythonw.exe가 있으면 그것을 사용."""
        py = tmp_path / "python.exe"
        pyw = tmp_path / "pythonw.exe"
        py.write_text(""); pyw.write_text("")
        from src.scheduler import _find_executable_for_scheduler
        result = _find_executable_for_scheduler(str(py))
        assert result == str(pyw)


class TestUnregisterIdempotent:
    def test_unregister_returns_true_when_task_not_found(self):
        """unregister() returns True when task doesn't exist (idempotent)."""
        with patch("subprocess.run", side_effect=[
            make_ok_result(returncode=1),  # /Delete → fail
            make_ok_result(returncode=1),  # /Query → not found
        ]):
            from src.scheduler import unregister
            assert unregister() is True

    def test_unregister_returns_false_when_task_exists_but_delete_fails(self):
        """unregister() returns False when task exists but can't be deleted."""
        with patch("subprocess.run", side_effect=[
            make_ok_result(returncode=1),  # /Delete → fail
            make_ok_result(returncode=0),  # /Query → task exists
        ]):
            from src.scheduler import unregister
            assert unregister() is False


class TestBuildRegisterPs:
    def test_build_register_ps_allows_battery_start(self):
        from src.scheduler import _build_register_ps
        ps = _build_register_ps("C:\\pyw.exe", "C:\\rollback.py", 10, "ab550")
        assert "-AllowStartIfOnBatteries" in ps

    def test_build_register_ps_does_not_stop_on_battery(self):
        from src.scheduler import _build_register_ps
        ps = _build_register_ps("C:\\pyw.exe", "C:\\rollback.py", 10, "ab550")
        assert "-DontStopIfGoingOnBatteries" in ps

    def test_build_register_ps_has_execution_time_limit(self):
        from src.scheduler import _build_register_ps
        ps = _build_register_ps("C:\\pyw.exe", "C:\\rollback.py", 10, "ab550")
        assert "ExecutionTimeLimit" in ps
        assert "Minutes 30" in ps

    def test_build_register_ps_keeps_existing_flags(self):
        from src.scheduler import _build_register_ps
        ps = _build_register_ps("C:\\pyw.exe", "C:\\rollback.py", 10, "ab550")
        assert "-StartWhenAvailable" in ps
        assert "-Hidden" in ps
        assert "-RunOnlyIfNetworkAvailable:$false" in ps
        assert "AtLogOn" in ps
        assert "PT10S" in ps

    def test_build_register_ps_standalone_exe_no_argument(self):
        from src.scheduler import _build_register_ps
        ps = _build_register_ps("C:\\WinLayoutSaverRollback.exe", "", 10, "ab550")
        assert "-Argument" not in ps
        assert "WinLayoutSaverRollback.exe" in ps


class TestRunNow:
    def test_run_now_success(self, monkeypatch):
        import src.scheduler as sched_mod
        import subprocess
        captured = {}
        def fake_run(cmd, **kw):
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0, "성공: ...", "")
        monkeypatch.setattr(subprocess, "run", fake_run)

        ok, msg = sched_mod.run_now()
        assert ok is True
        assert captured["cmd"][:3] == ["schtasks.exe", "/Run", "/TN"]
        assert captured["cmd"][3] == sched_mod.TASK_NAME

    def test_run_now_failure(self, monkeypatch):
        import src.scheduler as sched_mod
        import subprocess
        monkeypatch.setattr(subprocess, "run",
            lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "오류: 작업 없음"))

        ok, msg = sched_mod.run_now()
        assert ok is False
        assert "오류: 작업 없음" in msg


class TestRegisterDiagnostic:
    def test_register_writes_diagnostic_on_failure(self, monkeypatch, tmp_path):
        import src.scheduler as sched_mod
        import subprocess

        monkeypatch.setattr(sched_mod, "LOGS_DIR", tmp_path)

        fake_result = subprocess.CompletedProcess(
            args=["powershell.exe"], returncode=1,
            stdout="some stdout", stderr="some stderr",
        )
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)

        ok = sched_mod.register(script_path="C:\\rollback.py", delay_seconds=10,
                                python_exe="C:\\pyw.exe")
        assert ok is False

        dumps = list(tmp_path.glob("scheduler-register-error-*.log"))
        assert len(dumps) == 1
        text = dumps[0].read_text(encoding="utf-8")
        assert "=== STDERR ===" in text
        assert "some stderr" in text
        assert "=== STDOUT ===" in text
        assert "some stdout" in text
        assert "=== Exit code ===" in text
        assert "Register-ScheduledTask" in text

    def test_register_no_diagnostic_on_success(self, monkeypatch, tmp_path):
        import src.scheduler as sched_mod
        import subprocess

        monkeypatch.setattr(sched_mod, "LOGS_DIR", tmp_path)
        fake_result = subprocess.CompletedProcess(
            args=["powershell.exe"], returncode=0, stdout="", stderr="",
        )
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)

        ok = sched_mod.register(script_path="C:\\rollback.py", delay_seconds=10,
                                python_exe="C:\\pyw.exe")
        assert ok is True
        assert list(tmp_path.glob("scheduler-register-error-*.log")) == []


class TestDelayStr:
    def test_delay_str_one_hour(self):
        """3600 seconds = 0060:00 (60 minutes), not 0100:00."""
        from src.scheduler import _delay_str
        assert _delay_str(3600) == "0060:00"

    def test_delay_str_90_minutes(self):
        """5400 seconds = 0090:00."""
        from src.scheduler import _delay_str
        assert _delay_str(5400) == "0090:00"
