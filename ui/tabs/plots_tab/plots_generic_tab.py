"""Fallback plot tab rendering for uncategorized plot images."""

import os

from ui.tabs.plots_tab.plots_base_tab import PlotsBaseTabMixin


class GenericPlotsTabMixin(PlotsBaseTabMixin):
    def _add_generic_plot_tab(self, png_file):
        """Render a generic plot tab for uncategorized PNGs."""
        filename = os.path.basename(png_file)
        tab_name = os.path.splitext(filename)[0].replace("_", " ").title()
        self._add_plot_image_tab(png_file, tab_name)
