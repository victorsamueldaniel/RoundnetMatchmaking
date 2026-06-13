"""ui_helpers.py — General-purpose helpers used by player_selection_ui.py.

Contains: current_dir detection, load_module, set_window_icon_from_logo,
          ConsoleRedirector, ProgressDialog.
"""

import importlib
import importlib.util
import io
import os
import sys
from pathlib import Path

import tkinter as tk
from tkinter import ttk

# ---------------------------------------------------------------------------
# Application base directory (works for plain script, PyInstaller exe, REPL)
# ---------------------------------------------------------------------------


def _is_project_root(candidate):
    candidate_path = Path(candidate)
    return (
        candidate_path.is_dir()
        and (candidate_path / "pyproject.toml").is_file()
        and (candidate_path / "core" / "main.py").is_file()
        and (candidate_path / "core" / "models.py").is_file()
    )


def _resolve_current_dir(
    *,
    is_frozen=None,
    executable=None,
    file_path=None,
    cwd=None,
    env=None,
):
    env = os.environ if env is None else env
    is_frozen = getattr(sys, "frozen", False) if is_frozen is None else is_frozen
    executable = sys.executable if executable is None else executable
    file_path = globals().get("__file__") if file_path is None else file_path
    cwd = os.getcwd() if cwd is None else cwd

    override = env.get("ROUNDNET_MATCHMAKING_SOURCE_ROOT")
    if override and _is_project_root(override):
        return str(Path(override).resolve()), "env_override"

    if is_frozen:
        executable_dir = Path(executable).resolve().parent
        for candidate in executable_dir.parents:
            if _is_project_root(candidate):
                return str(candidate), "workspace_source"
        return str(executable_dir), "frozen_bundle"

    if file_path:
        # ui_helpers.py lives in ui/functions/; project root is two levels up
        return str(Path(file_path).resolve().parents[2]), "source_tree"

    return str(Path(cwd).resolve()), "cwd"


current_dir, current_dir_source = _resolve_current_dir()

if current_dir not in sys.path:
    sys.path.insert(0, current_dir)


# ---------------------------------------------------------------------------
# Module loading
# ---------------------------------------------------------------------------


def load_module(module_name, file_name, force_reload=False):
    """Load a module by name, handling both script and frozen contexts."""
    module_path = os.path.join(current_dir, file_name)

    if not os.path.exists(module_path):
        raise ImportError(f"Cannot find {file_name} in {current_dir}")

    if module_name in sys.modules and force_reload:
        module = sys.modules[module_name]
        importlib.reload(module)
        return module

    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {module_path}")

    print(f"[module-load] {module_name} -> {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def set_window_icon_from_logo(root):
    """Set Tk window/taskbar icon from logo.png when available."""
    try:
        logo_path = os.path.join(current_dir, "ui", "logo.png")
        if os.path.exists(logo_path):
            icon_photo = tk.PhotoImage(file=logo_path)
            root.iconphoto(True, icon_photo)
            return icon_photo
    except Exception as e:
        print(f"Could not set app icon from logo.png: {e}")
    return None


# ---------------------------------------------------------------------------
# Console output redirect
# ---------------------------------------------------------------------------

# Set by bug_reporter.init_log_file() before the first ConsoleRedirector is
# created.  ConsoleRedirector will tee all stdout output to this file.
_log_file_path: str | None = None


class ConsoleRedirector(io.StringIO):
    """Redirect stdout to a tkinter Text widget, and tee to a log file."""

    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self._log_fh = None
        if _log_file_path:
            try:
                self._log_fh = open(  # noqa: SIM115
                    _log_file_path, "a", encoding="utf-8", buffering=1
                )
            except Exception:
                pass

    def write(self, string):
        if string:  # Write all non-empty strings, including newlines
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.insert(tk.END, string)
            self.text_widget.see(tk.END)
            self.text_widget.config(state=tk.DISABLED)
            self.text_widget.update()
            if self._log_fh is not None:
                try:
                    self._log_fh.write(string)
                except Exception:
                    pass
        return len(string)

    def flush(self):
        if self._log_fh is not None:
            try:
                self._log_fh.flush()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Progress dialog
# ---------------------------------------------------------------------------


class ProgressDialog:
    """Progress dialog shown while generating sessions."""

    def __init__(self, parent, first_seed, last_seed, colors):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Generating Session")
        screen_w = parent.winfo_screenwidth()
        screen_h = parent.winfo_screenheight()
        dlg_w = max(300, int(screen_w * 0.35))
        dlg_h = max(160, int(screen_h * 0.18))
        self.dialog.geometry(f"{dlg_w}x{dlg_h}")
        self.dialog.resizable(False, False)
        self.colors = colors
        self.first_seed = first_seed
        self.last_seed = last_seed
        self.current_seed = first_seed

        self.dialog.configure(bg=colors["bg_dark"])
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.dialog.update_idletasks()
        x = (
            parent.winfo_x()
            + (parent.winfo_width() // 2)
            - (self.dialog.winfo_width() // 2)
        )
        y = (
            parent.winfo_y()
            + (parent.winfo_height() // 2)
            - (self.dialog.winfo_height() // 2)
        )
        self.dialog.geometry(f"+{x}+{y}")

        title_font_size = max(12, int(dlg_h / 12))
        prog_font_size = max(10, int(dlg_h / 18))

        tk.Label(
            self.dialog,
            text="⚡ Generating Session ⚡",
            font=("Arial", title_font_size, "bold"),
            fg=colors["accent_yellow"],
            bg=colors["bg_dark"],
        ).pack(pady=(20, 10))

        self.progress_label = tk.Label(
            self.dialog,
            text=f"Testing seed {first_seed} of {last_seed}...",
            font=("Arial", prog_font_size),
            fg=colors["text_light"],
            bg=colors["bg_dark"],
        )
        self.progress_label.pack(pady=10)

        self.progress_var = tk.DoubleVar(master=self.dialog)
        pbar_len = int(dlg_w * 0.7)
        self.progress_bar = ttk.Progressbar(
            self.dialog,
            variable=self.progress_var,
            maximum=last_seed - first_seed + 1,
            length=pbar_len,
            mode="determinate",
        )
        self.progress_bar.pack(pady=10)

        self.percent_label = tk.Label(
            self.dialog,
            text="0%",
            font=("Arial", max(9, int(prog_font_size * 0.9)), "bold"),
            fg=colors["accent_yellow"],
            bg=colors["bg_dark"],
        )
        self.percent_label.pack(pady=5)

    def update_progress(self, seed):
        self.current_seed = seed
        progress = seed - self.first_seed + 1
        total = self.last_seed - self.first_seed + 1
        percentage = int((progress / total) * 100)
        self.progress_var.set(progress)
        self.progress_label.config(text=f"Testing seed {seed} of {self.last_seed}...")
        self.percent_label.config(text=f"{percentage}%")
        self.dialog.update()

    def close(self):
        self.dialog.grab_release()
        self.dialog.destroy()
