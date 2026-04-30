"""Shared UI tab helper functions and startup runtime helpers."""

import os
import sys

import tkinter as tk
from tkinter import ttk

from ui.functions.ui_helpers import set_window_icon_from_logo


# ---------------------------------------------------------------------------
# Session Generation tab helpers
# ---------------------------------------------------------------------------


def session_generation_round_type_priority(type_pref):
    """Return stable priority so level rounds are generated before balanced rounds."""
    if isinstance(type_pref, dict):
        round_type = type_pref.get("type")
    else:
        round_type = type_pref
    round_type = round_type.lower() if isinstance(round_type, str) else None
    if round_type == "level":
        return 0
    if round_type == "balanced":
        return 1
    return 2


# ---------------------------------------------------------------------------
# Games Editor tab helpers
# ---------------------------------------------------------------------------


def games_editor_delta_to_bg(delta):
    """Return (bg_hex, text_suffix) for a happiness delta."""
    THRESHOLD = 0.05
    CAP = 5.0

    if abs(delta) < THRESHOLD:
        return "#FFFFFF", None

    t = min(abs(delta) / CAP, 1.0)

    def lerp_channel(lo, hi, t):
        return int(lo + (hi - lo) * t)

    if delta > 0:
        r = lerp_channel(255, 0, t)
        g = lerp_channel(255, 204, t)
        b = lerp_channel(255, 68, t)
        return f"#{r:02X}{g:02X}{b:02X}", f"[{delta:+.1f}]"

    r = lerp_channel(255, 255, t)
    g = lerp_channel(255, 51, t)
    b = lerp_channel(255, 34, t)
    return f"#{r:02X}{g:02X}{b:02X}", f"[{delta:+.1f}]"


# ---------------------------------------------------------------------------
# Session Games tab helpers
# ---------------------------------------------------------------------------


def session_games_out_of_place_count(round_order):
    """Count rounds not in their original display position."""
    return sum(1 for i, value in enumerate(round_order) if i != value)


# ---------------------------------------------------------------------------
# Plots tab helpers
# ---------------------------------------------------------------------------


def plots_find_png_files(plots_dir):
    """Return sorted PNG files in a plots directory."""
    import glob

    return sorted(glob.glob(os.path.join(plots_dir, "*.png")))


# ---------------------------------------------------------------------------
# Startup runtime UI helpers
# ---------------------------------------------------------------------------


def _show_loading_window(root):
    """Display a splash/loading window while the app initialises."""
    splash = tk.Toplevel(root)
    splash.overrideredirect(True)
    splash.configure(bg="#2E2E2E")

    sw = splash.winfo_screenwidth()
    sh = splash.winfo_screenheight()
    w, h = 420, 220
    splash.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    set_window_icon_from_logo(splash)

    tk.Label(
        splash,
        text="⚡  ROUNDNET MATCHMAKING  ⚡",
        font=("Arial", 16, "bold"),
        fg="#FED403",
        bg="#2E2E2E",
    ).pack(pady=(35, 8))

    tk.Label(
        splash,
        text="Loading data…",
        font=("Arial", 12),
        fg="#FFFFFF",
        bg="#2E2E2E",
    ).pack(pady=4)

    progress_var = tk.DoubleVar()
    bar = ttk.Progressbar(
        splash,
        variable=progress_var,
        mode="indeterminate",
        length=320,
    )
    bar.pack(pady=18)
    bar.start(12)

    root.update()
    return splash


def _ensure_windows_tcl_env():
    """Set TCL/TK runtime paths on Windows when Python cannot auto-resolve them."""
    if os.name != "nt":
        return

    tcl_env = os.environ.get("TCL_LIBRARY", "").strip()
    tk_env = os.environ.get("TK_LIBRARY", "").strip()
    if tcl_env and tk_env:
        return

    for base_prefix in (getattr(sys, "base_prefix", ""), getattr(sys, "prefix", "")):
        if not base_prefix:
            continue

        tcl_root = os.path.join(base_prefix, "tcl")
        if not os.path.isdir(tcl_root):
            continue

        try:
            children = os.listdir(tcl_root)
        except OSError:
            continue

        tcl_dirs = sorted(
            [
                name
                for name in children
                if name.lower().startswith("tcl")
                and os.path.isdir(os.path.join(tcl_root, name))
            ],
            reverse=True,
        )
        tk_dirs = sorted(
            [
                name
                for name in children
                if name.lower().startswith("tk")
                and os.path.isdir(os.path.join(tcl_root, name))
            ],
            reverse=True,
        )

        if not tcl_dirs or not tk_dirs:
            continue

        if not tcl_env:
            os.environ["TCL_LIBRARY"] = os.path.join(tcl_root, tcl_dirs[0])
        if not tk_env:
            os.environ["TK_LIBRARY"] = os.path.join(tcl_root, tk_dirs[0])
        return
