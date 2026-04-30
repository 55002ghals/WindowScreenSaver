def test_gui_imports_version():
    """GUI 모듈이 src.version에서 __version__을 가져오는지 확인."""
    import importlib
    import src.gui as gui
    importlib.reload(gui)
    assert hasattr(gui, "__version__") or "version" in dir(gui)
    # 정확한 검증: gui.py 소스 안에 'from src.version import __version__'이 있어야 함
    from pathlib import Path
    src_text = Path(gui.__file__).read_text(encoding="utf-8")
    assert "from src.version import __version__" in src_text
    assert "v" in src_text and "__version__" in src_text  # 라벨에서 사용 흔적
