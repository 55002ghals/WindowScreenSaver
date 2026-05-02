STRINGS = {
    "ko": {
        "app_title": "WinLayoutSaver",
        "save_btn": "현재 배치 저장",
        "refresh_btn": "새로고침",
        "restore_btn": "복원",
        "settings_btn": "설정",
        "delete_btn": "삭제",
        "auto_rollback_label": "부팅 시 자동 복구:",
        "startup_delay_label": "시작 지연(초):",
        "enable_btn": "활성화",
        "disable_btn": "비활성화",
        "run_now_btn": "지금 실행",
        "run_now_success_msg": "자동 복구 작업을 트리거했습니다. 잠시 후 로그를 확인하세요.",
        "run_now_failed_msg": "자동 복구 실행 실패: {error}",
        "migrate_task_log": "기존 자동복구 작업을 새 설정으로 재등록합니다 (배터리 옵션 갱신)",
        "enabled_status": "활성화됨",
        "status_label": "상태:",
        "log_panel_title": "로그",
        "clear_btn": "지우기",
        "copy_btn": "복사",
        "open_log_dir_btn": "로그 폴더 열기",
        "confirm_restore_title": "모니터 구성 불일치",
        "confirm_restore_msg": "외부 모니터 구성이 달라 주 모니터 창만 복원됩니다. 계속하시겠습니까?",
        "yes": "예",
        "no": "아니오",
        "rename_dialog_title": "레이아웃 이름 변경",
        "rename_label": "새 이름:",
        "layout_deleted": "'{name}' 삭제됨",
        "layout_restored": "'{name}' 복원 완료 ({restored}/{total})",
        "layout_saved": "'{name}' 저장됨 ({count}개 창)",
        "no_layouts": "저장된 배치 없음",
        "log_module_filter_label": "모듈:",
        "mode_fast": "빠른 복구",
        "mode_full": "전체 복구",
        "mode_fast_desc": "이미 실행 중인 창만 재배치",
        "mode_full_desc": "없는 앱 자동 실행 후 배치",
        "saved_at_format": "%y.%m.%d/%H:%M:%S",
        "not_matched_label": "⚠Not matched",
        "preview_btn": "미리보기",
        "ar_section_title": "부팅 자동 복구",
        "mode_label": "모드:",
        "screenshot_missing_msg": "이 레이아웃에는 저장된 미리보기 이미지가 없습니다.",
        "preview_window_title": "미리보기 — {name}",
        "register_failed_msg": "자동복구 작업 등록에 실패했습니다.\n로그 파일을 확인하세요:\n{log_dir}",
        "run_now_not_registered_msg": "자동복구 작업이 등록되어 있지 않습니다.\n먼저 활성화 버튼을 눌러 등록하세요.",
        "migrate_failed_status": "자동복구 작업 마이그레이션 실패 — 다음 실행 시 재시도합니다.",
    },
    "en": {
        "app_title": "WinLayoutSaver",
        "save_btn": "Save Current Layout",
        "refresh_btn": "Refresh",
        "restore_btn": "Restore",
        "settings_btn": "Settings",
        "delete_btn": "Delete",
        "auto_rollback_label": "Auto-restore on boot:",
        "startup_delay_label": "Startup delay (sec):",
        "enable_btn": "Enable",
        "disable_btn": "Disable",
        "run_now_btn": "Run now",
        "run_now_success_msg": "Auto-recovery task triggered. Check logs in a moment.",
        "run_now_failed_msg": "Failed to run auto-recovery: {error}",
        "migrate_task_log": "Re-registering existing auto-recovery task with updated settings (battery flags)",
        "enabled_status": "Enabled",
        "status_label": "Status:",
        "log_panel_title": "Logs",
        "clear_btn": "Clear",
        "copy_btn": "Copy",
        "open_log_dir_btn": "Open log folder",
        "confirm_restore_title": "Monitor mismatch",
        "confirm_restore_msg": "External monitor config differs. Only primary monitor windows will be restored. Continue?",
        "yes": "Yes",
        "no": "No",
        "rename_dialog_title": "Rename Layout",
        "rename_label": "New name:",
        "layout_deleted": "'{name}' deleted",
        "layout_restored": "'{name}' restored ({restored}/{total})",
        "layout_saved": "'{name}' saved ({count} windows)",
        "no_layouts": "No saved layouts",
        "log_module_filter_label": "Module:",
        "mode_fast": "Quick restore",
        "mode_full": "Full restore",
        "mode_fast_desc": "Reposition already-running windows only",
        "mode_full_desc": "Launch missing apps, then reposition",
        "saved_at_format": "%y.%m.%d/%H:%M:%S",
        "not_matched_label": "⚠Not matched",
        "preview_btn": "Preview",
        "ar_section_title": "Auto-restore on boot",
        "mode_label": "Mode:",
        "screenshot_missing_msg": "No preview image saved for this layout.",
        "preview_window_title": "Preview — {name}",
        "register_failed_msg": "Failed to register the auto-recovery task.\nCheck the log files at:\n{log_dir}",
        "run_now_not_registered_msg": "The auto-recovery task is not registered.\nClick the Enable button first to register it.",
        "migrate_failed_status": "Auto-recovery task migration failed — will retry on next launch.",
    },
}

_lang = "ko"


def set_language(lang: str) -> None:
    global _lang
    if lang in STRINGS:
        _lang = lang


def t(key: str, **kwargs) -> str:
    text = STRINGS.get(_lang, STRINGS["ko"]).get(key) or STRINGS["ko"].get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text


def available_languages() -> list[str]:
    return list(STRINGS.keys())
