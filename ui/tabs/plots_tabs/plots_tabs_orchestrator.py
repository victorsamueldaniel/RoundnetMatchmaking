"""Plots tab orchestrator that routes plots to category-specific modules."""

import os

from ui.functions.tab_functions import plots_find_png_files
from ui.tabs.plots_tabs.plots_happiness_tab import HappinessPlotsTabMixin
from ui.tabs.plots_tabs.plots_spectrum_tab import SpectrumPlotsTabMixin
from ui.tabs.plots_tabs.plots_team_tab import TeamPlotsTabMixin
from ui.tabs.plots_tabs.plots_generic_tab import GenericPlotsTabMixin


class PlotsTabMixin(
    HappinessPlotsTabMixin,
    SpectrumPlotsTabMixin,
    TeamPlotsTabMixin,
    GenericPlotsTabMixin,
):
    def show_plots_window(self, plots_dir):
        """Add plot tabs to the main notebook."""
        games_editor_exists = False
        session_games_exists = False
        for tab_id in self.main_notebook.tabs():
            tab_text = self.main_notebook.tab(tab_id, "text")
            if tab_text == "Games Editor":
                games_editor_exists = True
            if tab_text == "Session Games":
                session_games_exists = True

        num_tabs_to_keep = 1 + int(session_games_exists) + int(games_editor_exists)
        while len(self.main_notebook.tabs()) > num_tabs_to_keep:
            self.main_notebook.forget(num_tabs_to_keep)

        png_files = plots_find_png_files(plots_dir)
        if not png_files:
            print("No plot files found to display.")
            return

        for png_file in png_files:
            filename_lower = os.path.basename(png_file).lower()
            if "happiness" in filename_lower:
                self._add_happiness_plot_tab(png_file)
            elif "spectrum" in filename_lower:
                self._add_spectrum_plot_tab(png_file)
            elif "team" in filename_lower:
                self._add_team_plot_tab(png_file)
            else:
                self._add_generic_plot_tab(png_file)

        print(f"Added {len(png_files)} plot tabs to main window.")
