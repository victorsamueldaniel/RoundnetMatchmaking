"""ui_helpers.py — General-purpose helpers used by player_selection_ui.py.

Contains: current_dir detection, load_module, set_window_icon_from_logo,
          ConsoleRedirector, ProgressDialog.
"""

import importlib
import importlib.util
import io
import os
import sys

import tkinter as tk
from tkinter import ttk

# ---------------------------------------------------------------------------
# Application base directory (works for plain script, PyInstaller exe, REPL)
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    current_dir = os.path.dirname(sys.executable)
elif "__file__" in globals():
    # ui_helpers.py lives in ui/functions/; project root is two levels up
    current_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
else:
    current_dir = os.getcwd()

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


class ConsoleRedirector(io.StringIO):
    """Redirect stdout to a tkinter Text widget."""

    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def write(self, string):
        if string:  # Write all non-empty strings, including newlines
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.insert(tk.END, string)
            self.text_widget.see(tk.END)
            self.text_widget.config(state=tk.DISABLED)
            self.text_widget.update()
        return len(string)

    def flush(self):
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
