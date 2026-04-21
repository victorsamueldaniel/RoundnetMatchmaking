# %%
import sys
import os

# Ensure project root is on sys.path so `ui.ui_helpers` and `core.*` resolve
# when running as a plain script (not needed in the frozen EXE).
if not getattr(sys, "frozen", False):
    # player_selection_ui.py lives in ui/; project root is one level up
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import importlib
import importlib.util
import ctypes
from ctypes import wintypes
from PIL import Image, ImageTk
import threading
import io
import json
import shutil
import tkinter.font as tkfont
from ui.ui_helpers import (
    current_dir,
    load_module,
    set_window_icon_from_logo,
    ConsoleRedirector,
    ProgressDialog,
)


# Modules are loaded lazily inside main() after the splash window is shown.
main_module = None
ftf_module = None

# ---------------------------------------------------------------------------
# First-run xlsx setup wizard
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    _xlsx_dir = os.path.join(os.path.dirname(sys.executable), "xlsx")
else:
    _xlsx_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "xlsx"
    )
_XLSX_CONFIG_PATH = os.path.join(_xlsx_dir, "xlsx_config.json")

# Import validation helper from core (available in both script and frozen contexts).
try:
    from core.data_loader import validate_xlsx
except ImportError:
    from data_loader import validate_xlsx  # type: ignore

import pandas as pd

_SPECTRUM_TERMS = {
    "Prey": "Enjoys losing and facing much stronger opponents —\nfinds value in difficult, one-sided challenges.",
    "Equilibrist": "Prefers balanced games where both teams\nare evenly matched in skill.",
    "Challenger": "Likes playing against opponents slightly above\ntheir own level to grow and improve.",
    "Chill": "Just here for fun — prefers relaxed games\nwith no pressure or intensity.",
    "Hunter": "Enjoys dominating weaker opponents\nand winning convincingly.",
    "Classist": "Prefers playing with others of exactly\nthe same skill level.",
}

_PLAYERS_FILE_HELP = (
    "Required columns:\n"
    "  • Name  (or 'Prénom')\n"
    "  • Surname  (or 'Nom')\n"
    "  • Gender  → 'Male' or 'Female' ('Masculin' or 'Féminin')\n"
    "  • Level  (numeric, e.g. 1.0 – 5.0)\n"
    "\n"
    "Optional spectrum columns (scores 0–5, blank → 5):\n"
    "  • Prey, Equilibrist, Challenger, Chill, Hunter, Classist\n"
    "\n"
    "Players with missing Gender or Level will be asked during setup."
)

# ---- kept for backward-compat when the wizard block below is read ----
_FILE_ROLES = []  # no longer used — single-file wizard replaces this


def _ask_missing_values(
    root,
    df,
    xlsx_path: str,
    BG: str,
    BG_SECT: str,
    BURG: str,
    YELLOW: str,
    WHITE: str,
    GRAY: str,
):
    """Show a modal dialog for any players with NaN Gender or NaN Level.
    Patches df in-place and writes changes back to xlsx_path."""

    missing_gender = [
        idx
        for idx in df.index
        if pd.isna(df.loc[idx, "Gender"]) or str(df.loc[idx, "Gender"]).strip() == ""
    ]
    missing_level = [idx for idx in df.index if pd.isna(df.loc[idx, "Level"])]

    if not missing_gender and not missing_level:
        return

    dlg = tk.Toplevel(root)
    dlg.title("Complete missing player data")
    dlg.configure(bg=BG)
    dlg.resizable(False, True)
    dlg.grab_set()
    DW = 640
    dlg.update_idletasks()
    sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
    dlg.geometry(f"{DW}x640+{(sw - DW) // 2}+{(sh - 640) // 2}")

    hdr = tk.Frame(dlg, bg=BURG)
    hdr.pack(fill=tk.X)
    tk.Label(
        hdr,
        text="⚠  Complete missing player data",
        font=("Arial", 12, "bold"),
        fg=WHITE,
        bg=BURG,
        padx=14,
        pady=8,
    ).pack(anchor=tk.W)

    tk.Label(
        dlg,
        text="Some players have missing Gender or Level. Please fill them in:",
        font=("Arial", 9),
        fg=GRAY,
        bg=BG,
        wraplength=530,
        justify=tk.LEFT,
        padx=14,
    ).pack(anchor=tk.W, pady=(6, 2))

    canvas = tk.Canvas(dlg, bg=BG, highlightthickness=0)
    scrollbar = ttk.Scrollbar(dlg, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0), pady=6)

    inner = tk.Frame(canvas, bg=BG)
    cw = canvas.create_window((0, 0), window=inner, anchor=tk.NW)

    def _on_inner_configure(e):
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfig(cw, width=canvas.winfo_width())

    inner.bind("<Configure>", _on_inner_configure)
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(cw, width=e.width))

    gender_vars: dict = {}
    level_vars: dict = {}

    all_players = list(dict.fromkeys(missing_gender + missing_level))
    for idx in all_players:
        frame = tk.Frame(inner, bg=BG_SECT, bd=1, relief=tk.SOLID)
        frame.pack(fill=tk.X, pady=3, padx=4)
        tk.Label(
            frame,
            text=idx,
            font=("Arial", 10, "bold"),
            fg=YELLOW,
            bg=BG_SECT,
            padx=10,
            pady=4,
        ).pack(anchor=tk.W)
        row = tk.Frame(frame, bg=BG_SECT)
        row.pack(fill=tk.X, padx=10, pady=(0, 6))

        if idx in missing_gender:
            tk.Label(
                row,
                text="Gender:",
                font=("Arial", 9),
                fg=GRAY,
                bg=BG_SECT,
                width=8,
                anchor=tk.W,
            ).pack(side=tk.LEFT)
            gv = tk.StringVar(value="Female")
            gender_vars[idx] = gv
            for label, val in [("Male", "Male"), ("Female", "Female")]:
                tk.Radiobutton(
                    row,
                    text=label,
                    variable=gv,
                    value=val,
                    font=("Arial", 9),
                    fg=WHITE,
                    bg=BG_SECT,
                    selectcolor=BG_SECT,
                    activebackground=BG_SECT,
                    activeforeground=WHITE,
                ).pack(side=tk.LEFT, padx=(0, 8))

        if idx in missing_level:
            tk.Label(
                row,
                text="Level:",
                font=("Arial", 9),
                fg=GRAY,
                bg=BG_SECT,
                width=6,
                anchor=tk.W,
            ).pack(side=tk.LEFT, padx=(12, 0))
            lv = tk.StringVar(value="")
            level_vars[idx] = lv
            tk.Entry(
                row,
                textvariable=lv,
                font=("Arial", 9),
                width=6,
                bg="#444444",
                fg=WHITE,
                insertbackground=WHITE,
            ).pack(side=tk.LEFT)
            tk.Label(
                row, text="(1.0 – 5.0)", font=("Arial", 8), fg=GRAY, bg=BG_SECT
            ).pack(side=tk.LEFT, padx=4)

    footer = tk.Frame(dlg, bg=BG)
    footer.pack(fill=tk.X, padx=14, pady=10)
    btn_row = tk.Frame(footer, bg=BG)
    btn_row.pack(fill=tk.X)
    err_lbl = tk.Label(
        btn_row,
        text="",
        font=("Arial", 9),
        fg="#FF6B6B",
        bg=BG,
        wraplength=400,
        justify=tk.LEFT,
    )
    err_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _on_ok():
        for idx, lv in level_vars.items():
            val = lv.get().strip()
            try:
                fval = float(val)
                if not (0.5 <= fval <= 6.0):
                    raise ValueError
            except ValueError:
                err_lbl.config(
                    text=f"Invalid level for {idx}: enter a number between 0.5 and 6.0"
                )
                return
        for idx, gv in gender_vars.items():
            df.at[idx, "Gender"] = gv.get()
        for idx, lv in level_vars.items():
            fval = float(lv.get().strip())
            df.at[idx, "Level"] = fval
            df.at[idx, "Category"] = fval
        # Write changes back to xlsx
        try:
            _save_df_to_xlsx(df, xlsx_path)
        except Exception as exc:
            err_lbl.config(text=f"Could not save: {exc}")
            return
        dlg.destroy()

    tk.Button(
        btn_row,
        text="Save & Continue →",
        font=("Arial", 11, "bold"),
        bg=YELLOW,
        fg="#000000",
        relief=tk.RAISED,
        cursor="hand2",
        padx=16,
        pady=6,
        command=_on_ok,
    ).pack(side=tk.RIGHT)
    dlg.protocol("WM_DELETE_WINDOW", _on_ok)
    root.wait_window(dlg)


def _save_df_to_xlsx(df: pd.DataFrame, path: str) -> None:
    """Write key player columns back to xlsx (index = NameSurname)."""
    save_cols = [
        "Name",
        "Surname",
        "Gender",
        "Level",
        "Prey",
        "Equilibrist",
        "Challenger",
        "Chill",
        "Hunter",
        "Classist",
    ]
    present = [c for c in save_cols if c in df.columns]
    # Reset index so NameSurname becomes a column, then drop it (it's derived)
    out = (
        df.reset_index(drop=True)[present]
        if "NameSurname" not in df.columns
        else df.reset_index()[["NameSurname"] + present]
    )
    out.to_excel(path, index=False)


