import logging
import os
import queue
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, simpledialog, scrolledtext, ttk

from src import storage, capture, restore as restore_mod, scheduler
from src.i18n import t, set_language
from src.logging_setup import setup_logging
from src.monitors import list_current_monitors, compare_monitors, MatchResult
from src.paths import LOGS_DIR
from src.version import __version__

logger = logging.getLogger("gui")


class WinLayoutSaverApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self._log_queue: queue.Queue = queue.Queue()
        setup_logging(enable_gui_handler=True, gui_queue=self._log_queue)

        config = storage.load_config()
        lang = config.get("ui", {}).get("language", "ko")
        set_language(lang)

        self.title(t("app_title"))
        self.geometry("800x600")
        self.resizable(True, True)

        self._current_monitors: list[dict] = []

        self._build_ui()
        self._refresh_layouts()
        self._drain_log_queue()
        self._poll_monitors()
        self._migrate_existing_task()

    # ── UI construction ─────────────────────────────────────────────────

    def _build_ui(self):
        # Footer (version label) — pack BOTTOM 먼저 호출해야 항상 하단에 고정됨
        footer = tk.Frame(self)
        footer.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 4))
        tk.Label(footer, text=f"v{__version__}", anchor="w",
                 fg="#888", font=("Consolas", 9)).pack(side=tk.LEFT)

        # Monitor strip
        self._monitor_strip_var = tk.StringVar(value="Monitors: detecting…")
        tk.Label(self, textvariable=self._monitor_strip_var, anchor="w", fg="#444",
                 font=("Consolas", 9)).pack(fill=tk.X, padx=8, pady=(4, 0))

        # Top toolbar
        toolbar = tk.Frame(self, pady=4)
        toolbar.pack(fill=tk.X, padx=8)
        tk.Button(toolbar, text=t("save_btn"), command=self._on_save).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text=t("refresh_btn"), command=self._refresh_layouts).pack(side=tk.LEFT, padx=2)

        # Layout list
        list_frame = tk.LabelFrame(self, text="Layouts", padx=4, pady=4)
        list_frame.pack(fill=tk.BOTH, expand=False, padx=8, pady=4)
        self._layout_inner = tk.Frame(list_frame)
        self._layout_inner.pack(fill=tk.X)

        # ─── Auto-rollback section (LabelFrame) ───────────────────────────
        self._ar_section = tk.LabelFrame(self, text=t("ar_section_title"), padx=8, pady=6)
        self._ar_section.pack(fill=tk.X, padx=8, pady=4)

        # 행 0: 활성화 버튼
        self._ar_toggle_btn = tk.Button(self._ar_section, text=t("enable_btn"),
                                        command=self._on_ar_toggle, padx=4, pady=0)
        self._ar_toggle_btn.grid(row=0, column=0, sticky="w", pady=(0, 6))

        self._run_now_btn = tk.Button(self._ar_section, text=t("run_now_btn"),
                                      command=self._on_run_now, padx=4, pady=0)
        self._run_now_btn.grid(row=0, column=1, columnspan=3, sticky="w",
                               padx=(8, 0), pady=(0, 6))

        # 행 1: 레이아웃 라벨 + 콤보
        tk.Label(self._ar_section, text=t("auto_rollback_label")).grid(row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        self._ar_layout_var = tk.StringVar()
        self._ar_combo = ttk.Combobox(self._ar_section, textvariable=self._ar_layout_var, state="readonly", width=16)
        self._ar_combo.grid(row=1, column=1, columnspan=3, sticky="w", pady=2)

        # 행 2: 모드 라벨 + Radio 2개 + 설명
        tk.Label(self._ar_section, text=t("mode_label")).grid(row=2, column=0, sticky="w", padx=(0, 6), pady=2)
        self._ar_mode_var = tk.StringVar(value="full")
        self._ar_mode_fast_rb = tk.Radiobutton(
            self._ar_section, text=t("mode_fast"),
            variable=self._ar_mode_var, value="fast",
            command=self._on_mode_change,
        )
        self._ar_mode_fast_rb.grid(row=2, column=1, sticky="w", pady=2)
        self._ar_mode_full_rb = tk.Radiobutton(
            self._ar_section, text=t("mode_full"),
            variable=self._ar_mode_var, value="full",
            command=self._on_mode_change,
        )
        self._ar_mode_full_rb.grid(row=2, column=2, sticky="w", padx=(8, 0), pady=2)
        self._mode_desc_var = tk.StringVar()
        tk.Label(
            self._ar_section, textvariable=self._mode_desc_var,
            fg="#555", font=("Consolas", 9),
        ).grid(row=2, column=3, sticky="w", padx=(16, 0), pady=2)

        # 행 3: 시작 지연 라벨 + Entry
        tk.Label(self._ar_section, text=t("startup_delay_label")).grid(row=3, column=0, sticky="w", padx=(0, 6), pady=2)
        self._delay_var = tk.StringVar(value="1")
        self._delay_entry = tk.Entry(self._ar_section, textvariable=self._delay_var, width=5)
        self._delay_entry.grid(row=3, column=1, sticky="w", pady=2)
        # ───────────────────────────────────────────────────────────────────

        # Status bar
        self._status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._status_var, anchor="w").pack(fill=tk.X, padx=8)

        # Log panel (splitter via PanedWindow)
        paned = tk.PanedWindow(self, orient=tk.VERTICAL, sashrelief=tk.RAISED)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        log_frame = tk.LabelFrame(paned, text=t("log_panel_title"), padx=4, pady=4)
        paned.add(log_frame, minsize=80)

        # Log filter checkboxes
        filter_row = tk.Frame(log_frame)
        filter_row.pack(fill=tk.X)
        self._log_levels = {}
        for lvl in ("DEBUG", "INFO", "WARN", "ERROR"):
            var = tk.BooleanVar(value=(lvl != "DEBUG"))
            cb = tk.Checkbutton(filter_row, text=lvl, variable=var, command=self._apply_log_filter)
            cb.pack(side=tk.LEFT)
            self._log_levels[lvl] = var

        # Module filter checkboxes (monitors off by default)
        self._module_filters: dict[str, tk.BooleanVar] = {}
        module_row = tk.Frame(log_frame)
        module_row.pack(fill=tk.X)
        tk.Label(module_row, text=t("log_module_filter_label")).pack(side=tk.LEFT)
        _MODULES = ["monitors", "capture", "restore", "launcher",
                    "scheduler", "gui", "rollback", "storage"]
        for mod in _MODULES:
            var = tk.BooleanVar(value=(mod != "monitors"))
            tk.Checkbutton(module_row, text=mod, variable=var,
                           command=self._apply_log_filter).pack(side=tk.LEFT)
            self._module_filters[mod] = var

        btn_row = tk.Frame(log_frame)
        btn_row.pack(fill=tk.X)
        tk.Button(btn_row, text=t("clear_btn"), command=self._clear_log).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_row, text=t("copy_btn"), command=self._copy_log).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_row, text=t("open_log_dir_btn"), command=self._open_log_dir).pack(side=tk.LEFT, padx=2)

        self._log_text = scrolledtext.ScrolledText(log_frame, state=tk.DISABLED, height=8,
                                                    font=("Consolas", 9), wrap=tk.NONE)
        self._log_text.pack(fill=tk.BOTH, expand=True)

        # Color tags
        self._log_text.tag_config("DEBUG", foreground="gray")
        self._log_text.tag_config("INFO", foreground="black")
        self._log_text.tag_config("WARN", foreground="orange")
        self._log_text.tag_config("ERROR", foreground="red")

        # Buffer to re-apply filter
        self._log_buffer: list[tuple[str, str, str]] = []  # (level, logger_name, text)

    # ── Layout list ─────────────────────────────────────────────────────

    def _refresh_layouts(self):
        logger.info("refreshing layout list")
        for w in self._layout_inner.winfo_children():
            w.destroy()
        names = storage.list_layouts()
        config = storage.load_config()
        ar_name = config.get("auto_rollback", {}).get("layout_name", "")
        ar_enabled = config.get("auto_rollback", {}).get("enabled", False)

        if not names:
            tk.Label(self._layout_inner, text=t("no_layouts"), fg="gray").pack()
        else:
            for name in names:
                row = tk.Frame(self._layout_inner)
                row.pack(fill=tk.X, pady=1)
                radio_var = tk.IntVar(value=1 if name == ar_name else 0)
                tk.Radiobutton(row, variable=radio_var, value=1, state=tk.DISABLED).pack(side=tk.LEFT)
                tk.Label(row, text=name, width=50, anchor="w").pack(side=tk.LEFT)

                # 저장 시각
                saved_at = self._format_saved_at(name)
                tk.Label(row, text=saved_at, width=18, anchor="w",
                         fg="#666", font=("Consolas", 9)).pack(side=tk.LEFT)

                # Per-layout monitor match indicator
                match_text, match_color = self._get_match_indicator(name)
                tk.Label(row, text=match_text, fg=match_color, width=14, anchor="w").pack(side=tk.LEFT)

                # ── 가로 확장용 spacer (Task-17): 이름과 버튼 사이 빈 공간이 늘어나게 ──
                spacer = tk.Frame(row)
                spacer.pack(side=tk.LEFT, fill=tk.X, expand=True)

                tk.Button(row, text=t("preview_btn"), command=lambda n=name: self._on_preview(n)).pack(side=tk.LEFT, padx=2)
                tk.Button(row, text=t("restore_btn"), command=lambda n=name: self._on_restore(n)).pack(side=tk.LEFT, padx=2)
                tk.Button(row, text=t("settings_btn"), command=lambda n=name: self._on_settings(n)).pack(side=tk.LEFT, padx=2)
                tk.Button(row, text=t("delete_btn"), command=lambda n=name: self._on_delete(n)).pack(side=tk.LEFT, padx=2)

        # Update auto-rollback combo
        self._ar_combo["values"] = names
        if ar_name in names:
            self._ar_layout_var.set(ar_name)
        elif names:
            self._ar_layout_var.set(names[0])
        self._apply_ar_toggle_style(ar_enabled)

        mode = config.get("auto_rollback", {}).get("mode", "fast")
        self._ar_mode_var.set(mode)
        self._on_mode_change()

        delay = config.get("auto_rollback", {}).get("startup_delay_seconds", 10)
        self._delay_var.set(str(delay))

    # ── Monitor strip + polling ──────────────────────────────────────────

    def _poll_monitors(self):
        def _work():
            monitors = list_current_monitors()
            self.after(0, lambda: self._update_monitor_strip(monitors))

        threading.Thread(target=_work, daemon=True).start()
        self.after(1000, self._poll_monitors)

    def _update_monitor_strip(self, monitors: list[dict]):
        monitors_changed = monitors != self._current_monitors
        if monitors_changed:
            self._current_monitors = monitors
        if not monitors:
            self._monitor_strip_var.set("Monitors: unknown")
            return
        parts = []
        for m in monitors:
            x, y, w, h = m["rect"]
            label = f"#{m['index']}{'★' if m.get('primary') else ''} {w}x{h}"
            if m.get("scale", 1.0) != 1.0:
                label += f" @{m['scale']:.1f}x"
            parts.append(label)
        self._monitor_strip_var.set("Monitors: " + "  |  ".join(parts))
        if monitors_changed:
            self.after(0, self._refresh_layouts)

    def _format_saved_at(self, name: str) -> str:
        """layout의 created_at(ISO 8601)을 i18n 포맷('%y.%m.%d/%H:%M:%S')으로 변환.
        파싱 실패 또는 키 부재 시 빈 문자열."""
        try:
            layout = storage.load_layout(name)
            iso = layout.get("created_at")
            if not iso:
                return ""
            dt = datetime.fromisoformat(iso)
            return dt.strftime(t("saved_at_format"))
        except Exception:
            return ""

    def _get_match_indicator(self, name: str) -> tuple[str, str]:
        """Return (indicator_text, color) for a layout's monitor match state."""
        if not self._current_monitors:
            return ("", "gray")
        try:
            layout = storage.load_layout(name)
            saved_monitors = layout.get("monitors", [])
            if not saved_monitors:
                return ("", "gray")
            result = compare_monitors(saved_monitors, self._current_monitors)
            if result == MatchResult.MATCH:
                return ("✓match", "green")
            elif result == MatchResult.PRIMARY_ONLY:
                return (t("not_matched_label"), "orange")
            else:
                return ("⚠mismatch", "red")
        except Exception:
            return ("", "gray")

    # ── Button handlers ──────────────────────────────────────────────────

    def _on_save(self):
        logger.info("user clicked Save")
        def _work():
            try:
                windows = capture.list_current_windows()
                monitors = list_current_monitors()
                name = storage.next_layout_name()
                layout = {
                    "name": name,
                    "created_at": datetime.now().astimezone().isoformat(),
                    "monitors": monitors,
                    "windows": windows,
                }
                storage.save_layout(name, layout)
                # 가상 데스크톱 전체 PNG 스크린샷 (실패해도 저장 자체는 성공으로 간주)
                try:
                    capture.capture_virtual_screen(storage.screenshot_path(name))
                except Exception as e:
                    logger.warning("screenshot capture skipped: %s", e)
                self.after(0, lambda: self._status_var.set(t("layout_saved", name=name, count=len(windows))))
                self.after(0, self._refresh_layouts)
            except Exception as e:
                logger.error("save failed: %s", e)
        threading.Thread(target=_work, daemon=True).start()

    def _on_restore(self, name: str):
        logger.info("user clicked Restore for '%s'", name)

        # Check monitor match and prompt if warning state
        match_text, _ = self._get_match_indicator(name)
        if match_text in (t("not_matched_label"), "⚠mismatch"):
            msg = (
                f"Monitor configuration differs from when '{name}' was saved.\n"
                f"({match_text.lstrip('⚠')})\n\n"
                "Windows may be restored to unexpected positions.\nContinue?"
            )
            if not messagebox.askyesno("Monitor Mismatch", msg, parent=self):
                return

        def _work():
            try:
                layout = storage.load_layout(name)
                result = restore_mod.restore_layout(
                    layout,
                    monitors_current=self._current_monitors or None,
                    post_launch_settle_ms=5000,
                )
                self.after(0, lambda: self._status_var.set(
                    t("layout_restored", name=name, restored=result["restored"], total=result["total"])
                ))
            except Exception as e:
                logger.error("restore failed: %s", e)
        threading.Thread(target=_work, daemon=True).start()

    def _on_delete(self, name: str):
        logger.info("user clicked Delete for '%s'", name)
        def _work():
            storage.delete_layout(name)
            self.after(0, lambda: self._status_var.set(t("layout_deleted", name=name)))
            self.after(0, self._refresh_layouts)
        threading.Thread(target=_work, daemon=True).start()

    def _on_settings(self, name: str):
        new_name = simpledialog.askstring(t("rename_dialog_title"), t("rename_label"), initialvalue=name, parent=self)
        if new_name and new_name != name:
            def _work():
                try:
                    layout = storage.load_layout(name)
                    layout["name"] = new_name
                    storage.save_layout(new_name, layout)
                    # PNG 동반 이동 (있을 때만)
                    old_png = storage.screenshot_path(name)
                    new_png = storage.screenshot_path(new_name)
                    if old_png.exists():
                        try:
                            old_png.replace(new_png)
                        except OSError as e:
                            logger.warning("png rename failed: %s", e)
                    storage.delete_layout(name)
                    self.after(0, self._refresh_layouts)
                except Exception as e:
                    logger.error("rename failed: %s", e)
            threading.Thread(target=_work, daemon=True).start()

    def _on_ar_toggle(self):
        config = storage.load_config()
        ar = config.setdefault("auto_rollback", {})
        new_enabled = not ar.get("enabled", False)
        ar["layout_name"] = self._ar_layout_var.get()
        ar["mode"] = self._ar_mode_var.get()
        try:
            ar["startup_delay_seconds"] = int(self._delay_var.get())
        except ValueError:
            ar["startup_delay_seconds"] = 1

        # Resolve scheduler args for current execution mode (frozen vs dev).
        if getattr(sys, "frozen", False):
            script_path = ""
            python_exe = str(Path(sys.executable).with_name("WinLayoutSaverRollback.exe"))
        else:
            script_path = str(Path(__file__).parent.parent / "cli" / "rollback.py")
            python_exe = None

        if new_enabled:
            ok = scheduler.register(
                script_path=script_path,
                delay_seconds=ar.get("startup_delay_seconds", 10),
                python_exe=python_exe,
            )
            if not ok:
                logger.error("auto-rollback enable FAILED for '%s' — task not registered", ar["layout_name"])
                ar["enabled"] = False
                storage.save_config(config)
                self._apply_ar_toggle_style(False)
                messagebox.showerror(
                    t("app_title"),
                    t("register_failed_msg").format(log_dir=str(LOGS_DIR)),
                )
                return
            ar["enabled"] = True
            storage.save_config(config)
            self._apply_ar_toggle_style(True)
            logger.info("auto-rollback enabled for '%s'", ar["layout_name"])
        else:
            ok = scheduler.unregister()
            ar["enabled"] = False
            storage.save_config(config)
            self._apply_ar_toggle_style(False)
            logger.info("auto-rollback disabled for '%s'", ar["layout_name"])
            if not ok:
                messagebox.showwarning(
                    t("app_title"),
                    t("register_failed_msg").format(log_dir=str(LOGS_DIR)),
                )

    def _on_run_now(self):
        if not scheduler.task_exists():
            messagebox.showerror(t("app_title"), t("run_now_not_registered_msg"))
            return
        ok, msg = scheduler.run_now()
        if ok:
            messagebox.showinfo(t("app_title"), t("run_now_success_msg"))
        else:
            messagebox.showerror(t("app_title"), t("run_now_failed_msg").format(error=msg))

    def _migrate_existing_task(self):
        config = storage.load_config()
        ar = config.get("auto_rollback", {})
        if not ar.get("enabled", False):
            return
        if ar.get("_migrated_v14", False):
            return

        logger.info(t("migrate_task_log"))

        if getattr(sys, "frozen", False):
            rollback_exe = str(Path(sys.executable).with_name("WinLayoutSaverRollback.exe"))
            scheduler.unregister()
            ok = scheduler.register(
                script_path="",
                delay_seconds=ar.get("startup_delay_seconds", 10),
                python_exe=rollback_exe,
            )
        else:
            script_path = str(Path(__file__).parent.parent / "cli" / "rollback.py")
            scheduler.unregister()
            ok = scheduler.register(
                script_path=script_path,
                delay_seconds=ar.get("startup_delay_seconds", 10),
            )

        if ok:
            ar["_migrated_v14"] = True
            config["auto_rollback"] = ar
            storage.save_config(config)
            logger.info("scheduler: migration complete (v14)")
        else:
            logger.warning("scheduler: migration failed — will retry on next launch")
            try:
                self._status_var.set(t("migrate_failed_status"))
            except Exception:
                pass

    def _on_mode_change(self):
        """모드 Radio 버튼 클릭 시 설명 Label을 갱신한다."""
        mode = self._ar_mode_var.get()
        self._mode_desc_var.set(t("mode_fast_desc" if mode == "fast" else "mode_full_desc"))

    def _on_preview(self, name: str):
        """선택한 layout의 PNG 스크린샷을 Toplevel 창에 표시.
        파일이 없으면 messagebox로 안내."""
        png_path = storage.screenshot_path(name)
        if not png_path.exists():
            messagebox.showinfo(
                t("preview_window_title", name=name),
                t("screenshot_missing_msg"),
                parent=self,
            )
            return
        try:
            from PIL import Image, ImageTk
        except ImportError:
            messagebox.showinfo(
                t("preview_window_title", name=name),
                "Pillow not installed",
                parent=self,
            )
            return

        try:
            img = Image.open(str(png_path))
            max_w, max_h = 1280, 720
            w, h = img.size
            scale = min(max_w / w, max_h / h, 1.0)
            if scale < 1.0:
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            top = tk.Toplevel(self)
            top.title(t("preview_window_title", name=name))
            photo = ImageTk.PhotoImage(img, master=top)
            lbl = tk.Label(top, image=photo)
            lbl.image = photo
            lbl.pack()
            tk.Button(top, text="Close", command=top.destroy).pack(pady=4)
        except Exception as e:
            logger.error("preview failed for '%s': %s", name, e)
            messagebox.showinfo(
                t("preview_window_title", name=name),
                str(e),
                parent=self,
            )

    def _apply_ar_toggle_style(self, enabled: bool):
        """부팅 자동 복구 활성화 상태에 따라 토글 버튼 및 관련 컨트롤 잠금/해제."""
        widget_state = "disabled" if enabled else "normal"
        combo_state  = "disabled" if enabled else "readonly"
        self._ar_combo.config(state=combo_state)
        self._ar_mode_fast_rb.config(state=widget_state)
        self._ar_mode_full_rb.config(state=widget_state)
        self._delay_entry.config(state=widget_state)

        if enabled:
            self._ar_toggle_btn.config(
                text=t("enabled_status"),
                bg="#2E7D32",
                fg="white",
                activebackground="#388E3C",
                activeforeground="white",
            )
        else:
            self._ar_toggle_btn.config(
                text=t("enable_btn"),
                bg="SystemButtonFace",
                fg="SystemButtonText",
                activebackground="SystemButtonFace",
                activeforeground="SystemButtonText",
            )

    # ── Log panel ────────────────────────────────────────────────────────

    def _drain_log_queue(self):
        drained = 0
        while drained < 200:
            try:
                record = self._log_queue.get_nowait()
            except queue.Empty:
                break
            drained += 1
            levelname = record.levelname
            # Map WARNING → WARN for display
            display_level = "WARN" if levelname == "WARNING" else levelname
            logger_name = record.name
            ts = time.strftime("%H:%M:%S", time.localtime(record.created))
            ms = int(record.msecs)
            text = f"{ts}.{ms:03d} {display_level:<5} {logger_name:<12}: {record.getMessage()}\n"
            self._log_buffer.append((display_level, logger_name, text))
            # Trim buffer
            if len(self._log_buffer) > 1000:
                self._log_buffer = self._log_buffer[-1000:]
            self._append_log_line(display_level, logger_name, text)
        self.after(100, self._drain_log_queue)

    def _append_log_line(self, level: str, logger_name: str, text: str):
        from src.gui_helpers import should_show_log_entry
        level_on  = {k for k, v in self._log_levels.items() if v.get()}
        module_on = {k for k, v in self._module_filters.items() if v.get()}
        if not should_show_log_entry(level, logger_name, level_on, module_on):
            return
        at_end = self._log_text.yview()[1] >= 0.99
        self._log_text.config(state=tk.NORMAL)
        self._log_text.insert(tk.END, text, level)
        # Trim to 1000 lines
        line_count = int(self._log_text.index(tk.END).split(".")[0]) - 1
        if line_count > 1000:
            self._log_text.delete("1.0", f"{line_count - 1000}.0")
        self._log_text.config(state=tk.DISABLED)
        if at_end:
            self._log_text.see(tk.END)

    def _apply_log_filter(self):
        self._log_text.config(state=tk.NORMAL)
        self._log_text.delete("1.0", tk.END)
        self._log_text.config(state=tk.DISABLED)
        for level, logger_name, text in self._log_buffer:
            self._append_log_line(level, logger_name, text)

    def _clear_log(self):
        self._log_text.config(state=tk.NORMAL)
        self._log_text.delete("1.0", tk.END)
        self._log_text.config(state=tk.DISABLED)
        self._log_buffer.clear()

    def _copy_log(self):
        self.clipboard_clear()
        self.clipboard_append(self._log_text.get("1.0", tk.END))

    def _open_log_dir(self):
        os.startfile(str(LOGS_DIR))


def main():
    app = WinLayoutSaverApp()
    app.mainloop()
