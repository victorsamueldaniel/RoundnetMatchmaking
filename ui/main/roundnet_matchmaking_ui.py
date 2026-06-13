# %%
"""Main UI orchestrator for Roundnet Matchmaking."""

import sys
import os
import threading
import traceback as _traceback

import tkinter as tk
from tkinter import messagebox

from ui.functions.ui_helpers import current_dir, current_dir_source, load_module
from ui.functions.bug_reporter import init_log_file, collect_bug_report
from ui.functions.setup_wizard import (
    _XLSX_CONFIG_PATH,
    _run_setup_wizard,
)
from ui.functions.tab_functions import (
    _show_loading_window,
    _ensure_windows_tcl_env,
)
from ui.tabs.session_generation_tab import SessionGenerationTabMixin
from ui.tabs.games_editor_tab import GamesEditorTabMixin
from ui.tabs.session_games_tab import SessionGamesTabMixin
from ui.tabs.contact import ContactTabMixin
from ui.tabs.plots_tabs.plots_tabs_orchestrator import PlotsTabMixin
import ui.tabs.session_generation_tab as session_generation_tab
import ui.tabs.games_editor_tab as games_editor_tab
import ui.tabs.session_games_tab as session_games_tab

main_module = None
ftf_module = None


def _make_crash_handler(root, app):
    """Return a sys.excepthook that collects a bug report then re-raises."""

    def _handler(exc_type, exc_value, exc_tb):
        if exc_type is KeyboardInterrupt:
            return
        tb_str = "".join(_traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            pkg_dir = collect_bug_report(app, traceback_str=tb_str)
            messagebox.showerror(
                "Unexpected Error",
                f"The application encountered an unexpected error.\n\n"
                f"{exc_type.__name__}: {exc_value}\n\n"
                f"A bug report has been saved to:\n{pkg_dir}\n\n"
                f"Please attach this folder when reporting the issue on GitHub.",
            )
        except Exception:
            pass
        # Propagate to the default handler so the traceback still prints.
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    return _handler


class PlayerSelectionUI(
    SessionGenerationTabMixin,
    GamesEditorTabMixin,
    SessionGamesTabMixin,
    ContactTabMixin,
    PlotsTabMixin,
):
    """Composed UI class built from tab mixins."""


class _UnsavedPrefsDialog:
    """Styled modal dialog with per-parameter Save / Discard toggles."""

    _LABELS: dict  # populated from preferences_manager at first use

    def __init__(self, parent, diff_keys, colors):
        self.colors = colors
        from ui.functions.preferences_manager import UI_DEFAULT_NOT_SAVED_LABELS

        self._LABELS = UI_DEFAULT_NOT_SAVED_LABELS
        self.choices = {k: tk.StringVar(value="discard") for k in diff_keys}
        self._confirmed = False

        dlg = tk.Toplevel(parent)
        self.dlg = dlg
        dlg.title("Unsaved settings")
        dlg.configure(bg=colors["bg_dark"])
        dlg.resizable(False, False)
        dlg.transient(parent)
        dlg.grab_set()

        # ── Title ──────────────────────────────────────────────────────
        tk.Label(
            dlg,
            text="Some settings were not saved",
            font=("Arial", 14, "bold"),
            fg=colors["accent_yellow"],
            bg=colors["bg_dark"],
        ).pack(pady=(20, 4), padx=28)

        tk.Label(
            dlg,
            text="Choose what to do for each setting:",
            font=("Arial", 11),
            fg=colors["text_light"],
            bg=colors["bg_dark"],
        ).pack(pady=(0, 14), padx=28)

        # ── One row per changed parameter ──────────────────────────────
        for key in diff_keys:
            self._add_row(dlg, key, self._LABELS.get(key, key))

        # ── Separator ──────────────────────────────────────────────────
        tk.Frame(dlg, bg=colors["accent_yellow"], height=1).pack(
            fill=tk.X, padx=20, pady=(18, 0)
        )

        # ── Bottom buttons ─────────────────────────────────────────────
        btn_frame = tk.Frame(dlg, bg=colors["bg_dark"])
        btn_frame.pack(pady=14)

        tk.Button(
            btn_frame,
            text="Save all",
            font=("Arial", 11, "bold"),
            bg=colors["accent_red"],
            fg=colors["text_light"],
            activebackground="#5a0100",
            activeforeground=colors["text_light"],
            relief=tk.FLAT,
            padx=18,
            pady=6,
            cursor="hand2",
            command=self._on_save_all,
        ).pack(side=tk.LEFT, padx=8)

        tk.Button(
            btn_frame,
            text="Confirm",
            font=("Arial", 11, "bold"),
            bg=colors["accent_yellow"],
            fg=colors["text_dark"],
            activebackground="#d8b500",
            activeforeground=colors["text_dark"],
            relief=tk.FLAT,
            padx=18,
            pady=6,
            cursor="hand2",
            command=self._on_confirm,
        ).pack(side=tk.LEFT, padx=8)

        tk.Button(
            btn_frame,
            text="Discard all",
            font=("Arial", 11),
            bg="#555555",
            fg=colors["text_light"],
            activebackground="#444444",
            activeforeground=colors["text_light"],
            relief=tk.FLAT,
            padx=18,
            pady=6,
            cursor="hand2",
            command=self._on_discard_all,
        ).pack(side=tk.LEFT, padx=8)

        # ── Centre on parent ───────────────────────────────────────────
        dlg.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - dlg.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{x}+{y}")

        parent.wait_window(dlg)

    def _add_row(self, parent, key, label_text):
        c = self.colors
        row = tk.Frame(parent, bg=c["bg_dark"])
        row.pack(fill=tk.X, padx=28, pady=5)

        tk.Label(
            row,
            text=label_text,
            font=("Arial", 11),
            fg=c["text_light"],
            bg=c["bg_dark"],
            width=22,
            anchor=tk.W,
        ).pack(side=tk.LEFT)

        var = self.choices[key]

        def _refresh(btns, v=var):
            val = v.get()
            btns[0].config(
                bg=c["accent_red"] if val == "save" else "#3a3a3a",
                relief=tk.SUNKEN if val == "save" else tk.FLAT,
            )
            btns[1].config(
                bg="#666666" if val == "discard" else "#3a3a3a",
                relief=tk.SUNKEN if val == "discard" else tk.FLAT,
            )

        btn_save = tk.Button(
            row,
            text="Save",
            font=("Arial", 10, "bold"),
            bg="#3a3a3a",
            fg=c["text_light"],
            activebackground="#5a0100",
            activeforeground=c["text_light"],
            relief=tk.FLAT,
            padx=12,
            pady=3,
            cursor="hand2",
        )
        btn_discard = tk.Button(
            row,
            text="Discard",
            font=("Arial", 10),
            bg="#666666",
            fg=c["text_light"],
            activebackground="#333333",
            activeforeground=c["text_light"],
            relief=tk.SUNKEN,
            padx=12,
            pady=3,
            cursor="hand2",
        )
        btns = [btn_save, btn_discard]
        btn_save.config(command=lambda: (var.set("save"), _refresh(btns)))
        btn_discard.config(command=lambda: (var.set("discard"), _refresh(btns)))

        btn_save.pack(side=tk.LEFT, padx=(8, 2))
        btn_discard.pack(side=tk.LEFT, padx=(2, 0))

    def _on_confirm(self):
        self._confirmed = True
        self.dlg.destroy()

    def _on_discard_all(self):
        for var in self.choices.values():
            var.set("discard")
        self._confirmed = True
        self.dlg.destroy()

    def _on_save_all(self):
        for var in self.choices.values():
            var.set("save")
        self._confirmed = True
        self.dlg.destroy()

    def get_keys_to_save(self):
        """Return only the keys the user chose to save."""
        if not self._confirmed:
            return []
        return [k for k, v in self.choices.items() if v.get() == "save"]


def _ask_save_extra_params(root, colors, date_str: str) -> bool:
    """Styled modal: ask whether to archive extra_parameters_temp.json as a dated file.

    Returns True if the user chose Save, False otherwise.
    """
    import datetime  # noqa: F401 — date_str already computed by caller

    result = [False]

    dlg = tk.Toplevel(root)
    dlg.title("Extra parameters modified")
    dlg.configure(bg=colors["bg_dark"])
    dlg.resizable(False, False)
    dlg.transient(root)
    dlg.grab_set()

    tk.Label(
        dlg,
        text="Extra parameters were modified",
        font=("Arial", 14, "bold"),
        fg=colors["accent_yellow"],
        bg=colors["bg_dark"],
    ).pack(pady=(20, 4), padx=28)

    tk.Label(
        dlg,
        text=(
            "The generation knobs in extra_parameters_temp.json\n"
            "differ from extra_parameters.json.\n\n"
            f"Save a copy as extra_parameters_temp_{date_str}.json?"
        ),
        font=("Arial", 11),
        fg=colors["text_light"],
        bg=colors["bg_dark"],
        justify=tk.CENTER,
    ).pack(pady=(0, 14), padx=28)

    tk.Frame(dlg, bg=colors["accent_yellow"], height=1).pack(
        fill=tk.X, padx=20, pady=(8, 0)
    )

    btn_frame = tk.Frame(dlg, bg=colors["bg_dark"])
    btn_frame.pack(pady=14)

    def _save():
        result[0] = True
        dlg.destroy()

    tk.Button(
        btn_frame,
        text="Save",
        font=("Arial", 11, "bold"),
        bg=colors["accent_red"],
        fg=colors["text_light"],
        activebackground="#5a0100",
        activeforeground=colors["text_light"],
        relief=tk.FLAT,
        padx=18,
        pady=6,
        cursor="hand2",
        command=_save,
    ).pack(side=tk.LEFT, padx=8)

    tk.Button(
        btn_frame,
        text="Discard",
        font=("Arial", 11),
        bg="#555555",
        fg=colors["text_light"],
        activebackground="#444444",
        activeforeground=colors["text_light"],
        relief=tk.FLAT,
        padx=18,
        pady=6,
        cursor="hand2",
        command=dlg.destroy,
    ).pack(side=tk.LEFT, padx=8)

    dlg.update_idletasks()
    x = root.winfo_x() + (root.winfo_width() - dlg.winfo_width()) // 2
    y = root.winfo_y() + (root.winfo_height() - dlg.winfo_height()) // 2
    dlg.geometry(f"+{x}+{y}")

    root.wait_window(dlg)
    return result[0]


def _on_app_close(root, app):
    """Show per-parameter save dialogs, clean up temp files, then close."""
    import datetime

    from ui.functions.preferences_manager import (
        cleanup_temp_files,
        update_ui_temp,
    )

    _default_colors = {
        "bg_dark": "#2E2E2E",
        "accent_yellow": "#FED403",
        "accent_red": "#7F0301",
        "text_light": "#FFFFFF",
        "text_dark": "#1A1A1A",
    }
    colors = getattr(app, "colors", _default_colors)

    # Flush current live widget state to temp so the comparison below is authoritative.
    try:
        update_ui_temp(app._collect_ui_all_tracked())
    except Exception:
        pass

    # ── UI-accessible not-saved keys (temp vs stable) ───────────────────
    try:
        from ui.functions.preferences_manager import (
            get_not_saved_diff_from_temp,
            save_ui_not_saved,
        )

        diff = get_not_saved_diff_from_temp()
        if diff:
            dialog = _UnsavedPrefsDialog(root, list(diff.keys()), colors)
            keys_to_save = dialog.get_keys_to_save()
            if keys_to_save:
                save_ui_not_saved({k: diff[k] for k in keys_to_save})
    except Exception:
        pass

    # ── Extra parameters archive (temp vs stable) ───────────────────────
    try:
        from ui.functions.preferences_manager import (
            extra_temp_differs_from_stable,
            save_extra_temp_as_dated,
        )

        if extra_temp_differs_from_stable():
            date_str = datetime.datetime.now().strftime("%d_%m_%Y")
            if _ask_save_extra_params(root, colors, date_str):
                saved_path = save_extra_temp_as_dated(date_str)
                print(f"[prefs] Extra parameters archived: {saved_path}")
    except Exception:
        pass

    try:
        cleanup_temp_files()
    except Exception:
        pass
    root.destroy()


def main():
    """Main function to run the UI."""
    global main_module, ftf_module

    init_log_file()

    _ensure_windows_tcl_env()
    print(f"[startup] runtime root ({current_dir_source}): {current_dir}")
    root = tk.Tk()
    root.withdraw()

    if not os.path.exists(_XLSX_CONFIG_PATH):
        if not _run_setup_wizard(root):
            root.destroy()
            return

    splash = _show_loading_window(root)
    root.update()

    try:
        for _key in list(sys.modules.keys()):
            if "data_loader" in _key or _key in ("main", "core", "core.main"):
                del sys.modules[_key]

        main_module = load_module("main", "core/main.py", force_reload=True)
        ftf_module = load_module(
            "fine_tuning_functions", "core/fine_tuning_functions.py"
        )
        print(
            f"[startup] main module file: {getattr(main_module, '__file__', 'unknown')}"
        )
        core_models_module = sys.modules.get("core.models")
        if core_models_module is not None:
            print(
                f"[startup] core.models file: {getattr(core_models_module, '__file__', 'unknown')}"
            )

        # Share runtime-loaded core main module with tab mixins.
        session_generation_tab.main_module = main_module
        games_editor_tab.main_module = main_module
        session_games_tab.main_module = main_module

    except Exception as e:
        splash.destroy()
        root.deiconify()
        messagebox.showerror(
            "Import Error",
            f"Failed to import required modules:\n\n{str(e)}\n\n"
            f"Please ensure core/main.py and core/fine_tuning_functions.py exist.\n"
            f"Current directory: {current_dir}",
        )
        sys.exit(1)

    if getattr(main_module, "main_df", None) is None:
        splash.destroy()
        root.deiconify()
        messagebox.showerror(
            "Data Load Error",
            "Could not load player data from the Excel files.\n\n"
            "Please verify the files in the xlsx/ folder are valid,\n"
            "then delete xlsx_config.json and restart to re-run setup.",
        )
        sys.exit(1)

    app = PlayerSelectionUI(root)
    root.protocol("WM_DELETE_WINDOW", lambda: _on_app_close(root, app))

    # Install global crash hooks so unhandled exceptions auto-collect a report.
    _handler = _make_crash_handler(root, app)
    sys.excepthook = _handler
    threading.excepthook = lambda args: _handler(
        args.exc_type, args.exc_value, args.exc_traceback
    )

    splash.destroy()
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()

# %%