def _run_setup_wizard(root):
    """
    Modal first-run wizard: browse for the single players xlsx, copy it
    into xlsx/ and write xlsx_config.json.
    Returns True on confirm, False on cancel.
    """
    result = {"ok": False}
    selected = {"players": None}

    BG = "#2E2E2E"
    BG_SECT = "#3A3A3A"
    BURG = "#7F0301"
    YELLOW = "#FED403"
    WHITE = "#FFFFFF"
    GRAY = "#BBBBBB"

    win = tk.Toplevel(root)
    win.title("First-time Setup — Import your players file")
    win.configure(bg=BG)
    win.resizable(False, False)
    win.grab_set()

    W, H = 680, 640
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")

    # --- Header ---
    hdr = tk.Frame(win, bg=BG)
    hdr.pack(fill=tk.X, padx=20, pady=(20, 6))
    tk.Label(
        hdr, text="⚡  First-time Setup", font=("Arial", 18, "bold"), fg=YELLOW, bg=BG
    ).pack(anchor=tk.W)
    tk.Label(
        hdr,
        text="Select your players Excel file. It will be copied into the xlsx/ folder.",
        font=("Arial", 11),
        fg=GRAY,
        bg=BG,
        wraplength=620,
        justify=tk.LEFT,
    ).pack(anchor=tk.W, pady=(2, 0))

    tip_win = [None]
    status_lbl_ref = [None]
    path_lbl_ref = [None]
    err_lbl_ref = [None]
    confirm_holder = []

    def _check_enable():
        if confirm_holder:
            ok = selected["players"] is not None and (
                err_lbl_ref[0] is None or err_lbl_ref[0].cget("text") == ""
            )
            confirm_holder[0].config(state=tk.NORMAL if ok else tk.DISABLED)

    def _browse():
        path = filedialog.askopenfilename(
            parent=win,
            title="Select players file",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")],
        )
        if not path:
            return
        errs = validate_xlsx(path, "players")
        fname = os.path.basename(path)
        display = fname if len(fname) <= 50 else "\u2026" + fname[-49:]
        path_lbl_ref[0].config(text=display)
        if errs:
            selected["players"] = None
            status_lbl_ref[0].config(text="\u2717  Invalid", fg="#CC4444")
            err_lbl_ref[0].config(text="  \u2022 " + "\n  \u2022 ".join(errs))
        else:
            selected["players"] = path
            status_lbl_ref[0].config(text="\u2713  Valid", fg="#44CC44")
            err_lbl_ref[0].config(text="")
        _check_enable()

    body = tk.Frame(win, bg=BG)
    body.pack(fill=tk.BOTH, expand=True, padx=20)

    sect = tk.Frame(body, bg=BG_SECT, bd=1, relief=tk.SOLID)
    sect.pack(fill=tk.X, pady=10)

    title_bar = tk.Frame(sect, bg=BURG)
    title_bar.pack(fill=tk.X)
    tk.Label(
        title_bar,
        text="Players file",
        font=("Arial", 11, "bold"),
        fg=WHITE,
        bg=BURG,
        padx=10,
        pady=5,
    ).pack(anchor=tk.W)

    # Help text with spectrum term tooltips
    def _show_tip(event, desc):
        if tip_win[0]:
            tip_win[0].destroy()
            tip_win[0] = None
        tw = tk.Toplevel(win)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{event.x_root + 14}+{event.y_root + 20}")
        tk.Label(
            tw,
            text=desc,
            font=("Arial", 9),
            bg="#FFFBD0",
            fg="#222222",
            relief=tk.SOLID,
            bd=1,
            padx=8,
            pady=5,
            justify=tk.LEFT,
        ).pack()
        tip_win[0] = tw

    def _hide_tip(event):
        if tip_win[0]:
            tip_win[0].destroy()
            tip_win[0] = None

    txt = tk.Text(
        sect,
        font=("Arial", 9),
        fg=GRAY,
        bg=BG_SECT,
        relief=tk.FLAT,
        bd=0,
        highlightthickness=0,
        padx=12,
        pady=6,
        wrap=tk.NONE,
        cursor="arrow",
        state=tk.NORMAL,
    )
    txt.tag_configure("term", foreground=YELLOW, font=("Arial", 9, "bold"))
    remaining = _PLAYERS_FILE_HELP
    while remaining:
        earliest_pos, earliest_term = len(remaining), None
        for term in _SPECTRUM_TERMS:
            idx2 = remaining.find(term)
            if 0 <= idx2 < earliest_pos:
                earliest_pos, earliest_term = idx2, term
        if earliest_term is None:
            txt.insert(tk.END, remaining)
            break
        if earliest_pos > 0:
            txt.insert(tk.END, remaining[:earliest_pos])
        tag_name = f"term_{earliest_term}"
        txt.insert(tk.END, earliest_term, (tag_name, "term"))
        txt.tag_bind(
            tag_name,
            "<Enter>",
            lambda e, d=_SPECTRUM_TERMS[earliest_term]: _show_tip(e, d),
        )
        txt.tag_bind(tag_name, "<Leave>", _hide_tip)
        remaining = remaining[earliest_pos + len(earliest_term) :]
    txt.config(height=_PLAYERS_FILE_HELP.count("\n") + 1, state=tk.DISABLED)
    txt.pack(anchor=tk.W)

    # --- Example table ---
    example_lbl = tk.Label(
        sect,
        text="Example:",
        font=("Arial", 8, "italic"),
        fg=GRAY,
        bg=BG_SECT,
        padx=12,
    )
    example_lbl.pack(anchor=tk.W)

    _EXAMPLE_COLS = (
        "Name",
        "Surname",
        "Gender",
        "Level",
        "Prey",
        "Equilibrist",
        "Challenger",
        "Chill",
        "Hunter",
        "Classist",
    )
    _EXAMPLE_ROWS = [
        ("Alice", "Martin", "Female", "3.0", "5", "4", "3", "2", "1", "5"),
        ("Bob", "Dupont", "Male", "3.5", "", "", "", "", "", ""),
        ("Clara", "Bernard", "Female", "2.0", "2", "5", "4", "3", "5", "1"),
    ]

    style = ttk.Style()
    style.configure(
        "Example.Treeview",
        background="#2A2A2A",
        foreground=WHITE,
        fieldbackground="#2A2A2A",
        rowheight=18,
        font=("Courier", 8),
    )
    style.configure(
        "Example.Treeview.Heading",
        background="#555555",
        foreground="#000000",
        font=("Courier", 8, "bold"),
        relief=tk.FLAT,
    )
    style.map("Example.Treeview", background=[("selected", "#444444")])

    tbl_frame = tk.Frame(sect, bg=BG_SECT)
    tbl_frame.pack(fill=tk.X, padx=12, pady=(0, 6))

    tbl = ttk.Treeview(
        tbl_frame,
        columns=_EXAMPLE_COLS,
        show="headings",
        height=len(_EXAMPLE_ROWS),
        style="Example.Treeview",
        selectmode="none",
    )
    col_widths = [52, 62, 56, 46, 34, 68, 70, 38, 50, 58]
    for col, w in zip(_EXAMPLE_COLS, col_widths):
        tbl.heading(col, text=col)
        tbl.column(col, width=w, anchor=tk.CENTER, stretch=False)
    for r in _EXAMPLE_ROWS:
        tbl.insert("", tk.END, values=r)
    tbl.pack(side=tk.LEFT)

    row = tk.Frame(sect, bg=BG_SECT)
    row.pack(fill=tk.X, padx=10, pady=(0, 6))

    path_lbl = tk.Label(
        row,
        text="No file selected",
        font=("Arial", 9, "italic"),
        fg=GRAY,
        bg=BG_SECT,
        anchor=tk.W,
    )
    path_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
    path_lbl_ref[0] = path_lbl

    status_lbl = tk.Label(
        row,
        text="\u2717  Not selected",
        font=("Arial", 9, "bold"),
        fg="#CC4444",
        bg=BG_SECT,
        width=14,
    )
    status_lbl.pack(side=tk.RIGHT, padx=(6, 0))
    status_lbl_ref[0] = status_lbl

    tk.Button(
        row,
        text="Browse\u2026",
        font=("Arial", 9, "bold"),
        bg=YELLOW,
        fg="#000000",
        relief=tk.RAISED,
        cursor="hand2",
        command=_browse,
    ).pack(side=tk.RIGHT, padx=(0, 6))

    err_lbl = tk.Label(
        sect,
        text="",
        font=("Arial", 9),
        fg="#FF6B6B",
        bg=BG_SECT,
        justify=tk.LEFT,
        padx=12,
        wraplength=630,
        anchor=tk.W,
    )
    err_lbl.pack(anchor=tk.W, pady=(0, 4))
    err_lbl_ref[0] = err_lbl

    # --- Footer ---
    footer = tk.Frame(win, bg=BG)
    footer.pack(fill=tk.X, padx=20, pady=16)

    def _on_cancel():
        win.destroy()

    def _on_confirm():
        os.makedirs(_xlsx_dir, exist_ok=True)
        src = selected["players"]
        dest = os.path.join(_xlsx_dir, os.path.basename(src))
        if os.path.abspath(src) != os.path.abspath(dest):
            shutil.copy2(src, dest)
        config = {"players": os.path.basename(dest)}
        with open(_XLSX_CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(config, fh, ensure_ascii=False, indent=2)

        # Evict cached data_loader so load_data() re-reads the new file
        import sys as _sys

        for _k in list(_sys.modules.keys()):
            if "data_loader" in _k or (_k == "core.main") or (_k == "main"):
                del _sys.modules[_k]

        try:
            from core.data_loader import load_data as _load_data  # type: ignore
        except ImportError:
            from data_loader import load_data as _load_data  # type: ignore

        try:
            df = _load_data()
        except Exception as exc:
            err_lbl_ref[0].config(text=str(exc))
            return

        result["ok"] = True
        win.withdraw()

        # Ask for any missing gender / level
        _ask_missing_values(root, df, dest, BG, BG_SECT, BURG, YELLOW, WHITE, GRAY)

        # Setup-complete confirmation dialog
        copied_to = os.path.abspath(_xlsx_dir)
        dlg = tk.Toplevel(root)
        dlg.title("Setup complete")
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.update_idletasks()
        DW, DH = 520, 280
        sw2, sh2 = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
        dlg.geometry(f"{DW}x{DH}+{(sw2 - DW) // 2}+{(sh2 - DH) // 2}")
        dlg.grab_set()

        hdr2 = tk.Frame(dlg, bg=BURG)
        hdr2.pack(fill=tk.X)
        tk.Label(
            hdr2,
            text="\u2714  Setup complete",
            font=("Arial", 13, "bold"),
            fg=WHITE,
            bg=BURG,
            padx=16,
            pady=10,
        ).pack(anchor=tk.W)

        body2 = tk.Frame(dlg, bg=BG)
        body2.pack(fill=tk.BOTH, expand=True, padx=20, pady=14)
        tk.Label(
            body2,
            text=f"Your file has been copied to:\n{copied_to}",
            font=("Arial", 9, "bold"),
            fg=YELLOW,
            bg=BG,
            justify=tk.LEFT,
            wraplength=470,
            anchor=tk.W,
        ).pack(anchor=tk.W, pady=(0, 8))
        tk.Label(
            body2,
            text=(
                "You can update it at any time (e.g. add new players) —\n"
                "just keep the file name exactly the same.\n\n"
                "To reset and re-import a different file, delete the contents\n"
                "of the xlsx/ folder and xlsx_config.json, then restart."
            ),
            font=("Arial", 9),
            fg=GRAY,
            bg=BG,
            justify=tk.LEFT,
            wraplength=470,
            anchor=tk.W,
        ).pack(anchor=tk.W)

        ftr2 = tk.Frame(dlg, bg=BG)
        ftr2.pack(fill=tk.X, padx=20, pady=(0, 16))

        def _close_dlg():
            dlg.destroy()
            win.destroy()

        tk.Button(
            ftr2,
            text="OK",
            font=("Arial", 11, "bold"),
            bg=YELLOW,
            fg="#000000",
            relief=tk.RAISED,
            cursor="hand2",
            padx=20,
            pady=6,
            command=_close_dlg,
        ).pack(side=tk.RIGHT)
        dlg.bind("<Return>", lambda _: _close_dlg())
        dlg.protocol("WM_DELETE_WINDOW", _close_dlg)

    tk.Button(
        footer,
        text="Cancel",
        font=("Arial", 11),
        bg="#555555",
        fg=WHITE,
        relief=tk.RAISED,
        cursor="hand2",
        padx=14,
        pady=6,
        command=_on_cancel,
    ).pack(side=tk.LEFT)

    confirm_btn = tk.Button(
        footer,
        text="Confirm & Continue \u2192",
        font=("Arial", 11, "bold"),
        bg=YELLOW,
        fg="#000000",
        relief=tk.RAISED,
        cursor="hand2",
        padx=14,
        pady=6,
        state=tk.DISABLED,
        command=_on_confirm,
    )
    confirm_btn.pack(side=tk.RIGHT)
    confirm_holder.append(confirm_btn)

    win.protocol("WM_DELETE_WINDOW", _on_cancel)
    root.wait_window(win)
    return result["ok"]


class PlayerSelectionUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Roundnet Matchmaking - Player Selection")
        self._app_icon_photo = set_window_icon_from_logo(self.root)

        # Make window full screen by default (maximized)
        self.root.state("zoomed")

        # Color palette
        self.colors = {
            "bg_dark": "#2E2E2E",  # Dark grey background
            "bg_light": "#FFFFFF",  # White
            "accent_red": "#7F0301",  # Burgundy
            "accent_yellow": "#FED403",  # Yellow
            "text_dark": "#000000",  # Black
            "text_light": "#FFFFFF",  # White
        }

        # Screen size and scale factor (use 1080p as baseline)
        self.screen_w, self.screen_h = self._get_current_monitor_size()
        self.scale = max(0.6, self.screen_h / 1080.0)
        self._base_scale = self.scale
        self._last_monitor_signature = (
            self.screen_w,
            self.screen_h,
            round(self.scale, 3),
        )
        self._layout_refresh_after_id = None
        self._player_button_fit_after_id = None
        self._widget_base_fonts = {}

        self._base_font_sizes = {
            "small": 13,
            "small_bold": 13,
            "normal": 16,
            "normal_bold": 16,
            "big": 20,
            "huge": 32,
        }
        self._rebuild_fonts_from_scale()

        # Configure root background
        self.root.configure(bg=self.colors["bg_dark"])

        # Load main dataframe
        self.main_df = main_module.main_df.copy()
        self.selected_players = []
        self.player_overrides = {}
        self.preferred_pairs = []  # list of (frozenset({name1, name2}), forced_games)
        self._tooltip_window = None
        self._tooltip_after_id = None
        self._tooltip_delay_ms = 500

        # Create main frame with dark background
        main_frame = tk.Frame(root, bg=self.colors["bg_dark"])
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Create main notebook (tabbed interface) for all content
        # Configure style for tabs
        self.style = ttk.Style()
        self.style.theme_use("default")
        self.style.configure(
            "TNotebook.Tab",
            background=self.colors["accent_red"],
            foreground=self.colors["text_light"],
            padding=[20, 10],
            font=self.fonts["normal_bold"],
        )
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", self.colors["accent_yellow"])],
            foreground=[("selected", self.colors["text_dark"])],
        )

        self.main_notebook = ttk.Notebook(main_frame)
        self.main_notebook.pack(fill=tk.BOTH, expand=True)

        # Create "Session Generation" tab
        session_tab = tk.Frame(self.main_notebook, bg=self.colors["bg_dark"])
        self.main_notebook.add(session_tab, text="Session Generation")
        self.session_tab = session_tab

        # Header frame with logo and title (inside session tab)
        header_frame = tk.Frame(session_tab, bg=self.colors["bg_dark"])
        header_frame.pack(side=tk.TOP, pady=(10, 10))

        # Container to center logo and title together
        title_container = tk.Frame(header_frame, bg=self.colors["bg_dark"])
        title_container.pack()

        # Load and display logo
        try:
            logo_path = os.path.join(current_dir, "ui", "logo.png")
            logo_image = Image.open(logo_path)
            # Resize logo relative to screen scale
            logo_size = max(40, int(80 * getattr(self, "scale", 1.0)))
            logo_image = logo_image.resize(
                (logo_size, logo_size), Image.Resampling.LANCZOS
            )
            self.logo_photo = ImageTk.PhotoImage(logo_image)
            logo_label = tk.Label(
                title_container, image=self.logo_photo, bg=self.colors["bg_dark"]
            )
            logo_label.pack(side=tk.LEFT, padx=(0, 15))
        except Exception as e:
            print(f"Could not load logo: {e}")

        # Title with yellow accent
        title_label = tk.Label(
            title_container,
            text="ROUNDNET MATCHMAKING",
            font=self.fonts["huge"],
            fg=self.colors["accent_yellow"],
            bg=self.colors["bg_dark"],
        )
        title_label.pack(side=tk.LEFT)

        # Player count label with white text
        self.count_label = tk.Label(
            session_tab,
            text="Selected: 0 players",
            font=self.fonts["normal_bold"],
            fg=self.colors["text_light"],
            bg=self.colors["bg_dark"],
        )
        self.count_label.pack(
            side=tk.TOP, fill=tk.X, pady=(0, 10), padx=20, anchor=tk.W
        )

        # Buttons frame (part of session tab) - placed before the main paned area
        button_frame = tk.Frame(session_tab, bg=self.colors["bg_dark"])
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=15, padx=20)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(5, weight=1)

        # Custom button style
        btn_config = {
            "font": self.fonts["normal_bold"],
            "relief": tk.FLAT,
            "cursor": "hand2",
            "padx": 20,
            "pady": 10,
        }

        # Preferred Pairs button — leftmost
        self.pairs_btn = tk.Button(
            button_frame,
            text="\U0001f465 Preferred Pairs",
            command=self.show_preferred_pairs_dialog,
            bg=self.colors["accent_red"],
            fg=self.colors["text_light"],
            font=self.fonts["normal_bold"],
            relief=tk.FLAT,
            cursor="hand2",
            padx=20,
            pady=10,
        )
        self.pairs_btn.grid(row=0, column=1, padx=5)

        # Select All button
        self.select_all_btn = tk.Button(
            button_frame,
            text="Select All",
            command=self.select_all,
            bg=self.colors["bg_light"],
            fg=self.colors["text_dark"],
            **btn_config,
        )
        self.select_all_btn.grid(row=0, column=2, padx=5)

        # Clear Selection button
        self.clear_btn = tk.Button(
            button_frame,
            text="Clear Selection",
            command=self.clear_selection,
            bg=self.colors["bg_light"],
            fg=self.colors["text_dark"],
            **btn_config,
        )
        self.clear_btn.grid(row=0, column=3, padx=5)

        # Run Session button - highlighted with yellow
        self.run_btn = tk.Button(
            button_frame,
            text="⚡ RUN SESSION GENERATION ⚡",
            command=self.run_session,
            bg=self.colors["accent_yellow"],
            fg=self.colors["text_dark"],
            font=self.fonts["big"],
            relief=tk.FLAT,
            cursor="hand2",
            padx=25,
            pady=12,
        )
        self.run_btn.grid(row=0, column=4, padx=10)

        # Create vertical PanedWindow to separate main content from preferences
        vertical_paned = tk.PanedWindow(
            session_tab,
            orient=tk.VERTICAL,
            sashwidth=8,
            sashrelief=tk.RAISED,
            bg=self.colors["bg_dark"],
            bd=0,
        )
        vertical_paned.pack(
            side=tk.TOP, fill=tk.BOTH, expand=True, padx=20, pady=(0, 20)
        )

        # Store reference for dynamic resizing
        self.vertical_paned = vertical_paned

        # Create horizontal PanedWindow for resizable panels (top section)
        paned_window = tk.PanedWindow(
            vertical_paned,
            orient=tk.HORIZONTAL,
            sashwidth=8,
            sashrelief=tk.RAISED,
            bg=self.colors["bg_dark"],
            bd=0,
        )
        # Set default height relative to screen height
        top_pane_height = int(self.screen_h * 0.53)
        paned_window.config(height=top_pane_height)
        vertical_paned.add(paned_window, stretch="always")

        # Store reference for configuration
        self.paned_window = paned_window

        # Create frame for player buttons with burgundy border
        list_frame = self._make_label_frame(paned_window, "Available Players")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        paned_window.add(list_frame, stretch="always")

        # Store reference for configuration
        self.list_frame = list_frame

        # Create canvas and scrollbar for player buttons
        canvas = tk.Canvas(list_frame, bg=self.colors["bg_light"], highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.colors["bg_light"])

        # Keep references for later use
        self.player_canvas = canvas
        self.player_scrollable_frame = scrollable_frame

        # Initialize current mousewheel target (used by Games Editor)
        self._mousewheel_target_canvas = None

        # Update scrollregion when the internal frame changes
        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        # Create the window with a tag so we can reliably update its width
        canvas.create_window(
            (0, 0), window=scrollable_frame, anchor="nw", tags=("player_window",)
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        # Bind canvas resize to update scrollable_frame width using the tag
        def on_canvas_configure(event):
            try:
                canvas.itemconfig("player_window", width=event.width)
            except Exception:
                pass
            self._schedule_player_button_font_fit()

        canvas.bind("<Configure>", on_canvas_configure)

        # Mouse wheel handled globally to allow multiple scrollable areas

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Store player buttons
        self.player_buttons = {}
        self.player_button_states = {}  # Track selected state

        # Create player buttons in 6 columns, sorted alphabetically horizontally
        sorted_players = sorted(self.main_df.index)
        num_columns = 6

        for idx, player_name in enumerate(sorted_players):
            row = idx // num_columns
            col = idx % num_columns

            btn = tk.Button(
                scrollable_frame,
                text=self.format_player_button_text(player_name),
                font=self.player_button_font,
                bg=self.colors["bg_light"],
                fg=self.colors["text_dark"],
                relief=tk.RAISED,
                bd=2,
                cursor="hand2",
                padx=self.player_button_padx,
                pady=self.player_button_pady,
                anchor="center",
                command=lambda name=player_name: self.toggle_player(name),
            )
            btn.grid(row=row, column=col, padx=2, pady=2, sticky=(tk.W, tk.E))
            btn.bind(
                "<Button-3>",
                lambda event, name=player_name: self.show_edit_player_dialog(name),
            )
            self.bind_tooltip(btn, "right click to change specs")

            self.player_buttons[player_name] = btn
            self.player_button_states[player_name] = False

        # Add "+ Add Player" button at the end of the list
        total_players = len(sorted_players)
        add_row = total_players // num_columns
        add_col = total_players % num_columns

        add_player_btn = tk.Button(
            scrollable_frame,
            text="+ Add Player",
            font=self.player_button_font,
            bg=self.colors["accent_red"],
            fg=self.colors["text_light"],
            relief=tk.RAISED,
            bd=2,
            cursor="hand2",
            padx=self.player_button_padx,
            pady=self.player_button_pady,
            anchor="center",
            command=self.show_add_player_dialog,
        )
        add_player_btn.grid(
            row=add_row, column=add_col, padx=2, pady=2, sticky=(tk.W, tk.E)
        )
        self.add_player_btn = add_player_btn

        # Configure column weights for equal distribution
        for col in range(num_columns):
            scrollable_frame.columnconfigure(col, weight=1)

        # Let tkinter process pending events so the splash bar keeps animating
        self.root.update_idletasks()

        # Create frame for selected players info
        info_frame = self._make_label_frame(paned_window, "Selected Players Info")
        info_frame.rowconfigure(0, weight=1)
        info_frame.columnconfigure(0, weight=1)
        paned_window.add(info_frame, stretch="always")

        # Store reference for configuration
        self.info_frame = info_frame

        self.info_text = scrolledtext.ScrolledText(
            info_frame,
            width=40,
            font=self.fonts["small"],
            bg=self.colors["bg_light"],
            fg=self.colors["text_dark"],
            highlightthickness=0,
            wrap=tk.WORD,
        )
        self.info_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create console output frame on the right
        console_frame = self._make_label_frame(paned_window, "Console Output")
        console_frame.rowconfigure(0, weight=1)
        console_frame.columnconfigure(0, weight=1)
        paned_window.add(console_frame, stretch="always")

        # Store reference for configuration
        self.console_frame = console_frame

        self.console_text = scrolledtext.ScrolledText(
            console_frame,
            width=50,
            font=("Consolas", 9),
            bg="#1E1E1E",
            fg="#D4D4D4",
            highlightthickness=0,
            wrap=tk.WORD,
        )
        self.console_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.console_text.insert("1.0", "Console output will appear here...\n")
        self.console_text.config(state=tk.DISABLED)

        # Redirect stdout to console immediately and permanently
        self.original_stdout = sys.stdout
        sys.stdout = ConsoleRedirector(self.console_text)

        # Create frame for round preferences (bottom section of vertical paned window)
        prefs_frame = self._make_label_frame(vertical_paned, "Round Preferences")
        vertical_paned.add(prefs_frame, stretch="never")
        prefs_frame.rowconfigure(0, weight=1)
        prefs_frame.columnconfigure(0, weight=3)
        prefs_frame.columnconfigure(1, weight=2)

        # Store reference for dynamic resizing
        self.prefs_frame = prefs_frame
        self.prefs_default_height = int(
            self.screen_h * 0.27
        )  # Store default height (scaled)

        # Create left panel for round preferences list
        rounds_panel = tk.Frame(prefs_frame, bg=self.colors["bg_light"])
        rounds_panel.grid(
            row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(10, 6), pady=10
        )
        rounds_panel.rowconfigure(0, weight=1)
        rounds_panel.columnconfigure(0, weight=1)

        # Create right panel for parameters
        parameters_panel = tk.LabelFrame(
            prefs_frame,
            text="parameters",
            font=self.fonts["normal_bold"],
            bg=self.colors["bg_light"],
            fg=self.colors["accent_red"],
            bd=2,
            relief=tk.RIDGE,
            padx=10,
            pady=10,
        )
        parameters_panel.grid(
            row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(6, 10), pady=10
        )
        parameters_panel.rowconfigure(0, weight=1)
        parameters_panel.columnconfigure(0, weight=1)

        # Make parameters area scrollable vertically
        params_canvas = tk.Canvas(
            parameters_panel, bg=self.colors["bg_light"], highlightthickness=0
        )
        params_scrollbar = tk.Scrollbar(
            parameters_panel, orient="vertical", command=params_canvas.yview
        )
        params_scrollable_frame = tk.Frame(params_canvas, bg=self.colors["bg_light"])

        params_scrollable_frame.bind(
            "<Configure>",
            lambda e: params_canvas.configure(scrollregion=params_canvas.bbox("all")),
        )

        params_canvas.create_window(
            (0, 0),
            window=params_scrollable_frame,
            anchor="nw",
            width=params_canvas.winfo_width(),
            tags=("params_window",),
        )
        params_canvas.configure(yscrollcommand=params_scrollbar.set)

        def on_params_canvas_configure(event):
            try:
                params_canvas.itemconfig("params_window", width=event.width)
            except Exception:
                pass

        params_canvas.bind("<Configure>", on_params_canvas_configure)

        # Store references for global mousewheel dispatcher
        self.params_canvas = params_canvas
        self.params_scrollable_frame = params_scrollable_frame

        params_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        params_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        params_grid = tk.Frame(params_scrollable_frame, bg=self.colors["bg_light"])
        params_grid.pack(fill=tk.BOTH, expand=True)
        params_grid.columnconfigure(0, weight=1)
        params_grid.columnconfigure(1, weight=1)

        # Create canvas and scrollbar for round preferences
        rounds_canvas = tk.Canvas(
            rounds_panel, bg=self.colors["bg_light"], highlightthickness=0
        )
        rounds_scrollbar = tk.Scrollbar(
            rounds_panel, orient="vertical", command=rounds_canvas.yview
        )
        rounds_scrollable_frame = tk.Frame(rounds_canvas, bg=self.colors["bg_light"])

        rounds_scrollable_frame.bind(
            "<Configure>",
            lambda e: rounds_canvas.configure(scrollregion=rounds_canvas.bbox("all")),
        )

        rounds_canvas.create_window(
            (0, 0),
            window=rounds_scrollable_frame,
            anchor="nw",
            width=rounds_canvas.winfo_width(),
        )
        rounds_canvas.configure(yscrollcommand=rounds_scrollbar.set)

        # Bind canvas resize to update scrollable_frame width
        def on_rounds_canvas_configure(event):
            rounds_canvas.itemconfig(
                rounds_canvas.find_withtag("all")[0], width=event.width
            )

        rounds_canvas.bind("<Configure>", on_rounds_canvas_configure)

        # Store references for global mousewheel dispatcher
        self.rounds_canvas = rounds_canvas
        self.rounds_scrollable_frame = rounds_scrollable_frame

        rounds_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        rounds_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # Container for round preferences (will be dynamically populated)
        self.rounds_container = tk.Frame(
            rounds_scrollable_frame, bg=self.colors["bg_light"]
        )
        self.rounds_container.grid(
            row=0, column=0, columnspan=5, sticky=(tk.W, tk.E), padx=10, pady=10
        )

        # Create initial round preferences
        self.type_prefs = []
        self.gender_prefs = []
        self.round_frames = []
        self.type_buttons_list = []  # Store type button references
        self.gender_buttons_list = []  # Store gender button references

        self.num_rounds_var = tk.IntVar(value=4)

        self.create_round_preferences()
        self.root.update_idletasks()

        # Number of rounds control
        rounds_control_frame = tk.Frame(
            rounds_scrollable_frame, bg=self.colors["bg_light"]
        )
        rounds_control_frame.grid(
            row=1, column=0, columnspan=5, pady=(10, 10), sticky=tk.W, padx=10
        )

        tk.Label(
            rounds_control_frame,
            text="Number of Rounds:",
            font=self.fonts["normal_bold"],
            bg=self.colors["bg_light"],
            fg=self.colors["text_dark"],
        ).pack(side=tk.LEFT, padx=5)

        # Custom styled buttons for rounds
        minus_btn = tk.Button(
            rounds_control_frame,
            text="-",
            width=3,
            command=self.decrease_rounds,
            bg=self.colors["accent_red"],
            fg=self.colors["text_light"],
            font=self.fonts["normal_bold"],
            relief=tk.FLAT,
            cursor="hand2",
        )
        minus_btn.pack(side=tk.LEFT, padx=2)

        self.rounds_label = tk.Label(
            rounds_control_frame,
            text="4",
            font=self.fonts["big"],
            width=3,
            bg=self.colors["accent_yellow"],
            fg=self.colors["text_dark"],
        )
        self.rounds_label.pack(side=tk.LEFT, padx=5)

        plus_btn = tk.Button(
            rounds_control_frame,
            text="+",
            width=3,
            command=self.increase_rounds,
            bg=self.colors["accent_red"],
            fg=self.colors["text_light"],
            font=self.fonts["normal_bold"],
            relief=tk.FLAT,
            cursor="hand2",
        )
        plus_btn.pack(side=tk.LEFT, padx=2)

        # Games per round control
        games_control_frame = tk.Frame(
            rounds_scrollable_frame, bg=self.colors["bg_light"]
        )
        games_control_frame.grid(
            row=2, column=0, columnspan=5, pady=(10, 10), sticky=tk.W, padx=10
        )

        tk.Label(
            games_control_frame,
            text="Games per Round:",
            font=self.fonts["normal_bold"],
            bg=self.colors["bg_light"],
            fg=self.colors["text_dark"],
        ).pack(side=tk.LEFT, padx=5)

        # Create radio buttons for games per round
        self.games_per_round_var = tk.StringVar(value="auto")

        games_options_frame = tk.Frame(games_control_frame, bg=self.colors["bg_light"])
        games_options_frame.pack(side=tk.LEFT, padx=5)

        # Auto option (default: players/4)
        tk.Radiobutton(
            games_options_frame,
            text="Auto",
            variable=self.games_per_round_var,
            value="auto",
            bg=self.colors["bg_light"],
            fg=self.colors["text_dark"],
            selectcolor=self.colors["accent_yellow"],
            font=self.fonts["normal"],
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=5)

        # Specific number options (1-5 games)
        for num_games in range(1, 9):
            tk.Radiobutton(
                games_options_frame,
                text=str(num_games),
                variable=self.games_per_round_var,
                value=str(num_games),
                bg=self.colors["bg_light"],
                fg=self.colors["text_dark"],
                selectcolor=self.colors["accent_yellow"],
                font=self.fonts["normal"],
                cursor="hand2",
            ).pack(side=tk.LEFT, padx=3)

        # Parameter sliders
        self._make_param_slider(
            params_grid,
            0,
            0,
            "Shift female levels",
            "Temporary shifter applied to female players' level before matchmaking.",
            "female_boost_var",
            "female_boost_scale",
            -2.0,
            2.0,
            0.1,
            0.0,
        )
        self._make_param_slider(
            params_grid,
            2,
            0,
            "maximal level gap in game",
            "Maximum allowed level difference considered acceptable inside a game.",
            "level_gap_tol_var",
            "level_gap_tol_scale",
            0.5,
            3.0,
            0.1,
            1.1,
        )
        self._make_param_slider(
            params_grid,
            1,
            0,
            "minimize happiness gap",
            "Higher values prioritize reducing happiness inequality across players.",
            "lambda_weight_var",
            "lambda_weight_scale",
            0.0,
            5.0,
            0.1,
            2.4,
        )

        # Spectrum toggle parameter
        spectrum_control_frame = tk.Frame(
            params_grid, bg="#dddddd", bd=2, relief=tk.RIDGE
        )
        spectrum_control_frame.grid(
            row=0, column=1, rowspan=3, sticky=(tk.W, tk.E, tk.N), padx=4, pady=4
        )

        spectrum_row = tk.Frame(spectrum_control_frame, bg="#dddddd")
        spectrum_row.pack(fill=tk.X, padx=5, pady=4)

        spectrum_label = tk.Label(
            spectrum_row,
            text="Spectrum",
            font=self.fonts["small_bold"],
            bg="#dddddd",
            fg=self.colors["text_dark"],
        )
        spectrum_label.pack(side=tk.LEFT)
        self.bind_tooltip(
            spectrum_label,
            "Enable or disable spectrum preferences during matchup generation.",
        )

        self.spectrum_var = tk.BooleanVar(value=True)
        spectrum_buttons_frame = tk.Frame(spectrum_row, bg="#dddddd")
        spectrum_buttons_frame.pack(side=tk.RIGHT)

        spectrum_on_btn = tk.Button(
            spectrum_buttons_frame,
            text="ON",
            font=self.fonts["small"],
            width=6,
            cursor="hand2",
            padx=5,
            pady=0,
            command=lambda: self.set_spectrum_state(True),
        )
        spectrum_on_btn.pack(side=tk.LEFT, padx=2)

        spectrum_off_btn = tk.Button(
            spectrum_buttons_frame,
            text="OFF",
            font=self.fonts["small"],
            width=6,
            cursor="hand2",
            padx=5,
            pady=0,
            command=lambda: self.set_spectrum_state(False),
        )
        spectrum_off_btn.pack(side=tk.LEFT, padx=2)

        self.spectrum_buttons = {"on": spectrum_on_btn, "off": spectrum_off_btn}
        self.update_spectrum_switch_display()

        # PNG levels toggle
        levels_row = tk.Frame(spectrum_control_frame, bg="#dddddd")
        levels_row.pack(fill=tk.X, padx=5, pady=(0, 4))
        levels_label = tk.Label(
            levels_row,
            text="Show levels in session PNG",
            font=self.fonts["small_bold"],
            bg="#dddddd",
            fg=self.colors["text_dark"],
        )
        levels_label.pack(side=tk.LEFT)
        self.bind_tooltip(
            levels_label,
            "Show each player's level next to their name in the Session Games PNG.",
        )
        self.png_show_levels_var = tk.BooleanVar(value=False)
        levels_btn_frame = tk.Frame(levels_row, bg="#dddddd")
        levels_btn_frame.pack(side=tk.RIGHT)
        levels_on_btn = tk.Button(
            levels_btn_frame,
            text="ON",
            font=self.fonts["small"],
            width=6,
            cursor="hand2",
            padx=5,
            pady=0,
            command=lambda: self._set_png_levels_state(True),
        )
        levels_on_btn.pack(side=tk.LEFT, padx=2)
        levels_off_btn = tk.Button(
            levels_btn_frame,
            text="OFF",
            font=self.fonts["small"],
            width=6,
            cursor="hand2",
            padx=5,
            pady=0,
            command=lambda: self._set_png_levels_state(False),
        )
        levels_off_btn.pack(side=tk.LEFT, padx=2)
        self._png_levels_buttons = {"on": levels_on_btn, "off": levels_off_btn}
        self._set_png_levels_state(False)  # initialise display

        # Configure grid weights
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Configure grid weights
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Configure default pane sizes relative to screen
        list_w = int(self.screen_w * 0.5)
        info_w = int(self.screen_w * 0.22)
        console_w = int(self.screen_w * 0.28)

        self.paned_window.paneconfigure(self.list_frame, width=list_w)
        self.paned_window.paneconfigure(self.info_frame, width=info_w)
        self.paned_window.paneconfigure(self.console_frame, width=console_w)

        # Vertical panes: use top_pane_height computed earlier and scaled prefs height
        prefs_height = int(self.screen_h * 0.27)
        self.vertical_paned.paneconfigure(self.paned_window, height=top_pane_height)
        self.vertical_paned.paneconfigure(self.prefs_frame, height=prefs_height)

        # Global mousewheel handler to dispatch scroll events to the widget under cursor
        def _can_scroll(cnv):
            try:
                bbox = cnv.bbox("all")
                if not bbox:
                    return False
                content_h = bbox[3] - bbox[1]
                visible_h = cnv.winfo_height()
                return content_h > visible_h
            except Exception:
                return True

        def _wheel_units(event):
            delta = getattr(event, "delta", 0)
            if delta == 0:
                return 0
            if abs(delta) < 120:
                return -1 if delta > 0 else 1
            return int(-1 * (delta / 120))

        def _on_global_mousewheel(event):
            try:
                # If a target canvas is explicitly set by hover, prefer it
                target = getattr(self, "_mousewheel_target_canvas", None)
                if target is not None:
                    try:
                        units = _wheel_units(event)
                        if _can_scroll(target):
                            target.yview_scroll(units, "units")
                        return "break"
                    except Exception:
                        return

                # Fallback: find widget under pointer and dispatch
                x_root = self.root.winfo_pointerx()
                y_root = self.root.winfo_pointery()
                widget = self.root.winfo_containing(x_root, y_root)

                # Helper to check ancestry
                def is_descendant(w, ancestor):
                    while w is not None:
                        if w == ancestor:
                            return True
                        w = getattr(w, "master", None)
                    return False

                # Dispatch to player canvas if pointer is inside its scrollable frame
                if (
                    hasattr(self, "player_scrollable_frame")
                    and widget is not None
                    and is_descendant(widget, self.player_scrollable_frame)
                ):
                    try:
                        units = _wheel_units(event)
                        if _can_scroll(self.player_canvas):
                            self.player_canvas.yview_scroll(units, "units")
                        return "break"
                    except Exception:
                        pass

                # Dispatch to rounds canvas if pointer is inside its scrollable frame
                if (
                    hasattr(self, "rounds_scrollable_frame")
                    and widget is not None
                    and is_descendant(widget, self.rounds_scrollable_frame)
                ):
                    try:
                        units = _wheel_units(event)
                        if _can_scroll(self.rounds_canvas):
                            self.rounds_canvas.yview_scroll(units, "units")
                        return "break"
                    except Exception:
                        pass

                # Dispatch to parameters canvas if pointer is inside its scrollable frame
                if (
                    hasattr(self, "params_scrollable_frame")
                    and widget is not None
                    and is_descendant(widget, self.params_scrollable_frame)
                ):
                    try:
                        units = _wheel_units(event)
                        if _can_scroll(self.params_canvas):
                            self.params_canvas.yview_scroll(units, "units")
                        return "break"
                    except Exception:
                        pass
            except Exception:
                pass

        # Bind the global mousewheel dispatcher
        try:
            self.root.bind_all("<MouseWheel>", _on_global_mousewheel)
        except Exception:
            pass

        # Monitor-aware responsive refresh (handles moving window between screens)
        self.root.bind("<Configure>", self._on_root_configure)
        self.root.after(150, lambda: self.refresh_layout_for_current_screen(force=True))
        # Second pass after the window manager has fully settled the maximized layout
        self.root.after(800, self._schedule_player_button_font_fit)

    def _make_label_frame(self, parent, title, bd=3):
        """Return a styled LabelFrame with the app's standard look."""
        return tk.LabelFrame(
            parent,
            text=title,
            font=self.fonts["normal_bold"],
            bg=self.colors["bg_light"],
            fg=self.colors["accent_red"],
            bd=bd,
            relief=tk.RIDGE,
        )

    def _make_param_slider(
        self,
        parent,
        grid_row,
        grid_col,
        label_text,
        tooltip_text,
        var_attr,
        scale_attr,
        from_,
        to_,
        resolution,
        initial_value,
    ):
        """Create a ridged labeled Scale, assigning self.{var_attr} and self.{scale_attr}."""
        ctrl_frame = tk.Frame(parent, bg="#dddddd", bd=2, relief=tk.RIDGE)
        ctrl_frame.grid(
            row=grid_row, column=grid_col, sticky=(tk.W, tk.E), padx=4, pady=4
        )
        row_frame = tk.Frame(ctrl_frame, bg="#dddddd")
        row_frame.pack(fill=tk.X, padx=5, pady=4)
        label = tk.Label(
            row_frame,
            text=label_text,
            font=self.fonts["small_bold"],
            bg="#dddddd",
            fg=self.colors["text_dark"],
        )
        label.pack(side=tk.LEFT)
        self.bind_tooltip(label, tooltip_text)
        var = tk.DoubleVar(value=initial_value)
        setattr(self, var_attr, var)
        scale = tk.Scale(
            row_frame,
            from_=from_,
            to=to_,
            resolution=resolution,
            orient=tk.HORIZONTAL,
            variable=var,
            showvalue=True,
            length=max(100, int(120 * self.scale)),
            font=self.fonts["normal"],
            bg="#dddddd",
            fg=self.colors["text_dark"],
            highlightthickness=0,
            troughcolor=self.colors["bg_light"],
            activebackground=self.colors["accent_yellow"],
            cursor="hand2",
        )
        scale.pack(side=tk.RIGHT)
        setattr(self, scale_attr, scale)

    def _make_toggle_group(self, parent, bg_color, label_text, options, var):
        """Create a ridged section with toggle buttons for a StringVar.

        Returns (section_frame, buttons_dict).
        """
        section = tk.Frame(parent, bg=bg_color, relief=tk.RIDGE, bd=2)
        tk.Label(
            section,
            text=label_text,
            font=self.fonts["small_bold"],
            bg=bg_color,
            fg=self.colors["text_dark"],
        ).pack(side=tk.LEFT, padx=(5, 5))
        btn_frame = tk.Frame(section, bg=bg_color)
        btn_frame.pack(side=tk.LEFT, padx=(0, 5), pady=1)

        buttons = {}
        for option in options:
            btn = tk.Button(
                btn_frame,
                text=option.capitalize(),
                font=self.fonts["small"],
                width=8,
                cursor="hand2",
                padx=5,
                pady=0,
            )
            btn.pack(side=tk.LEFT, padx=2)
            buttons[option] = btn

        def make_toggle(opt, btns_ref):
            def toggle():
                var.set(opt)
                for o, b in btns_ref.items():
                    if o == opt:
                        b.config(
                            bg=self.colors["accent_yellow"],
                            fg=self.colors["text_dark"],
                            relief=tk.SUNKEN,
                        )
                    else:
                        b.config(
                            bg=self.colors["bg_light"],
                            fg=self.colors["text_dark"],
                            relief=tk.RAISED,
                        )

            return toggle

        for option, btn in buttons.items():
            btn.config(command=make_toggle(option, buttons))

        for option, btn in buttons.items():
            if option == var.get():
                btn.config(
                    bg=self.colors["accent_yellow"],
                    fg=self.colors["text_dark"],
                    relief=tk.SUNKEN,
                )
            else:
                btn.config(
                    bg=self.colors["bg_light"],
                    fg=self.colors["text_dark"],
                    relief=tk.RAISED,
                )

        return section, buttons

    def _scaled_font_tuple(self, font_tuple, factor: float):
        """Create a scaled font tuple from an existing font tuple."""
        name = font_tuple[0]
        size = font_tuple[1] if len(font_tuple) > 1 else 12
        extras = font_tuple[2:] if len(font_tuple) > 2 else ()
        return (name, max(8, int(size * factor)), *extras)

    def _rebuild_fonts_from_scale(self):
        """Rebuild standard UI fonts from current scale."""

        def s(sz):
            return max(8, int(sz * self.scale))

        self.fonts = {
            "small": ("Arial", s(self._base_font_sizes["small"])),
            "small_bold": ("Arial", s(self._base_font_sizes["small_bold"]), "bold"),
            "normal": ("Arial", s(self._base_font_sizes["normal"])),
            "normal_bold": (
                "Arial",
                s(self._base_font_sizes["normal_bold"]),
                "bold",
            ),
            "big": ("Arial", s(self._base_font_sizes["big"]), "bold"),
            "huge": ("Arial", s(self._base_font_sizes["huge"]), "bold"),
        }

        # Slightly larger player selection button font and padding (~108%)
        self.player_button_font = self._scaled_font_tuple(
            self.fonts["normal_bold"], 1.08
        )
        self.player_button_padx = max(2, int(5 * 1.08 * self.scale))
        self.player_button_pady = max(2, int(5 * 1.08 * self.scale))

    def _get_current_monitor_size(self):
        """Return width/height of monitor containing the root window (with fallback)."""
        try:
            user32 = ctypes.windll.user32

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD),
                ]

            MONITOR_DEFAULTTONEAREST = 2
            hwnd = self.root.winfo_id()
            monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
            if monitor:
                monitor_info = MONITORINFO()
                monitor_info.cbSize = ctypes.sizeof(MONITORINFO)
                if user32.GetMonitorInfoW(monitor, ctypes.byref(monitor_info)):
                    rect = monitor_info.rcMonitor
                    width = max(1, rect.right - rect.left)
                    height = max(1, rect.bottom - rect.top)
                    return width, height
        except Exception:
            pass

        return self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def _on_root_configure(self, event=None):
        """Throttle resize/monitor-change refreshes."""
        if self._layout_refresh_after_id is not None:
            try:
                self.root.after_cancel(self._layout_refresh_after_id)
            except Exception:
                pass

        self._layout_refresh_after_id = self.root.after(
            120, self.refresh_layout_for_current_screen
        )
        # Always re-fit button fonts on any window geometry change (e.g. maximize/restore)
        self._schedule_player_button_font_fit()

    def _apply_scaled_fonts_to_widget_tree(self):
        """Apply scaled fonts to current widget tree while preserving font family/style."""
        scale_ratio = self.scale / self._base_scale if self._base_scale else 1.0

        # Nothing to rescale if ratio is 1 — skip the expensive tree walk
        if abs(scale_ratio - 1.0) < 0.001:
            return

        def walk(widget):
            try:
                for child in widget.winfo_children():
                    walk(child)
            except Exception:
                return

            widget_id = str(widget)
            try:
                current_font = widget.cget("font")
            except Exception:
                return

            if not current_font:
                return

            if widget_id not in self._widget_base_fonts:
                try:
                    f = tkfont.Font(font=current_font)
                    actual = f.actual()
                    self._widget_base_fonts[widget_id] = {
                        "family": actual.get("family", "Arial"),
                        "size": max(1, abs(int(actual.get("size", 10)))),
                        "weight": actual.get("weight", "normal"),
                        "slant": actual.get("slant", "roman"),
                        "underline": int(actual.get("underline", 0)),
                        "overstrike": int(actual.get("overstrike", 0)),
                    }
                except Exception:
                    return

            base = self._widget_base_fonts.get(widget_id)
            if not base:
                return

            new_size = max(8, int(base["size"] * scale_ratio))
            try:
                style_tokens = []
                if base["weight"] == "bold":
                    style_tokens.append("bold")
                if base["slant"] == "italic":
                    style_tokens.append("italic")
                if base["underline"]:
                    style_tokens.append("underline")
                if base["overstrike"]:
                    style_tokens.append("overstrike")

                style_suffix = " ".join(style_tokens)
                if style_suffix:
                    widget.configure(font=(base["family"], new_size, style_suffix))
                else:
                    widget.configure(font=(base["family"], new_size))
            except Exception:
                pass

        walk(self.root)

    def _schedule_player_button_font_fit(self):
        """Throttle auto-fit of player button text to button width."""
        if self._player_button_fit_after_id is not None:
            try:
                self.root.after_cancel(self._player_button_fit_after_id)
            except Exception:
                pass

        self._player_button_fit_after_id = self.root.after(
            50, self._fit_player_button_fonts
        )

    def _fit_player_button_fonts(self):
        """Set one shared font size for all player buttons based on longest label."""
        self._player_button_fit_after_id = None

        if not hasattr(self, "player_buttons"):
            return

        try:
            base_family = self.player_button_font[0]
            base_size = int(self.player_button_font[1])
            base_style = (
                self.player_button_font[2:] if len(self.player_button_font) > 2 else ()
            )
        except Exception:
            base_family = "Arial"
            base_size = 12
            base_style = ("bold",)

        min_size = 7

        all_buttons = []
        all_labels = []

        for player_name, button in self.player_buttons.items():
            all_buttons.append(button)
            all_labels.append(self.format_player_button_text(player_name))

        if hasattr(self, "add_player_btn") and self.add_player_btn is not None:
            all_buttons.append(self.add_player_btn)
            all_labels.append("+ Add Player")

        if not all_buttons:
            return

        longest_label = max(all_labels, key=lambda x: len(str(x)))

        available_widths = []
        for button in all_buttons:
            try:
                width_px = int(button.winfo_width())
                pad_x = int(button.cget("padx"))
                if width_px > 1:
                    available_widths.append(max(20, width_px - (2 * pad_x) - 10))
            except Exception:
                continue

        if not available_widths:
            # Geometry not ready yet — flush pending layout and retry once.
            self.root.update_idletasks()
            for button in all_buttons:
                try:
                    width_px = int(button.winfo_width())
                    pad_x = int(button.cget("padx"))
                    if width_px > 1:
                        available_widths.append(max(20, width_px - (2 * pad_x) - 10))
                except Exception:
                    continue

        if not available_widths:
            # Still not ready — schedule another attempt in 300 ms.
            self._player_button_fit_after_id = self.root.after(
                300, self._fit_player_button_fonts
            )
            return

        target_available_px = min(available_widths)
        target_size = base_size

        while target_size > min_size:
            candidate_font = (base_family, target_size, *base_style)
            try:
                text_px = tkfont.Font(font=candidate_font).measure(longest_label)
            except Exception:
                break
            if text_px <= target_available_px:
                break
            target_size -= 1

        shared_font = (base_family, target_size, *base_style)
        for button in all_buttons:
            try:
                button.config(font=shared_font)
            except Exception:
                pass

    def refresh_layout_for_current_screen(self, force=False):
        """Refresh dimensions/fonts when monitor changes or a resize requires re-scaling."""
        self._layout_refresh_after_id = None
        screen_w, screen_h = self._get_current_monitor_size()
        next_scale = max(0.6, screen_h / 1080.0)
        signature = (screen_w, screen_h, round(next_scale, 3))

        if not force and signature == self._last_monitor_signature:
            return

        self.screen_w = screen_w
        self.screen_h = screen_h
        self.scale = next_scale
        self._last_monitor_signature = signature

        self._rebuild_fonts_from_scale()

        # Notebook tab typography and spacing
        try:
            self.style.configure(
                "TNotebook.Tab",
                font=self.fonts["normal_bold"],
                padding=[max(12, int(20 * self.scale)), max(6, int(10 * self.scale))],
            )
        except Exception:
            pass

        # Refresh pane sizes
        try:
            list_w = int(self.screen_w * 0.5)
            info_w = int(self.screen_w * 0.22)
            console_w = int(self.screen_w * 0.28)
            self.paned_window.paneconfigure(self.list_frame, width=list_w)
            self.paned_window.paneconfigure(self.info_frame, width=info_w)
            self.paned_window.paneconfigure(self.console_frame, width=console_w)
        except Exception:
            pass

        try:
            top_pane_height = int(self.screen_h * 0.53)
            prefs_height = int(self.screen_h * 0.27)
            self.vertical_paned.paneconfigure(self.paned_window, height=top_pane_height)
            self.vertical_paned.paneconfigure(self.prefs_frame, height=prefs_height)
            self.prefs_default_height = prefs_height
        except Exception:
            pass

        # Scale parameter controls lengths
        control_length = max(100, int(120 * self.scale))
        for control_name in (
            "female_boost_scale",
            "level_gap_tol_scale",
            "lambda_weight_scale",
        ):
            try:
                getattr(self, control_name).config(length=control_length)
            except Exception:
                pass

        # Scale player list button typography/padding
        for button in self.player_buttons.values():
            try:
                button.config(
                    font=self.player_button_font,
                    padx=self.player_button_padx,
                    pady=self.player_button_pady,
                )
            except Exception:
                pass

        try:
            self.add_player_btn.config(
                font=self.player_button_font,
                padx=self.player_button_padx,
                pady=self.player_button_pady,
            )
        except Exception:
            pass

        self._schedule_player_button_font_fit()

        # Apply scaled fonts across existing widgets
        self._apply_scaled_fonts_to_widget_tree()

    def write_to_console(self, text):
        """Write text to the console output widget"""
        self.console_text.config(state=tk.NORMAL)
        self.console_text.insert(tk.END, text)
        self.console_text.see(tk.END)
        self.console_text.config(state=tk.DISABLED)
        self.root.update()

    def bind_tooltip(self, widget, text):
        """Bind a simple hover tooltip to a widget."""
        widget.bind(
            "<Enter>",
            lambda event, tooltip_text=text: self.schedule_tooltip(event, tooltip_text),
        )
        widget.bind("<Leave>", self.hide_tooltip)

    def schedule_tooltip(self, event, text):
        """Schedule tooltip display after a short delay."""
        self.hide_tooltip()

        widget = event.widget
        x = widget.winfo_rootx() + 14
        y = widget.winfo_rooty() + widget.winfo_height() + 8

        self._tooltip_after_id = self.root.after(
            self._tooltip_delay_ms,
            lambda: self.show_tooltip_at(x, y, text),
        )

    def show_tooltip(self, event, text):
        """Show a tooltip near the hovered widget."""
        self.hide_tooltip()

        x = event.widget.winfo_rootx() + 14
        y = event.widget.winfo_rooty() + event.widget.winfo_height() + 8
        self.show_tooltip_at(x, y, text)

    def show_tooltip_at(self, x, y, text):
        """Show a tooltip at screen coordinates."""
        self.hide_tooltip()

        tooltip = tk.Toplevel(self.root)
        tooltip.wm_overrideredirect(True)
        try:
            tooltip.wm_attributes("-topmost", True)
        except Exception:
            pass

        tooltip_label = tk.Label(
            tooltip,
            text=text,
            justify=tk.LEFT,
            bg="#FFF8DC",
            fg=self.colors["text_dark"],
            relief=tk.SOLID,
            bd=1,
            padx=6,
            pady=4,
            wraplength=max(220, int(280 * self.scale)),
            font=self.fonts["small"],
        )
        tooltip_label.pack()
        tooltip.wm_geometry(f"+{x}+{y}")

        self._tooltip_window = tooltip

    def hide_tooltip(self, event=None):
        """Hide current tooltip if displayed."""
        if self._tooltip_after_id is not None:
            try:
                self.root.after_cancel(self._tooltip_after_id)
            except Exception:
                pass
            self._tooltip_after_id = None

        if self._tooltip_window is not None:
            try:
                self._tooltip_window.destroy()
            except Exception:
                pass
            self._tooltip_window = None

    def clear_console(self):
        """Clear the console output"""
        self.console_text.config(state=tk.NORMAL)
        self.console_text.delete("1.0", tk.END)
        self.console_text.config(state=tk.DISABLED)

    def show_plots_window(self, plots_dir):
        """Add plot tabs to the main notebook"""
        import glob

        # Remove existing plot tabs (keep Session Generation at index 0, Session Games
        # at index 1 if it exists, and Games Editor if it exists)
        games_editor_exists = False
        session_games_exists = False
        for i, tab_id in enumerate(self.main_notebook.tabs()):
            tab_text = self.main_notebook.tab(tab_id, "text")
            if tab_text == "Games Editor":
                games_editor_exists = True
            if tab_text == "Session Games":
                session_games_exists = True

        # Keep: Session Generation (always), Session Games (if present), Games Editor (if present)
        num_tabs_to_keep = 1 + int(session_games_exists) + int(games_editor_exists)
        while len(self.main_notebook.tabs()) > num_tabs_to_keep:
            self.main_notebook.forget(num_tabs_to_keep)

        # Find all PNG files in the plots directory
        png_files = glob.glob(os.path.join(plots_dir, "*.png"))

        if not png_files:
            print("No plot files found to display.")
            return

        # Create a tab for each PNG file
        for png_file in sorted(png_files):
            # Get filename without path and extension for tab label
            filename = os.path.basename(png_file)
            tab_name = os.path.splitext(filename)[0].replace("_", " ").title()

            # Create frame for this tab
            tab_frame = tk.Frame(self.main_notebook, bg=self.colors["bg_light"])
            self.main_notebook.add(tab_frame, text=tab_name)

            # Add centered title at the top
            title_label = tk.Label(
                tab_frame,
                text=tab_name,
                font=self.fonts["big"],
                fg=self.colors["accent_red"],
                bg=self.colors["bg_light"],
            )
            title_label.pack(side=tk.TOP, pady=(20, 10))

            # Create canvas with scrollbars for the image
            canvas = tk.Canvas(tab_frame, bg=self.colors["bg_light"])
            h_scrollbar = tk.Scrollbar(
                tab_frame, orient=tk.HORIZONTAL, command=canvas.xview
            )
            v_scrollbar = tk.Scrollbar(
                tab_frame, orient=tk.VERTICAL, command=canvas.yview
            )

            canvas.configure(
                xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set
            )

            # Pack scrollbars and canvas
            h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
            v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

            # Initialize zoom level
            canvas.zoom_level = 1.0
            canvas.auto_fit_width = True

            # Load and display image
            try:
                img = Image.open(png_file)

                # Store original image for resizing
                canvas.original_image = img
                canvas.png_file = png_file

                # Create functions with proper closure (wrapping in a factory function)
                def make_image_functions(cnv):
                    def fit_to_width():
                        try:
                            canvas_width = cnv.winfo_width()
                            if canvas_width <= 1:
                                return

                            original_width, _ = cnv.original_image.size
                            # Small margin so image does not touch edges
                            cnv.zoom_level = max(
                                (canvas_width - 20) / original_width, 0.1
                            )
                        except Exception:
                            pass

                    # Function to update image with current zoom level
                    def update_image():
                        try:
                            # Get canvas dimensions
                            canvas_width = cnv.winfo_width()
                            canvas_height = cnv.winfo_height()

                            if canvas_width <= 1 or canvas_height <= 1:
                                return

                            # Calculate new dimensions maintaining aspect ratio
                            original_width, original_height = cnv.original_image.size

                            # Apply zoom
                            new_width = int(original_width * cnv.zoom_level)
                            new_height = int(original_height * cnv.zoom_level)

                            # Resize image
                            resized_img = cnv.original_image.resize(
                                (new_width, new_height), Image.Resampling.LANCZOS
                            )
                            photo = ImageTk.PhotoImage(resized_img)

                            # Update canvas - center the image
                            cnv.delete("all")

                            # Calculate position to center the image
                            x_pos = max(0, (canvas_width - new_width) // 2)
                            y_pos = max(0, (canvas_height - new_height) // 2)

                            cnv.create_image(x_pos, y_pos, anchor=tk.NW, image=photo)
                            cnv.image = photo  # Keep a reference

                            # Configure scroll region to allow scrolling if image is larger than canvas
                            scroll_x0 = min(0, x_pos)
                            scroll_y0 = min(0, y_pos)
                            scroll_x1 = max(canvas_width, x_pos + new_width)
                            scroll_y1 = max(canvas_height, y_pos + new_height)
                            cnv.configure(
                                scrollregion=(
                                    scroll_x0,
                                    scroll_y0,
                                    scroll_x1,
                                    scroll_y1,
                                )
                            )
                        except Exception as e:
                            print(f"Error updating image: {e}")

                    # Function to resize and display image to fit canvas height
                    def resize_image(event):
                        if getattr(cnv, "auto_fit_width", False):
                            fit_to_width()
                        update_image()

                    # Zoom in function
                    def zoom_in():
                        cnv.auto_fit_width = False
                        cnv.zoom_level = min(cnv.zoom_level * 1.2, 5.0)  # Max 500%
                        update_image()

                    # Zoom out function
                    def zoom_out():
                        cnv.auto_fit_width = False
                        cnv.zoom_level = max(cnv.zoom_level / 1.2, 0.1)  # Min 10%
                        update_image()

                    return update_image, resize_image, zoom_in, zoom_out

                # Create the functions for this specific canvas
                update_image, resize_image, zoom_in, zoom_out = make_image_functions(
                    canvas
                )

                # Bind canvas resize event
                canvas.bind("<Configure>", resize_image)

                # Fit to width initially - with better timing and proper closure
                def make_fit_function(cnv, update_func):
                    def fit_to_width_on_load():
                        # Wait for the canvas to be fully rendered
                        cnv.update_idletasks()
                        canvas_width = cnv.winfo_width()

                        # If canvas isn't rendered yet, try again
                        if canvas_width <= 1:
                            cnv.after(50, fit_to_width_on_load)
                            return

                        original_width, _ = cnv.original_image.size
                        # Subtract a small margin to ensure it fills the available horizontal area
                        cnv.zoom_level = max((canvas_width - 20) / original_width, 0.1)
                        update_func()

                    return fit_to_width_on_load

                fit_to_width_on_load = make_fit_function(canvas, update_image)

                # Schedule fit to width after window is drawn with multiple attempts
                canvas.after(2, fit_to_width_on_load)

                # Bind mouse wheel for zooming (with Ctrl key) - with proper closure
                def make_mousewheel_functions(cnv, zoom_in_func, zoom_out_func):
                    def on_mousewheel_zoom(event):
                        if event.state & 0x0004:  # Ctrl key is pressed
                            if event.delta > 0:
                                zoom_in_func()
                            else:
                                zoom_out_func()
                            return "break"
                        else:
                            # Regular scroll (vertical)
                            cnv.yview_scroll(int(-1 * (event.delta / 120)), "units")

                    def on_shift_mousewheel(event):
                        if event.state & 0x0001:  # Shift key is pressed
                            cnv.xview_scroll(int(-1 * (event.delta / 120)), "units")
                            return "break"

                    return on_mousewheel_zoom, on_shift_mousewheel

                on_mousewheel_zoom, on_shift_mousewheel = make_mousewheel_functions(
                    canvas, zoom_in, zoom_out
                )

                canvas.bind("<MouseWheel>", on_mousewheel_zoom)
                canvas.bind("<Shift-MouseWheel>", on_shift_mousewheel)

            except Exception as e:
                # If image loading fails, show error message
                error_label = tk.Label(
                    tab_frame,
                    text=f"Error loading image:\n{str(e)}",
                    font=self.fonts["normal"],
                    fg="red",
                    bg=self.colors["bg_light"],
                )
                error_label.pack(expand=True)

        print(f"Added {len(png_files)} plot tabs to main window.")

    def show_session_games_tab(self, png_path: str):
        """Display the Session Games overview PNG in a dedicated tab."""
        # Remove any existing "Session Games" tab
        for tab_id in list(self.main_notebook.tabs()):
            if self.main_notebook.tab(tab_id, "text") == "Session Games":
                self.main_notebook.forget(tab_id)
                break

        # Create the tab frame
        tab_frame = tk.Frame(self.main_notebook, bg=self.colors["bg_light"])
        self.main_notebook.add(tab_frame, text="Session Games")

        # Move to position 2 (after Session Generation at 0 and Games Editor at 1)
        num_tabs = len(self.main_notebook.tabs())
        if num_tabs > 1:
            self.main_notebook.insert(2, tab_frame)

        # Do NOT select this tab — Games Editor stays focused after generation

        # Canvas + scrollbars (same pattern as show_plots_window)
        canvas = tk.Canvas(tab_frame, bg=self.colors["bg_light"])
        h_scrollbar = tk.Scrollbar(
            tab_frame, orient=tk.HORIZONTAL, command=canvas.xview
        )
        v_scrollbar = tk.Scrollbar(tab_frame, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)

        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        canvas.zoom_level = 1.0
        canvas.auto_fit_height = True

        try:
            img = Image.open(png_path)
            canvas.original_image = img

            def make_image_functions(cnv):
                def fit_to_height():
                    try:
                        ch = cnv.winfo_height()
                        if ch <= 1:
                            return
                        _, orig_h = cnv.original_image.size
                        cnv.zoom_level = max((ch - 20) / orig_h, 0.1)
                    except Exception:
                        pass

                def update_image():
                    try:
                        cw = cnv.winfo_width()
                        ch = cnv.winfo_height()
                        if cw <= 1 or ch <= 1:
                            return
                        ow, oh = cnv.original_image.size
                        nw = int(ow * cnv.zoom_level)
                        nh = int(oh * cnv.zoom_level)
                        resized = cnv.original_image.resize(
                            (nw, nh), Image.Resampling.LANCZOS
                        )
                        photo = ImageTk.PhotoImage(resized)
                        cnv.delete("all")
                        xp = max(0, (cw - nw) // 2)
                        yp = max(0, (ch - nh) // 2)
                        cnv.create_image(xp, yp, anchor=tk.NW, image=photo)
                        cnv.image = photo
                        cnv.configure(
                            scrollregion=(
                                min(0, xp),
                                min(0, yp),
                                max(cw, xp + nw),
                                max(ch, yp + nh),
                            )
                        )
                    except Exception as e:
                        print(f"Session Games tab: error updating image: {e}")

                def resize_image(event):
                    if getattr(cnv, "auto_fit_height", False):
                        fit_to_height()
                    update_image()

                def zoom_in():
                    cnv.auto_fit_height = False
                    cnv.zoom_level = min(cnv.zoom_level * 1.2, 5.0)
                    update_image()

                def zoom_out():
                    cnv.auto_fit_height = False
                    cnv.zoom_level = max(cnv.zoom_level / 1.2, 0.1)
                    update_image()

                return update_image, resize_image, zoom_in, zoom_out

            update_image, resize_image, zoom_in, zoom_out = make_image_functions(canvas)

            canvas.bind("<Configure>", resize_image)

            def make_fit_fn(cnv, upd_fn):
                def _fit():
                    cnv.update_idletasks()
                    if cnv.winfo_height() <= 1:
                        cnv.after(50, _fit)
                        return
                    _, oh = cnv.original_image.size
                    cnv.zoom_level = max((cnv.winfo_height() - 20) / oh, 0.1)
                    upd_fn()

                return _fit

            canvas.after(2, make_fit_fn(canvas, update_image))

            def make_wheel_fns(cnv, zi, zo):
                def _wheel(event):
                    if event.state & 0x0004:
                        zi() if event.delta > 0 else zo()
                        return "break"
                    cnv.yview_scroll(int(-1 * (event.delta / 120)), "units")

                def _shift_wheel(event):
                    if event.state & 0x0001:
                        cnv.xview_scroll(int(-1 * (event.delta / 120)), "units")
                        return "break"

                return _wheel, _shift_wheel

            _wheel, _shift_wheel = make_wheel_fns(canvas, zoom_in, zoom_out)
            canvas.bind("<MouseWheel>", _wheel)
            canvas.bind("<Shift-MouseWheel>", _shift_wheel)

        except Exception as e:
            tk.Label(
                tab_frame,
                text=f"Error loading Session Games image:\n{e}",
                font=self.fonts["normal"],
                fg="red",
                bg=self.colors["bg_light"],
            ).pack(expand=True)

        self.session_games_png_path = png_path

    def show_games_editor(self):
        """Create interactive games editor tab where users can swap players"""
        if not hasattr(self, "session_of_rounds") or self.session_of_rounds is None:
            print("No session available to edit.")
            return

        # Compact sizing for this tab so 4 rounds can fit horizontally.
        self.games_editor_button_font = self._scaled_font_tuple(
            self.fonts["small"], 0.85
        )
        self.games_editor_player_button_font = self._scaled_font_tuple(
            self.fonts["small"], 0.8
        )
        self.games_editor_vs_font = self._scaled_font_tuple(
            self.fonts["small_bold"], 0.78
        )

        # Check if Games Editor tab already exists
        for tab_id in self.main_notebook.tabs():
            if self.main_notebook.tab(tab_id, "text") == "Games Editor":
                # Tab exists, remove it first so we can recreate it with fresh data
                self.main_notebook.forget(tab_id)
                break

        # Create "Games Editor" tab
        editor_tab = tk.Frame(self.main_notebook, bg=self.colors["bg_dark"])

        # Add the tab (it will be added after existing tabs)
        # Then we can select it to make it visible
        self.main_notebook.add(editor_tab, text="Games Editor")

        # Move it to position 1 (right after Session Generation at position 0)
        num_tabs = len(self.main_notebook.tabs())
        if num_tabs > 1:
            # Move the last tab (just added) to position 1
            last_tab_index = num_tabs - 1
            if last_tab_index > 1:
                # There are other tabs, need to reorder
                tab_id = self.main_notebook.tabs()[last_tab_index]
                # Remove and reinsert at position 1
                self.main_notebook.forget(last_tab_index)
                self.main_notebook.insert(1, editor_tab, text="Games Editor")

        # Header frame for title (centered, matching Session Generation tab)
        header_frame = tk.Frame(editor_tab, bg=self.colors["bg_dark"])
        header_frame.pack(side=tk.TOP, pady=(10, 10))

        # Title container to center the title
        title_container = tk.Frame(header_frame, bg=self.colors["bg_dark"])
        title_container.pack()

        # Add title
        title_label = tk.Label(
            title_container,
            text="INTERACTIVE GAMES EDITOR",
            font=self.fonts["huge"],
            fg=self.colors["accent_yellow"],
            bg=self.colors["bg_dark"],
        )
        title_label.pack()

        # Instructions and status in a separate frame
        info_frame = tk.Frame(editor_tab, bg=self.colors["bg_dark"])
        info_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10), padx=20)

        # Instructions
        instructions = tk.Label(
            info_frame,
            text="Click on two players to swap their positions. Selected players are highlighted in yellow.",
            font=self.fonts["normal"],
            fg=self.colors["text_light"],
            bg=self.colors["bg_dark"],
        )
        instructions.pack(side=tk.TOP, pady=(0, 5))

        # Changes display frame (scrollable list of swaps)
        changes_container = tk.Frame(info_frame, bg=self.colors["bg_dark"])
        changes_container.pack(side=tk.TOP, fill=tk.X, pady=(10, 5))

        changes_label = tk.Label(
            changes_container,
            text="Pending Changes:",
            font=self.fonts["small_bold"],
            fg=self.colors["text_light"],
            bg=self.colors["bg_dark"],
        )
        changes_label.pack(side=tk.TOP, anchor=tk.W)

        # Frame to hold the list of changes
        self.changes_list_frame = tk.Frame(
            changes_container, bg=self.colors["bg_light"], relief=tk.RIDGE, bd=1
        )
        self.changes_list_frame.pack(side=tk.TOP, fill=tk.X, pady=(5, 0))

        # Initially show "No changes" message
        self.no_changes_label = tk.Label(
            self.changes_list_frame,
            text="No changes yet",
            font=self.fonts["small"],
            fg="#888888",
            bg=self.colors["bg_light"],
        )
        self.no_changes_label.pack(pady=5)

        # Status label
        self.status_label = tk.Label(
            info_frame,
            text="No changes pending",
            font=self.fonts["normal"],
            fg=self.colors["text_light"],
            bg=self.colors["bg_dark"],
        )
        self.status_label.pack(side=tk.TOP, pady=(5, 0))

        # Track pending changes
        self.pending_changes = []
        self.swap_history = []  # Track swaps for undo functionality

        # --- Score history (initial + after each Apply) ---
        try:
            _lw = float(self.lambda_weight_var.get())
        except Exception:
            _lw = 2.4
        import numpy as _np

        _h = [p.happiness for p in self.session_of_rounds.players]
        _initial_score = float(_np.mean(_h) - _lw * _np.std(_h))
        self.score_history = [_initial_score]
        self._score_history_lambda = _lw

        # Buttons frame (part of editor tab) - matching Session Generation layout
        # Pack this BEFORE canvas so it stays at the bottom
        button_frame = tk.Frame(editor_tab, bg=self.colors["bg_dark"])
        button_frame.pack(side=tk.BOTTOM, pady=15, padx=20)

        # Score history strip — just above buttons
        score_history_outer = tk.Frame(editor_tab, bg=self.colors["bg_dark"])
        score_history_outer.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(0, 4))
        tk.Label(
            score_history_outer,
            text="Score history  (mean − λ·std):",
            font=self.fonts["small_bold"],
            fg=self.colors["text_light"],
            bg=self.colors["bg_dark"],
        ).pack(side=tk.LEFT, padx=(0, 8))
        self.score_history_container = tk.Frame(
            score_history_outer, bg=self.colors["bg_dark"]
        )
        self.score_history_container.pack(side=tk.LEFT, fill=tk.X)
        self._render_score_history()

        # Custom button style
        btn_config = {
            "font": self.games_editor_button_font,
            "relief": tk.FLAT,
            "cursor": "hand2",
            "padx": 12,
            "pady": 6,
        }

        # Undo button
        self.undo_button = tk.Button(
            button_frame,
            text="Undo Last Swap",
            command=self.undo_last_swap,
            bg=self.colors["bg_light"],
            fg=self.colors["text_dark"],
            state=tk.DISABLED,
            **btn_config,
        )
        self.undo_button.grid(row=0, column=0, padx=5)

        # Apply button - highlighted with yellow (matching Run Session button)
        self.apply_button = tk.Button(
            button_frame,
            text="⚡ APPLY CHANGES & RECALCULATE ⚡",
            command=self.apply_changes,
            bg=self.colors["accent_yellow"],
            fg=self.colors["text_dark"],
            font=self.games_editor_button_font,
            relief=tk.FLAT,
            cursor="hand2",
            padx=14,
            pady=6,
        )
        self.apply_button.grid(row=0, column=1, padx=10)

        # Create scrollable area (pack AFTER button_frame so it fills remaining space)
        canvas = tk.Canvas(editor_tab, bg=self.colors["bg_dark"])
        v_scrollbar = tk.Scrollbar(editor_tab, orient=tk.VERTICAL, command=canvas.yview)
        h_scrollbar = tk.Scrollbar(
            editor_tab, orient=tk.HORIZONTAL, command=canvas.xview
        )
        scrollable_frame = tk.Frame(canvas, bg=self.colors["bg_dark"])

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Track selected players for swapping
        self.selected_for_swap = []

        # Mapping for player buttons in the games editor UI
        # Keyed by (round_idx, game_idx, team_id, row, col) -> button
        self.game_player_buttons = {}

        # Mapping for level-diff labels above VS: (round_idx, game_idx) -> Label
        self.game_level_diff_labels = {}

        # Mapping for team frames: (round_idx, game_idx, team_id) -> (outer_frame, inner_frame)
        self.game_team_frames = {}

        # Create rounds container with columns
        num_rounds = len(self.session_of_rounds.rounds)
        rounds_container = tk.Frame(scrollable_frame, bg=self.colors["bg_dark"])
        rounds_container.pack(expand=True, fill=tk.BOTH, padx=4, pady=6)

        # Configure columns to have equal weight
        for col_idx in range(num_rounds):
            rounds_container.columnconfigure(col_idx, weight=1, uniform="round")

        # Display each round in a column
        for round_idx, game_round in enumerate(self.session_of_rounds.rounds):
            # Round column
            round_column = tk.Frame(
                rounds_container, bg=self.colors["bg_light"], relief=tk.RIDGE, bd=2
            )
            round_column.grid(
                row=0, column=round_idx, sticky=(tk.N, tk.S, tk.E, tk.W), padx=2
            )

            # Round header
            round_header = tk.Frame(round_column, bg=self.colors["accent_red"], pady=6)
            round_header.pack(fill=tk.X, pady=(0, 10))

            round_label = tk.Label(
                round_header,
                text=f"ROUND {round_idx + 1}",
                font=self.fonts["big"],
                fg=self.colors["text_light"],
                bg=self.colors["accent_red"],
            )
            round_label.pack()

            # Games section
            games_frame = tk.Frame(round_column, bg=self.colors["bg_light"])
            games_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

            for game_idx, game in enumerate(game_round.games):
                # Game frame
                game_frame = tk.Frame(games_frame, bg="#F0F0F0", relief=tk.RAISED, bd=2)
                game_frame.pack(fill=tk.X, pady=3, padx=3)

                game_title = tk.Label(
                    game_frame,
                    text=f"Game {game_idx + 1}",
                    font=self.games_editor_button_font,
                    fg=self.colors["accent_red"],
                    bg="#F0F0F0",
                )
                game_title.pack(pady=(6, 1))

                # Game type subtitle (type_preference + gender_preference)
                type_str = (game.type_preference or "open").capitalize()
                gender_str = (game.gender_preference or "open").capitalize()
                game_type_label = tk.Label(
                    game_frame,
                    text=f"{type_str}  |  {gender_str}",
                    font=(
                        self.games_editor_button_font[0],
                        max(7, self.games_editor_button_font[1] - 1),
                        "italic",
                    ),
                    fg="#555555",
                    bg="#F0F0F0",
                    anchor="center",
                    justify="center",
                )
                game_type_label.pack(pady=(0, 4), fill=tk.X)

                # Teams container
                teams_container = tk.Frame(game_frame, bg="#F0F0F0")
                teams_container.pack(pady=(0, 6))

                # Team A
                team_a_bg = self._team_pair_bg(round_idx, game_idx, "A")
                team_a_frame = tk.Frame(
                    teams_container, bg=team_a_bg, relief=tk.GROOVE, bd=2
                )
                team_a_frame.grid(row=0, column=0, padx=4, pady=3, sticky=tk.NSEW)

                # Create horizontal layout for Team A players
                team_a_players_frame = tk.Frame(team_a_frame, bg=team_a_bg)
                team_a_players_frame.pack(padx=3, pady=3)
                self.game_team_frames[(round_idx, game_idx, "A")] = (
                    team_a_frame,
                    team_a_players_frame,
                )

                for col_idx, player in enumerate(game.team_A.players):
                    self.create_player_button_grid(
                        team_a_players_frame,
                        player,
                        round_idx,
                        game_idx,
                        "A",
                        0,
                        col_idx,
                    )

                # VS label with level diff above it
                vs_container = tk.Frame(teams_container, bg="#F0F0F0")
                vs_container.grid(row=0, column=1, padx=2)

                level_diff = game.team_A.mean_level - game.team_B.mean_level
                diff_text = (
                    f"+{level_diff:.1f}" if level_diff > 0 else f"{level_diff:.1f}"
                )
                diff_color = "#2255AA" if level_diff >= 0 else "#AA2222"
                diff_label = tk.Label(
                    vs_container,
                    text=diff_text,
                    font=(
                        self.games_editor_vs_font[0],
                        max(7, self.games_editor_vs_font[1] - 4),
                    ),
                    fg=diff_color,
                    bg="#F0F0F0",
                )
                diff_label.pack()
                self.game_level_diff_labels[(round_idx, game_idx)] = diff_label
                vs_label = tk.Label(
                    vs_container,
                    text="VS",
                    font=self.games_editor_vs_font,
                    fg=self.colors["accent_red"],
                    bg="#F0F0F0",
                )
                vs_label.pack()

                # Team B
                team_b_bg = self._team_pair_bg(round_idx, game_idx, "B")
                team_b_frame = tk.Frame(
                    teams_container, bg=team_b_bg, relief=tk.GROOVE, bd=2
                )
                team_b_frame.grid(row=0, column=2, padx=4, pady=3, sticky=tk.NSEW)

                # Create horizontal layout for Team B players
                team_b_players_frame = tk.Frame(team_b_frame, bg=team_b_bg)
                team_b_players_frame.pack(padx=3, pady=3)
                self.game_team_frames[(round_idx, game_idx, "B")] = (
                    team_b_frame,
                    team_b_players_frame,
                )

                for col_idx, player in enumerate(game.team_B.players):
                    self.create_player_button_grid(
                        team_b_players_frame,
                        player,
                        round_idx,
                        game_idx,
                        "B",
                        0,
                        col_idx,
                    )

            # Not playing section
            if game_round.not_playing:
                not_playing_frame = tk.Frame(
                    round_column, bg="#FFF8DC", relief=tk.RIDGE, bd=2
                )
                not_playing_frame.pack(fill=tk.X, pady=(0, 6))

                not_playing_label = tk.Label(
                    not_playing_frame,
                    text="Not Playing:",
                    font=self.games_editor_button_font,
                    fg=self.colors["text_dark"],
                    bg="#FFF8DC",
                )
                not_playing_label.pack(pady=(3, 0))

                # Create a grid container for 2 columns
                not_playing_grid = tk.Frame(not_playing_frame, bg="#FFF8DC")
                not_playing_grid.pack(pady=(0, 3))

                # Place players in 4 columns
                for idx, player in enumerate(game_round.not_playing):
                    row = idx // 4
                    col = idx % 4
                    player_btn = self.create_player_button_grid(
                        not_playing_grid,
                        player,
                        round_idx,
                        None,
                        "not_playing",
                        row,
                        col,
                    )

        # Bind mouse wheel for scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def on_shift_mousewheel(event):
            canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

        # Use enter/leave on the scrollable frame to set the mousewheel target for the games editor
        def _on_editor_enter(event):
            self._mousewheel_target_canvas = canvas

        def _on_editor_leave(event):
            if getattr(self, "_mousewheel_target_canvas", None) == canvas:
                self._mousewheel_target_canvas = None

        scrollable_frame.bind("<Enter>", _on_editor_enter)
        scrollable_frame.bind("<Leave>", _on_editor_leave)

        # Switch to the Games Editor tab
        self.main_notebook.select(editor_tab)

    def create_player_button(self, parent, player, round_idx, game_idx, team_id):
        """Create a clickable player button for swapping"""
        player_info = {
            "player": player,
            "round_idx": round_idx,
            "game_idx": game_idx,
            "team_id": team_id,
        }

        btn = tk.Button(
            parent,
            text=f"{player.name}\n(Lvl {player.level})",
            font=getattr(self, "games_editor_player_button_font", self.fonts["small"]),
            bg=self.colors["bg_light"],
            fg=self.colors["text_dark"],
            relief=tk.RAISED,
            padx=6,
            pady=3,
            cursor="hand2",
            command=lambda: self.toggle_player_selection(btn, player_info),
        )
        btn.pack(padx=3, pady=2)
        # Attach the mutable player_info dict to the button so it can be
        # updated when swaps/undo happen and refresh routines can keep
        # closures in sync with the underlying data model.
        try:
            btn._player_info = player_info
        except Exception:
            pass

    def create_player_button_grid(
        self, parent, player, round_idx, game_idx, team_id, row, col
    ):
        """Create a clickable player button for swapping in a grid layout"""
        player_info = {
            "player": player,
            "round_idx": round_idx,
            "game_idx": game_idx,
            "team_id": team_id,
        }

        btn = tk.Button(
            parent,
            text=f"{player.name}\n(Lvl {player.level})",
            font=getattr(self, "games_editor_player_button_font", self.fonts["small"]),
            bg=self.colors["bg_light"],
            fg=self.colors["text_dark"],
            relief=tk.RAISED,
            padx=6,
            pady=3,
            cursor="hand2",
            command=lambda: self.toggle_player_selection(btn, player_info),
        )
        btn.grid(row=row, column=col, padx=2, pady=2, sticky=tk.EW)

        # Store button reference so we can refresh labels when swaps/undo happen
        try:
            key = (round_idx, game_idx, team_id, row, col)
            self.game_player_buttons[key] = btn
        except Exception:
            # If mapping isn't available (called outside games editor), ignore
            pass
        # Also attach the player_info to the button for later refresh
        try:
            btn._player_info = player_info
        except Exception:
            pass
        return btn

    def refresh_round_ui(self, round_idx):
        """Refresh the visible buttons for a specific round based on data model."""
        if not hasattr(self, "session_of_rounds") or self.session_of_rounds is None:
            return

        try:
            game_round = self.session_of_rounds.rounds[round_idx]
        except Exception:
            return

        # Update games
        for game_idx, game in enumerate(game_round.games):
            # Team A
            for col_idx, player in enumerate(game.team_A.players):
                key = (round_idx, game_idx, "A", 0, col_idx)
                btn = self.game_player_buttons.get(key)
                if btn:
                    btn.config(
                        text=f"{player.name}\n(Lvl {player.level})",
                        bg=self.colors["bg_light"],
                        relief=tk.RAISED,
                    )

            # Team B
            for col_idx, player in enumerate(game.team_B.players):
                key = (round_idx, game_idx, "B", 0, col_idx)
                btn = self.game_player_buttons.get(key)
                if btn:
                    btn.config(
                        text=f"{player.name}\n(Lvl {player.level})",
                        bg=self.colors["bg_light"],
                        relief=tk.RAISED,
                    )

            # Refresh team frame colours
            self._refresh_team_frame_colors(round_idx, game_idx)

        # Update not playing
        if game_round.not_playing:
            for idx, player in enumerate(game_round.not_playing):
                row = idx // 4
                col = idx % 4
                key = (round_idx, None, "not_playing", row, col)
                btn = self.game_player_buttons.get(key)
                if btn:
                    btn.config(
                        text=f"{player.name}\n(Lvl {player.level})",
                        bg=self.colors["bg_light"],
                        relief=tk.RAISED,
                    )

    def refresh_all_rounds(self):
        """Refresh all stored game buttons from the session data.

        This is more robust than refreshing a single round because keys may
        not map perfectly in some edge cases; iterating stored buttons ensures
        visible labels match the underlying data model.
        """
        if not hasattr(self, "session_of_rounds") or self.session_of_rounds is None:
            return

        for key, btn in list(self.game_player_buttons.items()):
            try:
                round_idx, game_idx, team_id, row, col = key
                game_round = self.session_of_rounds.rounds[round_idx]

                if team_id == "not_playing":
                    index = row * 4 + col
                    player = game_round.not_playing[index]
                else:
                    # game_idx should be int
                    game = game_round.games[game_idx]
                    if team_id == "A":
                        player = game.team_A.players[col]
                    elif team_id == "B":
                        player = game.team_B.players[col]
                    else:
                        continue

                btn.config(
                    text=f"{player.name}\n(Lvl {player.level})",
                    bg=self.colors["bg_light"],
                    relief=tk.RAISED,
                )
                # use the correct player object
                try:
                    if hasattr(btn, "_player_info") and isinstance(
                        btn._player_info, dict
                    ):
                        btn._player_info["player"] = player
                except Exception:
                    pass
            except Exception:
                # If any mapping/indexing fails, skip updating that button
                continue

        # Refresh all team frame colours
        seen_games = set()
        for round_idx, game_idx, team_id, _row, _col in list(
            self.game_player_buttons.keys()
        ):
            if team_id != "not_playing" and game_idx is not None:
                key = (round_idx, game_idx)
                if key not in seen_games:
                    seen_games.add(key)
                    self._refresh_team_frame_colors(round_idx, game_idx)

    def _team_pair_bg(self, round_idx, game_idx, team_id):
        """Return gold if this team contains a preferred pair, else the normal team color."""
        GOLD = "#FFD700"
        normal = "#D0E8FF" if team_id == "A" else "#FFE0E0"
        if (
            not self.preferred_pairs
            or game_idx is None
            or not hasattr(self, "session_of_rounds")
            or self.session_of_rounds is None
        ):
            return normal
        try:
            game = self.session_of_rounds.rounds[round_idx].games[game_idx]
            team_names = (
                {p.name for p in game.team_A.players}
                if team_id == "A"
                else {p.name for p in game.team_B.players}
            )
            for pair_fs, _ in self.preferred_pairs:
                if pair_fs.issubset(team_names):
                    return GOLD
        except Exception:
            pass
        return normal

    def _refresh_team_frame_colors(self, round_idx, game_idx):
        """Update the background colour of both team frames for a given game."""
        for team_id in ("A", "B"):
            frames = self.game_team_frames.get((round_idx, game_idx, team_id))
            if frames is None:
                continue
            outer, inner = frames
            bg = self._team_pair_bg(round_idx, game_idx, team_id)
            try:
                outer.config(bg=bg)
                inner.config(bg=bg)
            except Exception:
                pass

    def toggle_player_selection(self, button, player_info):
        """Toggle player selection for swapping"""
        # Check if this player is already selected
        for idx, (btn, info) in enumerate(self.selected_for_swap):
            if info["player"].name == player_info["player"].name:
                # Deselect
                btn.config(bg=self.colors["bg_light"], relief=tk.RAISED)
                self.selected_for_swap.pop(idx)
                return

        # Select this player
        button.config(bg=self.colors["accent_yellow"], relief=tk.SUNKEN)
        self.selected_for_swap.append((button, player_info))

        # If two players are selected, perform swap
        if len(self.selected_for_swap) == 2:
            self.swap_players()

    def swap_players(self):
        """Swap two selected players"""
        if len(self.selected_for_swap) != 2:
            return

        btn1, info1 = self.selected_for_swap[0]
        btn2, info2 = self.selected_for_swap[1]

        player1 = info1["player"]
        player2 = info2["player"]

        # Check if they're in the same round
        if info1["round_idx"] != info2["round_idx"]:
            messagebox.showwarning(
                "Invalid Swap", "Can only swap players within the same round!"
            )
            # Deselect both
            btn1.config(bg=self.colors["bg_light"], relief=tk.RAISED)
            btn2.config(bg=self.colors["bg_light"], relief=tk.RAISED)
            self.selected_for_swap.clear()
            return

        round_idx = info1["round_idx"]
        game_round = self.session_of_rounds.rounds[round_idx]

        # Find positions of both players
        pos1 = game_round.find_player_position(player1)
        pos2 = game_round.find_player_position(player2)

        if pos1 is None or pos2 is None:
            messagebox.showerror("Error", "Could not find player positions!")
            self.selected_for_swap.clear()
            return

        # Perform the swap in the data structure
        game_round.swap_player_positions(pos1, pos2)

        # Track this change in pending changes
        self.pending_changes.append(
            {"round_idx": round_idx, "player1": player1.name, "player2": player2.name}
        )

        # Track in swap history for undo
        self.swap_history.append(
            {"round_idx": round_idx, "player1": player1, "player2": player2}
        )

        # Enable undo button
        self.undo_button.config(state=tk.NORMAL)

        # Update button labels
        btn1.config(
            text=f"{player2.name}\n(Lvl {player2.level})",
            bg=self.colors["bg_light"],
            relief=tk.RAISED,
        )
        btn2.config(
            text=f"{player1.name}\n(Lvl {player1.level})",
            bg=self.colors["bg_light"],
            relief=tk.RAISED,
        )

        # Update the player info references
        info1["player"] = player2
        info2["player"] = player1

        # Clear selection
        self.selected_for_swap.clear()

        # Refresh level diff labels and team frame colours for the affected games
        self._refresh_level_diff_labels(round_idx)
        self._refresh_team_frame_colors(round_idx, info1["game_idx"])
        if info2["game_idx"] != info1["game_idx"]:
            self._refresh_team_frame_colors(round_idx, info2["game_idx"])

        # Update changes display
        self.update_changes_display()

        # Update status
        self.status_label.config(
            text=f"{len(self.pending_changes)} change(s) pending - Click Apply to recalculate happiness",
            fg=self.colors["accent_yellow"],
        )

        print(
            f"Swapped {player1.name} and {player2.name} in Round {round_idx + 1} (pending)"
        )

    def _refresh_level_diff_labels(self, round_idx):
        """Update the level-diff labels above VS for every game in the given round."""
        if (
            not hasattr(self, "game_level_diff_labels")
            or self.session_of_rounds is None
        ):
            return
        game_round = self.session_of_rounds.rounds[round_idx]
        for game_idx, game in enumerate(game_round.games):
            diff_label = self.game_level_diff_labels.get((round_idx, game_idx))
            if diff_label is None:
                continue
            level_diff = game.team_A.mean_level - game.team_B.mean_level
            diff_text = f"+{level_diff:.1f}" if level_diff > 0 else f"{level_diff:.1f}"
            diff_color = "#2255AA" if level_diff >= 0 else "#AA2222"
            diff_label.config(text=diff_text, fg=diff_color)

    def _render_score_history(self):
        """Redraw the score history strip inside score_history_container."""
        if not hasattr(self, "score_history_container"):
            return
        for w in self.score_history_container.winfo_children():
            w.destroy()

        YELLOW = self.colors["accent_yellow"]
        GREEN = "#4CAF50"
        RED = "#E53935"
        GRAY = "#BBBBBB"
        BG = self.colors["bg_dark"]

        for i, score in enumerate(self.score_history):
            # Determine colour relative to previous entry
            if i == 0:
                label_text = "Initial"
                box_color = GRAY
                arrow = ""
            else:
                prev = self.score_history[i - 1]
                delta = score - prev
                if delta > 0.009:
                    box_color = GREEN
                    arrow = f"  ▲ +{delta:.2f}"
                elif delta < -0.009:
                    box_color = RED
                    arrow = f"  ▼ {delta:.2f}"
                else:
                    box_color = GRAY
                    arrow = "  ≈ 0"
                label_text = f"Swap {i}"

            cell = tk.Frame(
                self.score_history_container, bg=box_color, relief=tk.RIDGE, bd=1
            )
            cell.pack(side=tk.LEFT, padx=3, pady=2)

            tk.Label(
                cell,
                text=label_text,
                font=(
                    self.fonts["small"][0],
                    max(7, self.fonts["small"][1] - 1),
                    "bold",
                ),
                fg=self.colors["text_dark"],
                bg=box_color,
                padx=6,
                pady=1,
            ).pack()
            tk.Label(
                cell,
                text=f"{score:.3f}",
                font=(self.fonts["small"][0], self.fonts["small"][1], "bold"),
                fg=self.colors["text_dark"],
                bg=box_color,
                padx=6,
                pady=1,
            ).pack()

            if arrow:
                tk.Label(
                    cell,
                    text=arrow,
                    font=(self.fonts["small"][0], max(7, self.fonts["small"][1] - 1)),
                    fg=self.colors["text_dark"],
                    bg=box_color,
                    padx=4,
                    pady=1,
                ).pack()

    def update_changes_display(self):
        """Update the visual display of pending changes"""
        # Clear existing changes display
        for widget in self.changes_list_frame.winfo_children():
            widget.destroy()

        if not self.pending_changes:
            # Show "no changes" message
            self.no_changes_label = tk.Label(
                self.changes_list_frame,
                text="No changes yet",
                font=self.fonts["small"],
                fg="#888888",
                bg=self.colors["bg_light"],
            )
            self.no_changes_label.pack(pady=5)
        else:
            # Show list of changes
            for idx, change in enumerate(self.pending_changes, 1):
                change_text = f"{idx}. Round {change['round_idx'] + 1}: {change['player1']} ↔ {change['player2']}"
                change_label = tk.Label(
                    self.changes_list_frame,
                    text=change_text,
                    font=self.fonts["small"],
                    fg=self.colors["text_dark"],
                    bg=self.colors["bg_light"],
                    anchor=tk.W,
                )
                change_label.pack(anchor=tk.W, padx=10, pady=2)

    def undo_last_swap(self):
        """Undo the last swap operation"""
        if not self.swap_history:
            messagebox.showinfo("Nothing to Undo", "No swaps to undo.")
            return

        # Get the last swap
        last_swap = self.swap_history.pop()
        round_idx = last_swap["round_idx"]
        player1 = last_swap["player1"]
        player2 = last_swap["player2"]

        # Find and remove from pending changes
        for i, change in enumerate(self.pending_changes):
            if (
                change["round_idx"] == round_idx
                and change["player1"] == player1.name
                and change["player2"] == player2.name
            ):
                self.pending_changes.pop(i)
                break

        # Swap the players back
        game_round = self.session_of_rounds.rounds[round_idx]
        pos1 = game_round.find_player_position(player1)
        pos2 = game_round.find_player_position(player2)

        if pos1 and pos2:
            game_round.swap_player_positions(pos1, pos2)

        # Refresh visible UI for this round so button labels reflect the data model
        try:
            # Refresh visible UI. Use the comprehensive refresh to cover all stored buttons.
            self.refresh_all_rounds()
        except Exception:
            # Fallback: still update changes display even if refresh fails
            pass

        # Update changes display
        self.update_changes_display()

        # Update status
        if self.pending_changes:
            self.status_label.config(
                text=f"{len(self.pending_changes)} change(s) pending - Click Apply to recalculate happiness",
                fg=self.colors["accent_yellow"],
            )
        else:
            self.status_label.config(
                text="No pending changes", fg=self.colors["text_dark"]
            )

        # Disable undo button if no more swaps
        if not self.swap_history:
            self.undo_button.config(state=tk.DISABLED)

        print(f"Undid swap: {player1.name} and {player2.name} in Round {round_idx + 1}")

    def apply_changes(self):
        """Apply all pending changes and recalculate happiness for affected rounds"""
        if not self.pending_changes:
            messagebox.showinfo("No Changes", "No pending changes to apply.")
            return

        # Disable the apply button to prevent multiple clicks
        self.apply_button.config(state=tk.DISABLED)

        print("\n" + "=" * 80)
        print(f"APPLYING {len(self.pending_changes)} CHANGES")
        print("=" * 80)

        # Get unique rounds that were modified
        modified_rounds = sorted(
            set(change["round_idx"] for change in self.pending_changes)
        )

        # Apply changes using the SessionOfRounds methods
        print(f"\nRecalculating happiness for {len(modified_rounds)} round(s)...")

        # Check if the method exists (for older session objects)
        if hasattr(self.session_of_rounds, "apply_changes_to_rounds"):
            self.session_of_rounds.apply_changes_to_rounds(modified_rounds)
        else:
            # Fallback: manually recalculate for older session objects
            print("Using fallback recalculation method...")
            for round_idx in modified_rounds:
                print(f"Recalculating happiness for Round {round_idx + 1}...")
                game_round = self.session_of_rounds.rounds[round_idx]

                # Manually call recalculate_happiness if it exists
                if hasattr(game_round, "recalculate_happiness"):
                    game_round.recalculate_happiness(round_idx=round_idx)
                else:
                    messagebox.showerror(
                        "Error",
                        "Your session object is outdated. Please restart the Python kernel and regenerate the session.",
                    )
                    return

            # Recalculate session statistics
            if hasattr(self.session_of_rounds, "recalculate_session_statistics"):
                self.session_of_rounds.recalculate_session_statistics()
            else:
                # Fallback for older sessions
                import numpy as np  # noqa: PLC0415

                self.session_of_rounds.mean_happiness = np.mean(
                    [player.happiness for player in self.session_of_rounds.players]
                )
                self.session_of_rounds.std_happiness = np.std(
                    [player.happiness for player in self.session_of_rounds.players]
                )

        # Clear pending changes and swap history
        num_changes = len(self.pending_changes)
        self.pending_changes.clear()
        self.swap_history.clear()

        # Disable undo button
        self.undo_button.config(state=tk.DISABLED)

        # Update changes display
        self.update_changes_display()

        # Update status - show "Processing..." while regenerating plots
        self.status_label.config(
            text="Processing changes...", fg=self.colors["accent_yellow"]
        )

        print("\n" + "=" * 80)
        print("CHANGES APPLIED - RECALCULATION COMPLETE")
        print(f"New Mean Happiness: {self.session_of_rounds.mean_happiness:.2f}")
        print(f"New Std Happiness: {self.session_of_rounds.std_happiness:.2f}")
        print("=" * 80)

        # Append new score to history and refresh the strip
        try:
            import numpy as _np

            _lw = getattr(self, "_score_history_lambda", 2.4)
            _h = [p.happiness for p in self.session_of_rounds.players]
            _new_score = float(_np.mean(_h) - _lw * _np.std(_h))
            if hasattr(self, "score_history"):
                self.score_history.append(_new_score)
            self._render_score_history()
        except Exception:
            pass

        # Regenerate plots, update XLS and PKL files if they exist
        try:
            sessions_dir = "sessions"
            if os.path.exists(sessions_dir):
                session_folders = [
                    os.path.join(sessions_dir, d)
                    for d in os.listdir(sessions_dir)
                    if os.path.isdir(os.path.join(sessions_dir, d))
                ]
                folders_with_plots = [
                    f
                    for f in session_folders
                    if os.path.exists(os.path.join(f, "plots"))
                ]
                if folders_with_plots:
                    most_recent = max(folders_with_plots, key=os.path.getmtime)
                    plots_dir = os.path.join(most_recent, "plots")
                    session_folder = most_recent

                    print("\nRegenerating plots with updated data...")
                    # Add a clear blank line before heavy chart work
                    print()
                    main_module.create_all_session_charts(
                        self.session_of_rounds, save_png=True, png_dir=plots_dir
                    )

                    # Small pause in console output for readability
                    print()
                    # Refresh plot tabs
                    self.show_plots_window(plots_dir)
                    print("\nPlots regenerated successfully!\n")

                    # Update Excel file with new game data
                    print("\nUpdating Excel file with new data...\n")
                    try:
                        # Find the existing xlsx file in the session folder
                        xlsx_files = [
                            f
                            for f in os.listdir(session_folder)
                            if f.endswith(".xlsx") and not f.endswith("_read_only.xlsx")
                        ]
                        if xlsx_files:
                            xlsx_filename = xlsx_files[0]  # Use the first found
                        else:
                            # Fallback: use default naming if none found
                            folder_name = os.path.basename(session_folder)
                            date_str = folder_name.split("_")[0:3]
                            date_str = "_".join(date_str)
                            xlsx_filename = f"session_{date_str}.xlsx"

                        self.session_of_rounds.export_to_excel(
                            directory=session_folder, filename=xlsx_filename
                        )
                        print(f"Excel file updated successfully as {xlsx_filename}!")
                    except Exception as excel_error:
                        print(f"Warning: Could not update Excel file: {excel_error}")

                    # Update pickle file with new session data
                    print("\nUpdating pickle file with new data...\n")
                    try:
                        from core.pickle_helper import save_session

                        # Extract only the date part (e.g., 18_11_2025) from folder name
                        folder_name = os.path.basename(session_folder)
                        date_str = folder_name.split("_")[0:3]
                        date_str = "_".join(date_str)  # Only day_month_year

                        save_session(
                            self.session_of_rounds,
                            folder=session_folder,
                            filename=f"session_of_rounds_{date_str}_modified.pkl",
                        )
                        print("Pickle file updated successfully!")
                    except Exception as pickle_error:
                        print(f"Warning: Could not update pickle file: {pickle_error}")
        except Exception as e:
            print(f"Warning: Could not regenerate plots: {e}")

        # Update status label after everything is done
        self.status_label.config(
            text="Changes applied successfully!", fg=self.colors["accent_yellow"]
        )

        print("\n" + "=" * 80)
        print("ALL OPERATIONS COMPLETED SUCCESSFULLY")
        print("=" * 80)

        messagebox.showinfo(
            "Success",
            f"Applied {num_changes} change(s) successfully!\n\n"
            f"New Mean Happiness: {self.session_of_rounds.mean_happiness:.2f}\n"
            f"New Std Happiness: {self.session_of_rounds.std_happiness:.2f}\n\n"
            "Session files updated:\n"
            "• Plots regenerated\n"
            "• Excel file updated\n"
            "• Pickle file updated",
        )

        # Re-enable the apply button
        self.apply_button.config(state=tk.NORMAL)

    def create_round_preferences(self):
        """Create or recreate the round preference controls based on num_rounds_var"""
        # Clear existing round frames
        for frame in self.round_frames:
            frame.destroy()
        self.round_frames.clear()
        self.type_prefs.clear()
        self.gender_prefs.clear()
        self.type_buttons_list.clear()
        self.gender_buttons_list.clear()

        num_rounds = self.num_rounds_var.get()

        # Default preferences (cycle through these for any number of rounds)
        type_defaults = ["balanced", "balanced", "level", "level"]
        gender_defaults = ["open", "mixed", "mixed", "open"]

        for i in range(num_rounds):
            round_frame = tk.Frame(self.rounds_container, bg=self.colors["bg_light"])
            round_frame.grid(row=i, column=0, columnspan=5, sticky=(tk.W, tk.E), pady=2)
            self.round_frames.append(round_frame)

            # Round label with burgundy background
            round_label = tk.Label(
                round_frame,
                text=f"Round {i+1}:",
                font=self.fonts["normal_bold"],
                width=10,
                bg=self.colors["accent_red"],
                fg=self.colors["text_light"],
                padx=5,
                pady=3,
            )
            round_label.grid(row=0, column=0, padx=5, sticky=tk.W)

            # Type preference
            type_var = tk.StringVar(value=type_defaults[i % len(type_defaults)])
            self.type_prefs.append(type_var)
            type_section, type_buttons = self._make_toggle_group(
                round_frame, "#E8F4F8", "Type:", ["level", "balanced"], type_var
            )
            type_section.grid(row=0, column=1, padx=10, sticky=tk.W)
            self.type_buttons_list.append(type_buttons)

            # Gender preference
            gender_var = tk.StringVar(value=gender_defaults[i % len(gender_defaults)])
            self.gender_prefs.append(gender_var)
            gender_section, gender_buttons = self._make_toggle_group(
                round_frame, "#F8E8F4", "Gender:", ["open", "mixed"], gender_var
            )
            gender_section.grid(row=0, column=2, padx=10, sticky=tk.W)
            self.gender_buttons_list.append(gender_buttons)

    def toggle_spectrum_switch(self):
        """Toggle Spectrum parameter ON/OFF"""
        self.set_spectrum_state(not bool(self.spectrum_var.get()))

    def set_spectrum_state(self, enabled):
        """Set Spectrum parameter state"""
        self.spectrum_var.set(bool(enabled))
        self.update_spectrum_switch_display()

    def _set_png_levels_state(self, enabled):
        """Set the 'show levels in PNG' toggle state and refresh button display."""
        self.png_show_levels_var.set(bool(enabled))
        if not hasattr(self, "_png_levels_buttons"):
            return
        selected = "on" if enabled else "off"
        for key, btn in self._png_levels_buttons.items():
            if key == selected:
                btn.config(
                    bg=self.colors["accent_yellow"],
                    fg=self.colors["text_dark"],
                    relief=tk.SUNKEN,
                )
            else:
                btn.config(
                    bg=self.colors["bg_light"],
                    fg=self.colors["text_dark"],
                    relief=tk.RAISED,
                )

    def update_spectrum_switch_display(self):
        """Refresh Spectrum ON/OFF button appearances from current state"""
        if not hasattr(self, "spectrum_buttons"):
            return

        selected_key = "on" if bool(self.spectrum_var.get()) else "off"
        for key, btn in self.spectrum_buttons.items():
            if key == selected_key:
                btn.config(
                    bg=self.colors["accent_yellow"],
                    fg=self.colors["text_dark"],
                    relief=tk.SUNKEN,
                )
            else:
                btn.config(
                    bg=self.colors["bg_light"],
                    fg=self.colors["text_dark"],
                    relief=tk.RAISED,
                )

    def increase_rounds(self):
        """Increase the number of rounds"""
        current = self.num_rounds_var.get()
        if current < 10:  # Max 10 rounds
            self.num_rounds_var.set(current + 1)
            self.rounds_label.config(text=str(current + 1))
            self.create_round_preferences()
            # Expand the pane by approximately 30 pixels per round to keep buttons in place
            current_height = self.prefs_frame.winfo_height()
            if current_height > 1:  # Only adjust if widget has been rendered
                self.prefs_frame.config(height=current_height + 30)

    def decrease_rounds(self):
        """Decrease the number of rounds"""
        current = self.num_rounds_var.get()
        if current > 1:  # Min 1 round
            self.num_rounds_var.set(current - 1)
            self.rounds_label.config(text=str(current - 1))
            self.create_round_preferences()
            # Shrink the pane by approximately 30 pixels per round to keep buttons in place
            current_height = self.prefs_frame.winfo_height()
            if current_height > 430:  # Don't shrink below minimum
                self.prefs_frame.config(height=current_height - 30)

    def toggle_player(self, player_name):
        """Toggle player selection when button is clicked"""
        if self.player_button_states[player_name]:
            # Deselect
            self.player_button_states[player_name] = False
            self.player_buttons[player_name].config(
                bg=self.colors["bg_light"],
                fg=self.colors["text_dark"],
                relief=tk.RAISED,
            )
            self.selected_players.remove(player_name)
        else:
            # Select
            self.player_button_states[player_name] = True
            self.player_buttons[player_name].config(
                bg=self.colors["accent_yellow"],
                fg=self.colors["text_dark"],
                relief=tk.SUNKEN,
            )
            self.selected_players.append(player_name)

        # Update count label and info display
        self._update_count_label()
        self.update_info_display()

    def _update_count_label(self):
        """Update the count label with total, male and female counts."""
        n = len(self.selected_players)
        if n > 0 and "Gender" in self.main_df.columns:
            genders = [
                self.player_overrides.get(p, {}).get(
                    "Gender", self.main_df.at[p, "Gender"]
                )
                for p in self.selected_players
                if p in self.main_df.index
            ]
            n_male = sum(1 for g in genders if g == "Male")
            n_female = sum(1 for g in genders if g == "Female")
            self.count_label.config(
                text=f"Selected: {n} players  (M: {n_male}  F: {n_female})"
            )
        else:
            self.count_label.config(text=f"Selected: {n} players")

    def format_player_button_text(self, player_name):
        """Return button text with marker when player has temporary edits."""
        if player_name in self.player_overrides:
            return f"{player_name} ✎"
        return player_name

    def refresh_player_button_markers(self):
        """Refresh all player button labels to reflect edit markers."""
        for player_name, btn in self.player_buttons.items():
            btn.config(text=self.format_player_button_text(player_name))
        self._schedule_player_button_font_fit()

    def update_info_display(self):
        """Update the info display with selected players details"""
        self.info_text.delete("1.0", tk.END)

        if not self.selected_players:
            self.info_text.insert("1.0", "No players selected")
            return

        # Create dataframe of selected players
        selected_df = self.main_df.loc[self.selected_players].copy()
        for player_name in self.selected_players:
            overrides = self.player_overrides.get(player_name, {})
            for column_name, value in overrides.items():
                selected_df.at[player_name, column_name] = value

        # Display summary
        self.info_text.insert(tk.END, f"Total Players: {len(self.selected_players)}\n")
        n_male = (
            (selected_df["Gender"] == "Male").sum()
            if "Gender" in selected_df.columns
            else "?"
        )
        n_female = (
            (selected_df["Gender"] == "Female").sum()
            if "Gender" in selected_df.columns
            else "?"
        )
        self.info_text.insert(tk.END, f"Male: {n_male}  Female: {n_female}\n")
        self.info_text.insert(tk.END, "=" * 40 + "\n")

        # Display level distribution FIRST (above players list)
        self.info_text.insert(tk.END, "Level Distribution:\n")

        # Categorize levels into ranges
        levels = selected_df["Level"]
        range_1_2 = len(levels[(levels >= 1) & (levels < 2)])
        range_2_3 = len(levels[(levels >= 2) & (levels < 3)])
        range_3_4 = len(levels[(levels >= 3) & (levels <= 4)])

        self.info_text.insert(tk.END, f"  Level 1-2: {range_1_2} player(s)\n")
        self.info_text.insert(tk.END, f"  Level 2-3: {range_2_3} player(s)\n")
        self.info_text.insert(tk.END, f"  Level 3-4: {range_3_4} player(s)\n")

        self.info_text.insert(tk.END, f"Avg Level: {selected_df['Level'].mean():.2f}\n")
        self.info_text.insert(tk.END, "=" * 40 + "\n\n")

        # Display each player AFTER level distribution
        for name in self.selected_players:
            player = selected_df.loc[name]
            self.info_text.insert(tk.END, f"{name}\n")
            self.info_text.insert(tk.END, f"  Level: {player['Level']}\n")
            if "Gender" in player.index:
                self.info_text.insert(tk.END, f"  Gender: {player['Gender']}\n")
            self.info_text.insert(tk.END, "\n")

    def select_all(self):
        """Select all players"""
        # Select all player buttons
        for player_name in self.player_buttons:
            if not self.player_button_states[player_name]:
                self.player_button_states[player_name] = True
                button = self.player_buttons[player_name]
                button.config(bg="#FED403", relief=tk.SUNKEN)
                if player_name not in self.selected_players:
                    self.selected_players.append(player_name)

        # Update count and info display
        self._update_count_label()
        self.update_info_display()

    def clear_selection(self):
        """Clear all selections"""
        # Deselect all player buttons
        for player_name in self.player_buttons:
            if self.player_button_states[player_name]:
                self.player_button_states[player_name] = False
                button = self.player_buttons[player_name]
                button.config(bg="white", relief=tk.RAISED)

        # Clear selected players list
        self.selected_players = []
        self._update_count_label()
        self.info_text.delete("1.0", tk.END)
        self.info_text.insert("1.0", "No players selected")

    def show_add_player_dialog(self):
        """Show dialog to add a new player."""
        self._show_player_dialog()

    def show_edit_player_dialog(self, player_name):
        """Show dialog to edit an existing player's specs."""
        self._show_player_dialog(player_name)

    def _update_pairs_count_label(self):
        """Refresh the Preferred Pairs button text to show the current pair count."""
        n = len(self.preferred_pairs)
        if n == 0:
            self.pairs_btn.config(text="\U0001f465 Preferred Pairs")
        elif n == 1:
            self.pairs_btn.config(text="\U0001f465 Preferred Pairs  \u00b7  1 pair")
        else:
            self.pairs_btn.config(text=f"\U0001f465 Preferred Pairs  \u00b7  {n} pairs")

    def show_preferred_pairs_dialog(self):
        """Modal dialog for managing preferred pairs."""
        BG = self.colors["bg_dark"]
        BG_SECT = "#3A3A3A"
        BURG = self.colors["accent_red"]
        YELLOW = self.colors["accent_yellow"]
        WHITE = self.colors["text_light"]
        GRAY = "#BBBBBB"
        GREEN = "#4CAF50"

        win = tk.Toplevel(self.root)
        win.title("Preferred Pairs")
        win.configure(bg=BG)
        win.resizable(True, True)
        win.grab_set()

        W, H = 820, 660
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")

        # Working copies so cancelling has no effect
        # Each entry is (frozenset({name1, name2}), forced_games)
        pairs_working = list(self.preferred_pairs)
        pending = []  # 0, 1, or 2 player names waiting to form a pair

        # ── header ──────────────────────────────────────────────────────────
        hdr = tk.Frame(win, bg=BURG)
        hdr.pack(fill=tk.X)
        tk.Label(
            hdr,
            text="\U0001f465  Preferred Pairs",
            font=("Arial", 14, "bold"),
            fg=YELLOW,
            bg=BURG,
            padx=14,
            pady=8,
        ).pack(side=tk.LEFT)
        tk.Label(
            hdr,
            text="Click two players, then choose how many games to force them together.",
            font=("Arial", 10),
            fg=WHITE,
            bg=BURG,
            padx=6,
        ).pack(side=tk.LEFT)

        # ── current pairs display ────────────────────────────────────────────
        pairs_section = tk.LabelFrame(
            win,
            text="Current pairs",
            font=("Arial", 10, "bold"),
            bg=BG,
            fg=YELLOW,
            bd=1,
            relief=tk.RIDGE,
            padx=8,
            pady=4,
        )
        pairs_section.pack(fill=tk.X, padx=14, pady=(10, 4))

        pairs_text_var = tk.StringVar()
        pairs_display = tk.Label(
            pairs_section,
            textvariable=pairs_text_var,
            font=("Arial", 10),
            fg=WHITE,
            bg=BG,
            justify=tk.LEFT,
            wraplength=780,
            anchor=tk.W,
        )
        pairs_display.pack(anchor=tk.W)

        def refresh_pairs_display():
            if pairs_working:
                lines = []
                for i, (fs, fg) in enumerate(pairs_working, 1):
                    names = sorted(fs)
                    games_label = f"{fg} game" + ("s" if fg > 1 else "")
                    lines.append(f"  {i}. {names[0]}  /  {names[1]}   [{games_label}]")
                pairs_text_var.set("\n".join(lines))
            else:
                pairs_text_var.set("  (none)")
            _check_buttons()

        # ── player grid ─────────────────────────────────────────────────────
        grid_outer = tk.LabelFrame(
            win,
            text="Select two players",
            font=("Arial", 10, "bold"),
            bg=BG,
            fg=YELLOW,
            bd=1,
            relief=tk.RIDGE,
        )
        grid_outer.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        grid_canvas = tk.Canvas(grid_outer, bg="#F5F5F5", highlightthickness=0)
        grid_scroll = tk.Scrollbar(
            grid_outer, orient="vertical", command=grid_canvas.yview
        )
        grid_frame = tk.Frame(grid_canvas, bg="#F5F5F5")

        grid_frame.bind(
            "<Configure>",
            lambda e: grid_canvas.configure(scrollregion=grid_canvas.bbox("all")),
        )
        grid_canvas.create_window((0, 0), window=grid_frame, anchor="nw", tags=("gw",))
        grid_canvas.configure(yscrollcommand=grid_scroll.set)
        grid_canvas.bind(
            "<Configure>",
            lambda e: grid_canvas.itemconfig("gw", width=e.width),
        )

        def _on_mousewheel(event):
            grid_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        grid_canvas.bind("<MouseWheel>", _on_mousewheel)
        grid_frame.bind("<MouseWheel>", _on_mousewheel)

        grid_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        grid_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        sorted_players = sorted(self.main_df.index)
        num_cols = 6
        btn_refs = {}

        def _btn_bg(name):
            """Return background colour for a player button given current state."""
            if name in pending:
                return YELLOW
            # Check if player is in any existing pair
            for fs, _fg in pairs_working:
                if name in fs:
                    return "#8B3030"  # dark red tint — already paired
            return "#FFFFFF"

        def _btn_fg(name):
            if name in pending:
                return self.colors["text_dark"]
            for fs, _fg in pairs_working:
                if name in fs:
                    return WHITE
            return self.colors["text_dark"]

        def _refresh_grid():
            for name, btn in btn_refs.items():
                btn.config(bg=_btn_bg(name), fg=_btn_fg(name))

        def _on_player_click(name):
            if name in pending:
                pending.remove(name)
            else:
                if len(pending) >= 2:
                    pending.pop(0)
                pending.append(name)
            _refresh_grid()
            _check_buttons()

        for idx, name in enumerate(sorted_players):
            row = idx // num_cols
            col = idx % num_cols
            btn = tk.Button(
                grid_frame,
                text=name,
                font=("Arial", 9),
                bg=_btn_bg(name),
                fg=_btn_fg(name),
                relief=tk.RAISED,
                bd=1,
                cursor="hand2",
                padx=4,
                pady=4,
                anchor="center",
                command=lambda n=name: _on_player_click(n),
            )
            btn.grid(row=row, column=col, padx=2, pady=2, sticky=(tk.W, tk.E))
            btn.bind("<MouseWheel>", _on_mousewheel)
            btn_refs[name] = btn

        for c in range(num_cols):
            grid_frame.columnconfigure(c, weight=1)

        # ── footer buttons ───────────────────────────────────────────────────
        footer = tk.Frame(win, bg=BG)
        footer.pack(fill=tk.X, padx=14, pady=10)

        add_1_btn = tk.Button(
            footer,
            text="Add pair  ·  1 game 🔒",
            font=("Arial", 11, "bold"),
            bg=GREEN,
            fg=WHITE,
            relief=tk.RAISED,
            cursor="hand2",
            padx=16,
            pady=6,
            state=tk.DISABLED,
        )
        add_2_btn = tk.Button(
            footer,
            text="Add pair  ·  2 games 🔒",
            font=("Arial", 11, "bold"),
            bg="#2E7D32",
            fg=WHITE,
            relief=tk.RAISED,
            cursor="hand2",
            padx=16,
            pady=6,
            state=tk.DISABLED,
        )
        remove_btn = tk.Button(
            footer,
            text="Remove last pair",
            font=("Arial", 11, "bold"),
            bg="#CC4444",
            fg=WHITE,
            relief=tk.RAISED,
            cursor="hand2",
            padx=16,
            pady=6,
            state=tk.DISABLED,
        )
        close_btn = tk.Button(
            footer,
            text="Close",
            font=("Arial", 11),
            bg="#555555",
            fg=WHITE,
            relief=tk.RAISED,
            cursor="hand2",
            padx=16,
            pady=6,
        )

        def _check_buttons():
            # Add pair: need exactly 2 distinct pending players not already paired together
            can_add = False
            if len(pending) == 2 and pending[0] != pending[1]:
                candidate = frozenset(pending)
                if not any(fs == candidate for (fs, _fg) in pairs_working):
                    can_add = True
            add_1_btn.config(state=tk.NORMAL if can_add else tk.DISABLED)
            add_2_btn.config(state=tk.NORMAL if can_add else tk.DISABLED)
            remove_btn.config(state=tk.NORMAL if pairs_working else tk.DISABLED)

        def _on_add(forced_games):
            if len(pending) != 2 or pending[0] == pending[1]:
                return
            candidate = frozenset(pending)
            if any(fs == candidate for (fs, _fg) in pairs_working):
                return
            pairs_working.append((candidate, forced_games))
            pending.clear()
            _refresh_grid()
            refresh_pairs_display()

        def _on_remove():
            if pairs_working:
                pairs_working.pop()
                _refresh_grid()
                refresh_pairs_display()

        def _on_close():
            # Commit working copy back to the app state
            self.preferred_pairs = list(pairs_working)
            self._update_pairs_count_label()
            win.destroy()

        add_1_btn.config(command=lambda: _on_add(1))
        add_2_btn.config(command=lambda: _on_add(2))
        remove_btn.config(command=_on_remove)
        close_btn.config(command=_on_close)

        add_1_btn.pack(side=tk.LEFT, padx=(0, 6))
        add_2_btn.pack(side=tk.LEFT, padx=(0, 8))
        remove_btn.pack(side=tk.LEFT, padx=(0, 8))
        close_btn.pack(side=tk.RIGHT)

        win.protocol("WM_DELETE_WINDOW", _on_close)

        # Initial render
        refresh_pairs_display()
        _check_buttons()

    def _show_player_dialog(self, player_name=None):
        """Unified add/edit player dialog.  player_name=None → add mode."""
        edit_mode = player_name is not None

        if edit_mode and player_name not in self.main_df.index:
            messagebox.showerror("Error", f"Player '{player_name}' not found.")
            return

        # Load existing data in edit mode
        player_data = None
        if edit_mode:
            player_data = self.main_df.loc[player_name].copy()
            for col, val in self.player_overrides.get(player_name, {}).items():
                player_data[col] = val

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Player - {player_name}" if edit_mode else "Add New Player")
        dialog.geometry("450x550")
        dialog.resizable(False, False)
        dialog.configure(bg=self.colors["bg_light"])
        dialog.transient(self.root)
        dialog.grab_set()

        dialog.update_idletasks()
        x = (
            self.root.winfo_x()
            + (self.root.winfo_width() // 2)
            - (dialog.winfo_width() // 2)
        )
        y = (
            self.root.winfo_y()
            + (self.root.winfo_height() // 2)
            - (dialog.winfo_height() // 2)
        )
        dialog.geometry(f"+{x}+{y}")

        tk.Label(
            dialog,
            text=f"Edit {player_name}" if edit_mode else "Add New Player",
            font=self.fonts["big"],
            fg=self.colors["accent_red"],
            bg=self.colors["bg_light"],
        ).pack(pady=(20, 10))

        form_frame = tk.Frame(dialog, bg=self.colors["bg_light"])
        form_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

        # Name row
        tk.Label(
            form_frame,
            text="Name:",
            font=self.fonts["normal"],
            bg=self.colors["bg_light"],
        ).grid(row=0, column=0, sticky=tk.W, pady=5)
        name_entry = None
        if edit_mode:
            tk.Label(
                form_frame,
                text=player_name,
                font=self.fonts["normal_bold"],
                bg=self.colors["bg_light"],
                fg=self.colors["text_dark"],
            ).grid(row=0, column=1, sticky=tk.W, pady=5, padx=10)
        else:
            name_entry = tk.Entry(form_frame, font=self.fonts["normal"], width=25)
            name_entry.grid(row=0, column=1, pady=5, padx=10)
            name_entry.focus_set()

        # Gender row
        tk.Label(
            form_frame,
            text="Gender:",
            font=self.fonts["normal"],
            bg=self.colors["bg_light"],
        ).grid(row=1, column=0, sticky=tk.W, pady=5)
        if edit_mode:
            init_gender = str(player_data.get("Gender", "Male"))
            if init_gender not in ["Male", "Female"]:
                init_gender = "Male"
        else:
            init_gender = "Male"
        gender_var = tk.StringVar(value=init_gender)
        gender_frame = tk.Frame(form_frame, bg=self.colors["bg_light"])
        gender_frame.grid(row=1, column=1, pady=5, padx=10, sticky=tk.W)
        for g in ["Male", "Female"]:
            tk.Radiobutton(
                gender_frame,
                text=g,
                variable=gender_var,
                value=g,
                font=self.fonts["normal"],
                bg=self.colors["bg_light"],
            ).pack(side=tk.LEFT, padx=5)

        # Level row
        tk.Label(
            form_frame,
            text="Level:",
            font=self.fonts["normal"],
            bg=self.colors["bg_light"],
        ).grid(row=2, column=0, sticky=tk.W, pady=5)
        if edit_mode:
            try:
                init_level = float(player_data.get("Level", 1.5))
            except (TypeError, ValueError):
                init_level = 1.5
        else:
            init_level = 1.5
        level_var = tk.DoubleVar(value=init_level)
        tk.Spinbox(
            form_frame,
            from_=0,
            to=4,
            increment=0.1,
            textvariable=level_var,
            font=self.fonts["normal"],
            width=23,
        ).grid(row=2, column=1, pady=5, padx=10)

        # Separator
        tk.Frame(form_frame, height=2, bg=self.colors["accent_red"]).grid(
            row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10
        )

        # Spectrum section header
        tk.Label(
            form_frame,
            text="Spectrum Attributes:",
            font=self.fonts["normal_bold"],
            bg=self.colors["bg_light"],
            fg=self.colors["accent_red"],
        ).grid(row=4, column=0, columnspan=2, pady=(5, 10))

        # Happiness row
        tk.Label(
            form_frame,
            text="Happiness:",
            font=self.fonts["small"],
            bg=self.colors["bg_light"],
        ).grid(row=5, column=0, sticky=tk.W, pady=3)
        if edit_mode:
            try:
                init_happiness = int(player_data.get("Happiness", 0))
            except (TypeError, ValueError):
                init_happiness = 0
        else:
            init_happiness = 0
        happiness_var = tk.IntVar(value=init_happiness)
        tk.Entry(
            form_frame, textvariable=happiness_var, font=self.fonts["small"], width=25
        ).grid(row=5, column=1, pady=3, padx=10)

        # Spectrum spinboxes
        spectrum_names = [
            "Prey",
            "Equilibrist",
            "Challenger",
            "Chill",
            "Hunter",
            "Classist",
        ]
        spectrum_frame = tk.Frame(form_frame, bg=self.colors["bg_light"])
        spectrum_frame.grid(row=6, column=0, columnspan=2, pady=5)
        spectrum_vars = {}
        for idx, spec_name in enumerate(spectrum_names):
            row_idx = idx // 2
            col_idx = idx % 2
            spec_frame = tk.Frame(spectrum_frame, bg=self.colors["bg_light"])
            spec_frame.grid(row=row_idx, column=col_idx, padx=5, pady=3, sticky=tk.W)
            tk.Label(
                spec_frame,
                text=f"{spec_name}:",
                font=self.fonts["small"],
                bg=self.colors["bg_light"],
                width=10,
                anchor=tk.W,
            ).pack(side=tk.LEFT)
            if edit_mode:
                try:
                    init_spec = int(player_data.get(spec_name, 5))
                except (TypeError, ValueError):
                    init_spec = 5
            else:
                init_spec = 5
            var = tk.IntVar(value=init_spec)
            spectrum_vars[spec_name] = var
            tk.Spinbox(
                spec_frame,
                from_=0,
                to=10,
                textvariable=var,
                font=self.fonts["small"],
                width=5,
            ).pack(side=tk.LEFT, padx=5)

        # Buttons
        buttons_frame = tk.Frame(dialog, bg=self.colors["bg_light"])
        buttons_frame.pack(pady=20)
        btn_cfg = dict(
            font=self.fonts["normal_bold"],
            relief=tk.RAISED,
            bd=3,
            cursor="hand2",
            padx=20,
            pady=8,
        )

        if edit_mode:

            def on_save():
                try:
                    new_level = float(level_var.get())
                    new_happiness = int(happiness_var.get())
                except (TypeError, ValueError):
                    messagebox.showerror(
                        "Invalid Input", "Level and Happiness must be numeric values."
                    )
                    return
                self.player_overrides[player_name] = {
                    "Gender": str(gender_var.get()),
                    "Level": new_level,
                    "Category": new_level,
                    "Happiness": new_happiness,
                    **{s: int(spectrum_vars[s].get()) for s in spectrum_names},
                }
                self.refresh_player_button_markers()
                self.update_info_display()
                dialog.destroy()

            def on_reset():
                if player_name in self.player_overrides:
                    del self.player_overrides[player_name]
                base = self.main_df.loc[player_name]
                base_gender = str(base.get("Gender", "Male"))
                if base_gender not in ["Male", "Female"]:
                    base_gender = "Male"
                gender_var.set(base_gender)
                try:
                    level_var.set(float(base.get("Level", 1.5)))
                except (TypeError, ValueError):
                    level_var.set(1.5)
                try:
                    happiness_var.set(int(base.get("Happiness", 0)))
                except (TypeError, ValueError):
                    happiness_var.set(0)
                for s in spectrum_names:
                    try:
                        spectrum_vars[s].set(int(base.get(s, 5)))
                    except (TypeError, ValueError):
                        spectrum_vars[s].set(5)
                self.refresh_player_button_markers()
                self.update_info_display()

            dialog.bind("<Return>", lambda e: on_save())
            tk.Button(
                buttons_frame,
                text="Reset",
                command=on_reset,
                bg=self.colors["accent_red"],
                fg=self.colors["text_light"],
                **btn_cfg,
            ).pack(side=tk.LEFT, padx=5)
            tk.Button(
                buttons_frame,
                text="Save",
                command=on_save,
                bg=self.colors["accent_yellow"],
                fg=self.colors["text_dark"],
                **btn_cfg,
            ).pack(side=tk.LEFT, padx=5)
            tk.Button(
                buttons_frame,
                text="Cancel",
                command=dialog.destroy,
                bg=self.colors["bg_light"],
                fg=self.colors["text_dark"],
                **btn_cfg,
            ).pack(side=tk.LEFT, padx=5)
        else:

            def on_add():
                name = name_entry.get().strip()
                if not name:
                    messagebox.showerror("Error", "Please enter a player name.")
                    return
                if name in self.main_df.index:
                    messagebox.showerror("Error", f"Player '{name}' already exists.")
                    return
                self.add_new_player(
                    name=name,
                    gender=gender_var.get(),
                    level=level_var.get(),
                    happiness=happiness_var.get(),
                    prey=spectrum_vars["Prey"].get(),
                    equilibrist=spectrum_vars["Equilibrist"].get(),
                    challenger=spectrum_vars["Challenger"].get(),
                    chill=spectrum_vars["Chill"].get(),
                    hunter=spectrum_vars["Hunter"].get(),
                    classist=spectrum_vars["Classist"].get(),
                )
                dialog.destroy()

            dialog.bind("<Return>", lambda e: on_add())
            tk.Button(
                buttons_frame,
                text="Add Player",
                command=on_add,
                bg=self.colors["accent_yellow"],
                fg=self.colors["text_dark"],
                **btn_cfg,
            ).pack(side=tk.LEFT, padx=5)
            tk.Button(
                buttons_frame,
                text="Cancel",
                command=dialog.destroy,
                bg=self.colors["bg_light"],
                fg=self.colors["text_dark"],
                **btn_cfg,
            ).pack(side=tk.LEFT, padx=5)

    def add_new_player(
        self,
        name,
        gender,
        level,
        happiness,
        prey,
        equilibrist,
        challenger,
        chill,
        hunter,
        classist,
    ):
        """Add a new player to the main dataframe and update UI"""
        # Create a new player series
        new_player_data = {
            "Name": name,
            "Surname": "",
            "Level": float(level),
            "Gender": str(gender),
            "Happiness": int(happiness),
            "Games played": 0,
            "Noisy level": 0,
            "Category": float(level),
            "Prey": int(prey),
            "Equilibrist": int(equilibrist),
            "Challenger": int(challenger),
            "Chill": int(chill),
            "Hunter": int(hunter),
            "Classist": int(classist),
        }

        # Add to main_df - drop any existing player with same name first to avoid duplicates
        import pandas as pd  # noqa: PLC0415

        if name in self.main_df.index:
            self.main_df = self.main_df.drop(name)
        new_row_df = pd.DataFrame([new_player_data], index=[name])
        self.main_df = pd.concat([self.main_df, new_row_df])

        # Get the scrollable frame (parent of player buttons)
        scrollable_frame = getattr(self, "player_scrollable_frame", None)

        if scrollable_frame is None:
            messagebox.showerror("Error", "Could not find player button container.")
            return

        # Destroy all existing buttons and recreate them
        for widget in scrollable_frame.winfo_children():
            widget.destroy()

        # Save current selection state before recreating buttons
        previously_selected = set(self.selected_players)

        # Recreate all player buttons
        self.player_buttons = {}
        self.player_button_states = {}
        sorted_players = sorted(self.main_df.index)
        num_columns = 6

        for idx, player_name in enumerate(sorted_players):
            row = idx // num_columns
            col = idx % num_columns

            # Check if this player was previously selected OR is the newly added player
            is_selected = player_name in previously_selected or player_name == name

            btn = tk.Button(
                scrollable_frame,
                text=self.format_player_button_text(player_name),
                font=(
                    self.font_button_font
                    if hasattr(self, "font_button_font")
                    else self.player_button_font
                ),
                bg=(
                    self.colors["accent_yellow"]
                    if is_selected
                    else self.colors["bg_light"]
                ),
                fg=self.colors["text_dark"],
                relief=tk.SUNKEN if is_selected else tk.RAISED,
                bd=2,
                cursor="hand2",
                padx=self.player_button_padx,
                pady=self.player_button_pady,
                anchor="center",
                command=lambda pname=player_name: self.toggle_player(pname),
            )
            btn.grid(row=row, column=col, padx=2, pady=2, sticky=(tk.W, tk.E))
            btn.bind(
                "<Button-3>",
                lambda event, pname=player_name: self.show_edit_player_dialog(pname),
            )
            self.bind_tooltip(btn, "right click to change specs")

            self.player_buttons[player_name] = btn
            self.player_button_states[player_name] = is_selected

        # Rebuild selected_players list from the saved state plus the new player
        self.selected_players = [
            p for p in sorted_players if p in previously_selected or p == name
        ]

        # Add "+ Add Player" button at the end of the list
        total_players = len(sorted_players)
        add_row = total_players // num_columns
        add_col = total_players % num_columns

        add_player_btn = tk.Button(
            scrollable_frame,
            text="+ Add Player",
            font=self.fonts["normal_bold"],
            bg=self.colors["accent_red"],
            fg=self.colors["text_light"],
            relief=tk.RAISED,
            bd=2,
            cursor="hand2",
            padx=5,
            pady=5,
            anchor="center",
            command=self.show_add_player_dialog,
        )
        add_player_btn.grid(
            row=add_row, column=add_col, padx=2, pady=2, sticky=(tk.W, tk.E)
        )
        self.add_player_btn = add_player_btn

        # Configure column weights for equal distribution
        for col in range(num_columns):
            scrollable_frame.columnconfigure(col, weight=1)

        self._schedule_player_button_font_fit()

        # Update count label and info display
        self._update_count_label()
        self.update_info_display()

    def run_session(self):
        """Run session generation with selected players"""
        if len(self.selected_players) < 4:
            messagebox.showwarning(
                "Too Few Players", "Please select at least 4 players to run a session."
            )
            return

        # Disable the run button to prevent multiple clicks
        self.run_btn.config(state=tk.DISABLED)

        # Create sub dataframe - remove duplicates if any exist
        # Use unique() to ensure selected_players list has no duplicates
        import pandas as pd  # noqa: PLC0415

        unique_selected_players = list(dict.fromkeys(self.selected_players))
        sub_df = self.main_df.loc[unique_selected_players].copy()

        # Additional safety check: ensure sub_df has no duplicate indices
        if sub_df.index.duplicated().any():
            duplicates = sub_df.index[sub_df.index.duplicated()].tolist()
            messagebox.showerror(
                "Data Error",
                f"Duplicate players found in database: {', '.join(duplicates)}\n\n"
                "Please restart the application to fix this issue.",
            )
            self.run_btn.config(state=tk.NORMAL)
            return

        # Apply temporary UI overrides without mutating self.main_df
        for player_name in unique_selected_players:
            overrides = self.player_overrides.get(player_name, {})
            for column_name, value in overrides.items():
                sub_df.at[player_name, column_name] = value

        # Optional temporary female level/category shift (UI-only)
        try:
            female_shift = float(self.female_boost_var.get())
        except (TypeError, ValueError):
            female_shift = 0.0

        if female_shift != 0.0:
            female_mask = (
                sub_df["Gender"]
                .astype(str)
                .str.strip()
                .str.lower()
                .isin(["female", "f"])
            )
            if female_mask.any():
                boosted_levels = pd.to_numeric(
                    sub_df.loc[female_mask, "Level"], errors="coerce"
                ).fillna(0)
                sub_df.loc[female_mask, "Level"] = (
                    boosted_levels + female_shift
                ).round(1)

                if "Category" in sub_df.columns:
                    boosted_categories = pd.to_numeric(
                        sub_df.loc[female_mask, "Category"], errors="coerce"
                    ).fillna(0)
                    sub_df.loc[female_mask, "Category"] = (
                        boosted_categories + female_shift
                    ).round(1)

        sub_df["Happiness"] = 0
        sub_df["Games played"] = 0

        # Get selected preferences from UI
        type_preferences = [var.get() for var in self.type_prefs]
        gender_preferences = [var.get() for var in self.gender_prefs]
        amount_of_rounds = self.num_rounds_var.get()

        # Get games per round setting
        games_per_round_setting = self.games_per_round_var.get()
        if games_per_round_setting == "auto":
            games_per_round = len(self.selected_players) // 4
        else:
            games_per_round = int(games_per_round_setting)

        # Parameters for seed optimization
        first_seed = 0
        last_seed = 9

        # Parameters from UI
        try:
            level_gap_tol = float(self.level_gap_tol_var.get())
        except (TypeError, ValueError):
            level_gap_tol = 1.1

        try:
            lambda_weight = float(self.lambda_weight_var.get())
        except (TypeError, ValueError):
            lambda_weight = 2.4

        spectrum_enabled = bool(self.spectrum_var.get())

        # Create progress dialog
        progress_dialog = ProgressDialog(self.root, first_seed, last_seed, self.colors)

        # Run generation with progress tracking
        self.run_generation_with_progress(
            sub_df,
            amount_of_rounds,
            type_preferences,
            gender_preferences,
            first_seed,
            last_seed,
            progress_dialog,
            games_per_round,
            level_gap_tol,
            lambda_weight,
            spectrum_enabled,
            self.preferred_pairs,
        )

    def run_generation_with_progress(
        self,
        sub_df,
        amount_of_rounds,
        type_preferences,
        gender_preferences,
        first_seed,
        last_seed,
        progress_dialog,
        games_per_round,
        level_gap_tol,
        lambda_weight,
        spectrum_enabled,
        preferred_pairs=None,
    ):
        """Run session generation with progress updates."""
        try:
            # Clear console at start
            self.clear_console()
            print("Starting session generation...")
            print(f"Testing seeds {first_seed} to {last_seed}\n")

            # Compute rounds_reordering once: internally generate level rounds first for
            # better optimization, then reorder back to the user-intended display order.
            def _round_type_priority(type_pref):
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

            generated_order_indices = sorted(
                range(amount_of_rounds),
                key=lambda idx: (_round_type_priority(type_preferences[idx]), idx),
            )
            generated_pos_by_original_idx = {
                original_idx: generated_pos + 1
                for generated_pos, original_idx in enumerate(generated_order_indices)
            }
            rounds_reordering = [
                generated_pos_by_original_idx[i] for i in range(amount_of_rounds)
            ]

            session_of_rounds, chosen_seed = (
                main_module.run_session_generation_with_seed_optimization(
                    df=sub_df,
                    amount_of_rounds=amount_of_rounds,
                    type_preferences=type_preferences,
                    gender_preferences=gender_preferences,
                    rounds_reordering=rounds_reordering,
                    level_gap_tol=level_gap_tol,
                    num_iter=435,
                    lambda_weight=lambda_weight,
                    weight_same_teammate=5,
                    first_seed=first_seed,
                    last_seed=last_seed,
                    spectrum=spectrum_enabled,
                    games_per_round_each_round=games_per_round,
                    print_progress=True,
                    progress_callback=progress_dialog.update_progress,
                )
            )

            # Apply preferred-pairs post-processing
            if preferred_pairs:
                main_module.force_preferred_pairs_in_session(
                    session_of_rounds,
                    preferred_pairs,
                    lambda_weight=lambda_weight,
                )

            # Close progress dialog
            progress_dialog.close()

            # Show results in console/terminal
            print("\n" + "=" * 80)
            print("SESSION RESULTS")
            print("=" * 80)
            session_of_rounds.print_all_results(
                print_levels=True,
            )

            # Store session for further use
            self.session_of_rounds = session_of_rounds
            self.chosen_seed = chosen_seed

            # Save the session using save_session_of_rounds with default parameters
            try:
                session_of_rounds.save_session_of_rounds()
                print("\n" + "=" * 80)
                print("Session saved successfully!")
                print("=" * 80)

                # Find the most recently created session folder with plots
                sessions_dir = "sessions"
                if os.path.exists(sessions_dir):
                    # Get all subdirectories in sessions folder
                    session_folders = [
                        os.path.join(sessions_dir, d)
                        for d in os.listdir(sessions_dir)
                        if os.path.isdir(os.path.join(sessions_dir, d))
                    ]

                    # Find folders with a plots subdirectory
                    folders_with_plots = [
                        f
                        for f in session_folders
                        if os.path.exists(os.path.join(f, "plots"))
                    ]

                    # Get the most recently modified one
                    if folders_with_plots:
                        most_recent = max(folders_with_plots, key=os.path.getmtime)
                        plots_dir = os.path.join(most_recent, "plots")

                        # Generate and show the Session Games overview PNG
                        try:
                            from core.charts import (
                                create_session_games_png,
                            )  # noqa: PLC0415
                        except ImportError:
                            from charts import create_session_games_png  # type: ignore
                        session_games_png = os.path.join(
                            most_recent, "session_games.png"
                        )
                        print("Creating session games overview...")
                        create_session_games_png(
                            session_of_rounds,
                            session_games_png,
                            show_levels=self.png_show_levels_var.get(),
                        )

                        # Show interactive games editor then session games tab
                        self.show_games_editor()
                        self.show_session_games_tab(session_games_png)

                        # Then show happiness/team/spectrum charts in tabbed window
                        self.show_plots_window(plots_dir)

            except Exception as save_error:
                import traceback

                print(f"Warning: Could not save session: {save_error}")
                print("Full traceback:")
                traceback.print_exc()

                # Still try to show the UI even if save failed
                try:
                    sessions_dir = "sessions"
                    if os.path.exists(sessions_dir):
                        session_folders = [
                            os.path.join(sessions_dir, d)
                            for d in os.listdir(sessions_dir)
                            if os.path.isdir(os.path.join(sessions_dir, d))
                        ]
                        if session_folders:
                            most_recent = max(session_folders, key=os.path.getmtime)
                            plots_dir = os.path.join(most_recent, "plots")
                            if os.path.exists(plots_dir):
                                self.show_games_editor()
                                self.show_plots_window(plots_dir)
                            # Session Games tab even without plots folder
                            try:
                                from core.charts import (
                                    create_session_games_png,
                                )  # noqa: PLC0415
                            except ImportError:
                                from charts import create_session_games_png  # type: ignore
                            session_games_png = os.path.join(
                                most_recent, "session_games.png"
                            )
                            create_session_games_png(
                                session_of_rounds,
                                session_games_png,
                                show_levels=self.png_show_levels_var.get(),
                            )
                            self.show_session_games_tab(session_games_png)
                except:
                    pass

        except Exception as e:
            # Close progress dialog if still open
            try:
                progress_dialog.close()
            except:
                pass

            # Print error details
            print(f"Error: {e}")
            import traceback

            traceback.print_exc()

            messagebox.showerror("Error", f"An error occurred:\n\n{str(e)}")
        finally:
            # Re-enable the run button
            self.run_btn.config(state=tk.NORMAL)


def _show_loading_window(root):
    """Display a splash/loading window while the app initialises."""
    splash = tk.Toplevel(root)
    splash.overrideredirect(True)  # no window decorations
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


def main():
    """Main function to run the UI"""
    global main_module, ftf_module

    root = tk.Tk()
    root.withdraw()  # keep hidden until fully built

    # First-run: ask user to import xlsx files if config doesn't exist yet
    if not os.path.exists(_XLSX_CONFIG_PATH):
        if not _run_setup_wizard(root):
            root.destroy()
            return

    splash = _show_loading_window(root)
    root.update()  # force splash to paint before blocking imports

    try:
        # Evict all core sub-modules and main so everything re-executes from
        # scratch with the current xlsx_config.json (critical after the first-run
        # wizard writes the config while data_loader was already imported with
        # main_df=None).
        for _key in list(sys.modules.keys()):
            if "data_loader" in _key or _key in ("main", "core", "core.main"):
                del sys.modules[_key]

        main_module = load_module("main", "core/main.py", force_reload=True)
        ftf_module = load_module(
            "fine_tuning_functions", "core/fine_tuning_functions.py"
        )
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

    splash.destroy()
    root.deiconify()  # show the main window now
    root.mainloop()


if __name__ == "__main__":
    main()

# %%
