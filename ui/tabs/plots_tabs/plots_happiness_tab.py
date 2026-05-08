"""Happiness plot tab rendering."""

import os

from ui.tabs.plots_tabs.plots_base_tab import PlotsBaseTabMixin


class HappinessPlotsTabMixin(PlotsBaseTabMixin):
    def _add_happiness_plot_tab(self, png_file):
        """Render the happiness plot tab."""
        filename = os.path.basename(png_file)
        tab_name = os.path.splitext(filename)[0].replace("_", " ").title()
        self._add_plot_image_tab(png_file, tab_name)
