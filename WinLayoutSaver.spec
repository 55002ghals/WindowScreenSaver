# PyInstaller spec — builds two exes into a single onedir bundle:
#   dist/WinLayoutSaver/WinLayoutSaver.exe          (windowed GUI)
#   dist/WinLayoutSaver/WinLayoutSaverRollback.exe  (console-less headless rollback)
# Run:  pyinstaller WinLayoutSaver.spec --noconfirm
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# ── GUI ────────────────────────────────────────────────────────────────────────
gui_a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=['PIL._tkinter_finder'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)
gui_pyz = PYZ(gui_a.pure, gui_a.zipped_data, cipher=block_cipher)
gui_exe = EXE(
    gui_pyz,
    gui_a.scripts,
    [],
    exclude_binaries=True,
    name='WinLayoutSaver',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,            # windowed — no console
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# ── Rollback (headless) ────────────────────────────────────────────────────────
roll_a = Analysis(
    ['cli/rollback.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)
roll_pyz = PYZ(roll_a.pure, roll_a.zipped_data, cipher=block_cipher)
roll_exe = EXE(
    roll_pyz,
    roll_a.scripts,
    [],
    exclude_binaries=True,
    name='WinLayoutSaverRollback',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,            # also windowed — no console flash on logon
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# ── Single onedir COLLECT containing both exes + shared dependencies ───────────
coll = COLLECT(
    gui_exe,
    gui_a.binaries, gui_a.zipfiles, gui_a.datas,
    roll_exe,
    roll_a.binaries, roll_a.zipfiles, roll_a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='WinLayoutSaver',
)
