"""Main UI orchestrator for Roundnet Matchmaking."""

import sys
import os

import tkinter as tk
from tkinter import messagebox

from ui.ui_helpers import current_dir, load_module
from ui.tab_functions import (
    _XLSX_CONFIG_PATH,
    _run_setup_wizard,
    _show_loading_window,
    _ensure_windows_tcl_env,
)
from ui.session_generation_tab import SessionGenerationTabMixin
from ui.games_editor_tab import GamesEditorTabMixin
from ui.session_games_tab import SessionGamesTabMixin
from ui.plots_tab import PlotsTabMixin
import ui.session_generation_tab as session_generation_tab
import ui.games_editor_tab as games_editor_tab
import ui.session_games_tab as session_games_tab


main_module = None
ftf_module = None


class PlayerSelectionUI(
    SessionGenerationTabMixin,
    GamesEditorTabMixin,
    SessionGamesTabMixin,
    PlotsTabMixin,
):
    """Composed UI class built from tab mixins."""



def main():
    """Main function to run the UI."""
    global main_module, ftf_module

    _ensure_windows_tcl_env()
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
        ftf_module = load_module("fine_tuning_functions", "core/fine_tuning_functions.py")

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

    PlayerSelectionUI(root)

    splash.destroy()
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()
