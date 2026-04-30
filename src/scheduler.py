import base64
import logging
import os
import subprocess
import sys
from datetime import datetime
from glob import glob
from pathlib import Path

from src.paths import LOGS_DIR

logger = logging.getLogger("scheduler")

TASK_NAME = "WinLayoutSaver_Rollback"


def _delay_str(seconds: int) -> str:
    """Convert seconds to schtasks /DELAY format: mmmm:ss (total minutes:seconds)."""
    return f"{seconds // 60:04d}:{seconds % 60:02d}"


def _find_executable_for_scheduler(python_exe: str) -> str:
    """
    Task Scheduler가 콘솔창 없이 실행할 수 있는 Python 실행 파일을 선택.
    우선순위:
      1. python.exe → 같은 폴더의 pythonw.exe (콘솔 없음)
      2. WindowsApps 별칭 → pyw.exe (콘솔 없음, 우선) → py.exe → Packages 실경로
      3. 위 모두 실패 시 입력값 그대로 반환 + WARNING.
    """
    import shutil
    from pathlib import Path

    # (1) python.exe 입력 → pythonw.exe 동일 폴더 매핑
    p = Path(python_exe)
    if p.name.lower() == "python.exe":
        cand = p.with_name("pythonw.exe")
        if cand.exists():
            logger.debug("scheduler: swapping python.exe → pythonw.exe (%s)", cand)
            return str(cand)

    # (2) WindowsApps 별칭 처리
    if "WindowsApps" not in str(python_exe):
        return python_exe

    # 2-a. pyw.exe (no-console) 가장 우선
    pyw = shutil.which("pyw")
    if pyw and "WindowsApps" not in pyw:
        logger.debug("scheduler: using pyw.exe launcher: %s", pyw)
        return pyw

    # 2-b. py.exe 폴백
    py = shutil.which("py")
    if py and "WindowsApps" not in py:
        logger.debug("scheduler: using py.exe launcher: %s", py)
        return py

    # 2-c. Packages 아래 실 pythonw.exe / python.exe
    localappdata = os.environ.get("LOCALAPPDATA", "")
    for pattern in [
        localappdata + "\\Packages\\PythonSoftwareFoundation.Python.*"
                     "\\LocalCache\\local-packages\\Python3*\\pythonw.exe",
        localappdata + "\\Packages\\PythonSoftwareFoundation.Python.*"
                     "\\LocalCache\\local-packages\\Python3*\\python.exe",
    ]:
        matches = sorted(glob(pattern), reverse=True)
        if matches:
            logger.debug("scheduler: using real Python from Packages: %s", matches[0])
            return matches[0]

    logger.warning(
        "scheduler: Windows Store Python alias detected in /TR (%s) — "
        "task may show console window; install pyw.exe (Python Launcher) for console-less execution",
        python_exe,
    )
    return python_exe


def _build_register_ps(python_exe: str, script_path: str, delay_seconds: int, username: str) -> str:
    """Build the PowerShell script for Register-ScheduledTask."""
    def sq(s):
        return s.replace("'", "''")
    if script_path:
        action = f"$a = New-ScheduledTaskAction -Execute '{sq(python_exe)}' -Argument '\"{sq(script_path)}\"'; "
    else:
        # Standalone exe (PyInstaller-frozen rollback) — no script argument needed.
        action = f"$a = New-ScheduledTaskAction -Execute '{sq(python_exe)}'; "
    return (
        action +
        f"$t = New-ScheduledTaskTrigger -AtLogOn -User '{sq(username)}'; "
        f"$t.Delay = 'PT{delay_seconds}S'; "
        f"$s = New-ScheduledTaskSettingsSet "
        f"-StartWhenAvailable "
        f"-RunOnlyIfNetworkAvailable:$false "
        f"-Hidden "
        f"-AllowStartIfOnBatteries "
        f"-DontStopIfGoingOnBatteries "
        f"-ExecutionTimeLimit (New-TimeSpan -Minutes 30); "
        f"Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $a -Trigger $t "
        f"-Settings $s -RunLevel Limited -Force | Out-Null"
    )


def register(script_path: str, delay_seconds: int = 10, python_exe: str = None) -> bool:
    """
    Register WinLayoutSaver_Rollback in Windows Task Scheduler.
    Runs at logon for the current user with a startup delay.
    No admin rights needed (RunLevel=Limited, per-user AtLogOn trigger).
    Returns True on success.
    """
    if python_exe is None:
        python_dir = Path(sys.executable).parent
        pythonw = python_dir / "pythonw.exe"
        if not pythonw.exists():
            pythonw = Path(sys.executable)  # fallback
        python_exe = str(pythonw)

    python_exe = _find_executable_for_scheduler(python_exe)

    username = os.environ.get("USERNAME", "")
    ps = _build_register_ps(python_exe, script_path, delay_seconds, username)
    encoded = base64.b64encode(ps.encode("utf-16-le")).decode("ascii")
    cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]

    logger.info(
        "scheduler: registering task (PowerShell) for user=%s delay=%ds",
        username, delay_seconds,
    )
    result = subprocess.run(cmd, capture_output=True, text=True)
    logger.info("scheduler: powershell exit=%d", result.returncode)
    if result.returncode != 0:
        logger.error(
            "scheduler: registration failed — stderr=%s stdout=%s",
            result.stderr.strip(), result.stdout.strip(),
        )
        try:
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            dump_path = LOGS_DIR / f"scheduler-register-error-{ts}.log"
            dump_path.write_text(
                "=== PowerShell command (decoded) ===\n"
                f"{ps}\n\n"
                "=== Exit code ===\n"
                f"{result.returncode}\n\n"
                "=== STDOUT ===\n"
                f"{result.stdout}\n\n"
                "=== STDERR ===\n"
                f"{result.stderr}\n",
                encoding="utf-8",
            )
            logger.info("scheduler: wrote diagnostic dump → %s", dump_path)
        except OSError as e:
            logger.warning("scheduler: failed to write diagnostic dump: %s", e)
        return False
    return True


def run_now() -> tuple[bool, str]:
    """
    schtasks /Run /TN WinLayoutSaver_Rollback 으로 등록된 작업을 즉시 실행 트리거.
    Returns (ok, message). ok=False 인 경우 message에 stderr 포함.
    """
    cmd = ["schtasks.exe", "/Run", "/TN", TASK_NAME]
    logger.info("scheduler: run_now — %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    logger.info("scheduler: run_now exit=%d", result.returncode)
    if result.returncode == 0:
        return True, result.stdout.strip() or "OK"
    return False, (result.stderr.strip() or result.stdout.strip()
                   or f"exit code {result.returncode}")


def unregister() -> bool:
    """
    Remove WinLayoutSaver_Rollback from Windows Task Scheduler.
    Returns True on success or if the task was already not registered.
    """
    cmd = [
        "schtasks.exe",
        "/Delete",
        "/TN", TASK_NAME,
        "/F",
    ]
    logger.info("scheduler: unregistering task — %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    logger.info("scheduler: schtasks exit=%d", result.returncode)
    if result.returncode == 0:
        return True
    # Check whether the task actually exists; if not, the goal is already met.
    query = subprocess.run(
        ["schtasks.exe", "/Query", "/TN", TASK_NAME],
        capture_output=True,
    )
    if query.returncode != 0:
        logger.info("scheduler: task was already not registered — treating as success")
        return True
    logger.error("scheduler: unregister failed — stderr=%s", result.stderr)
    return False
