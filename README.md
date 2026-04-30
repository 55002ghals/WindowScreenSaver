# WinLayoutSaver

Save and restore window layouts on Windows. Capture where every visible app window is sitting (across multiple monitors), and restore that exact arrangement later — including launching apps that aren't running yet, and re-applying positions after a logon.

- 🪟 Multi-monitor aware (per-monitor DPI, virtual desktop)
- 💾 Per-layout JSON snapshots in `%APPDATA%\WinLayoutSaver`
- 🖼️ Full-screen PNG preview saved alongside each layout
- ⏱️ Optional auto-restore on logon (Windows Task Scheduler)
- 🌐 Korean / English UI

---

## Install (end users)

1. Download `WinLayoutSaverSetup.exe` from the [Releases](../../releases) page.
2. Run it. No admin rights required — it installs per-user under `%LOCALAPPDATA%\Programs\WinLayoutSaver`.
3. Launch from the Start Menu (or the desktop shortcut, if you ticked the box).

The installer drops two executables:

| File | Purpose |
|------|---------|
| `WinLayoutSaver.exe` | Main GUI. Use this. |
| `WinLayoutSaverRollback.exe` | Headless restore — invoked by Task Scheduler if you enable auto-restore. Don't run by hand. |

User data (saved layouts, screenshots, config, logs) lives in `%APPDATA%\WinLayoutSaver\` and is preserved across upgrades and uninstalls.

### Uninstall

Apps & Features → WinLayoutSaver → Uninstall. The scheduled rollback task is removed automatically; layouts under `%APPDATA%\WinLayoutSaver\` are kept (delete the folder by hand if you want them gone).

---

## Usage

### Save a layout

Click **현재 배치 저장 / Save Current Layout**. A new `Screen<N>` row appears, tagged with the timestamp. A full virtual-desktop PNG is captured at the same time — click **미리보기 / Preview** on a row to view it later.

### Restore

Click **복원 / Restore** on a row. WinLayoutSaver reapplies window positions; in **Full** mode it also relaunches missing apps before placing them.

If your monitor configuration has changed since the layout was saved, the row shows `⚠Not matched` (orange) or `⚠mismatch` (red) — restore still works, but windows may land on unexpected screens.

### Auto-restore on logon

In the **부팅 자동 복구 / Auto-restore on boot** section:

1. Pick a layout from the dropdown.
2. Choose mode: **Quick** (reposition existing windows only) or **Full** (also relaunch missing apps).
3. Set startup delay (seconds after logon).
4. Click **활성화 / Enable**.

This registers a per-user Windows scheduled task — no admin elevation. Click again to disable.

---

## Build from source

You'll need: Windows 10/11, Python 3.11+, and `pip`. The build script installs everything else (PyInstaller, Inno Setup) automatically via `winget` if missing.

```cmd
git clone https://github.com/<you>/WinLayoutSaver.git
cd WinLayoutSaver
build.bat
```

Output:

- `dist\WinLayoutSaver\` — runnable bundle (run `WinLayoutSaver.exe` directly to test)
- `installer\Output\WinLayoutSaverSetup.exe` — distributable installer

### Manual build

```cmd
pip install -r requirements.txt -r requirements-dev.txt
pyinstaller WinLayoutSaver.spec --noconfirm
ISCC.exe /DMyAppVersion=1.12.0 installer\WinLayoutSaver.iss
```

---

## Run from source (development)

```cmd
install.bat        :: install Python deps
python main.py     :: launch GUI
```

### Run tests

```cmd
pytest -q                       :: full unit suite
pytest --ignore=tests/integration -q   :: skip live-Notepad integration tests
```

---

## Project layout

```
.
├── main.py                    GUI entry point
├── cli/rollback.py            Headless restore (Task Scheduler target)
├── src/
│   ├── gui.py                 Tk UI
│   ├── capture.py             Window enumeration + virtual-desktop PNG
│   ├── restore.py             Reposition / relaunch logic
│   ├── monitors.py            DPI + multi-monitor geometry
│   ├── storage.py             JSON layout I/O
│   ├── scheduler.py           Windows Task Scheduler wrapper
│   ├── i18n.py                Korean / English strings
│   └── ...
├── tests/                     pytest suite (~200 tests)
├── WinLayoutSaver.spec        PyInstaller config (builds 2 exes)
├── installer/WinLayoutSaver.iss   Inno Setup installer script
├── build.bat                  end-to-end build orchestrator
└── requirements*.txt
```

---

## Tech stack

Python 3.11+ · tkinter · pywin32 · psutil · Pillow · PyInstaller · Inno Setup

## License

[MIT](LICENSE).
