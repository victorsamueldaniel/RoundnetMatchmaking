"""Shared UI tab functions and startup helpers."""

import sys
import os
import json
import shutil

import tkinter as tk
from tkinter import ttk, filedialog

import pandas as pd

from ui.ui_helpers import set_window_icon_from_logo
from core.data_loader import validate_xlsx


if getattr(sys, "frozen", False):
    _xlsx_dir = os.path.join(os.path.dirname(sys.executable), "xlsx")
else:
    _xlsx_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "xlsx"
    )
_XLSX_CONFIG_PATH = os.path.join(_xlsx_dir, "xlsx_config.json")


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


_FILE_ROLES = []


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

        from core.data_loader import load_data as _load_data  # type: ignore

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
