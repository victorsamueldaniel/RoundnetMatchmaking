# UI Structure

This document describes the new UI module layout and how the desktop app is composed.

## Overview

The UI has been split into a coordinator + tab modules architecture:
### main
- `ui/main/roundnet_matchmaking_ui.py`: main orchestrator and startup entrypoint.
- `ui/main/player_selection_ui.py`: backward-compatible wrapper entrypoint.
- `ui/main/build_exe.py`: PyInstaller build script.
### tabs
- `ui/tabs/session_generation_tab.py`: Session Generation tab controller. Includes the **Load Existing Session** button (📂) which opens a file dialog, deserializes a saved `.pkl`, and opens the same editor/plots tabs that appear after generating a session.
- `ui/tabs/games_editor_tab.py`: Games Editor tab controller.
- `ui/tabs/session_games_tab.py`: Session Games tab controller.
- `ui/tabs/plots_tab/plots_tab.py`: Plots tab controller.
- `ui/tabs/plots_tab/plots_happiness_tab.py`: Happiness plots tab renderer.
- `ui/tabs/plots_tab/plots_spectrum_tab.py`: Spectrum plots tab renderer.
- `ui/tabs/plots_tab/plots_team_tab.py`: Team analysis plots tab renderer.
- `ui/tabs/plots_tab/plots_generic_tab.py`: fallback renderer for uncategorized plots.
- `ui/tabs/plots_tab/plots_base_tab.py`: shared image/zoom/scroll rendering logic for plot tabs.
### functions
- `ui/functions/setup_wizard.py`: first-run setup wizard and XLSX configuration flow.
- `ui/functions/ui_helpers.py`: shared runtime helper utilities used across UI modules.
- `ui/functions/tab_functions.py`: shared standalone tab helpers plus startup runtime helpers.
### legacy
- `ui/main/player_selection_ui.py`: backward-compatible wrapper that forwards to the new orchestrator.

## Startup Flow

1. `main()` in `ui/main/roundnet_matchmaking_ui.py` runs.
2. `_ensure_windows_tcl_env()` is called (from `ui/functions/tab_functions.py`) before creating Tk root.
3. First-run wizard runs (from `ui/functions/setup_wizard.py`) when `xlsx/xlsx_config.json` is missing.
4. Splash window is shown while core modules are loaded lazily.
5. `core/main.py` is loaded via `load_module` (from `ui/functions/ui_helpers.py`) and injected into tab modules.
6. `PlayerSelectionUI` is instantiated (composed from tab mixins).
7. Main window is shown and event loop starts.

## Coordinator

`PlayerSelectionUI` in `ui/main/roundnet_matchmaking_ui.py` is composed from mixins:

- `SessionGenerationTabMixin`
- `GamesEditorTabMixin`
- `SessionGamesTabMixin`
- `PlotsTabMixin`

This keeps tab logic isolated while preserving a single shared state object (`self`) across tabs.

Rule of thumb: place cross-cutting runtime infrastructure helpers in `ui/functions/ui_helpers.py` (module loading, icon setup, console/progress plumbing), and place UI workflow/domain helpers in `ui/functions/tab_functions.py`.

## Tab Layout (visual ordering)

### Session Generation tab (`ui/tabs/session_generation_tab.py`)

UI build order follows top-to-bottom and left-to-right:

1. Header area:
   - Logo
   - Main title
   - Selected players count
2. Action button row (left to right):
   - Preferred Pairs
   - Select All
   - Clear Selection
   - Run Session
3. Main content top pane (left to right):
   - Available Players (scrollable grid)
   - Selected Players Info
   - Console Output
4. Round Preferences bottom pane:
   - Left panel: rounds list, round count controls, games-per-round controls
   - Right panel: parameter sliders and toggles

This module also contains shared responsive/font/tooltip behavior used by all tabs.

### Games Editor tab (`ui/tabs/games_editor_tab.py`)

Top-to-bottom:

1. Title
2. Instructions and pending changes display
3. Scrollable rounds/games content
4. Score history strip
5. Action buttons (Undo, Apply)


Inside each round column:

- Team A panel
- VS center
- Team B panel
- Not Playing panel (when present)

### Session Games tab (`ui/tabs/session_games_tab.py`)

Two display modes:

- Fallback mode: one combined image with zoom/scroll.
- Interactive mode: stacked round images on the left, control panel on the right.

Interactive mode right panel order:

1. Round Order label
2. Usage instructions
3. Status label
4. Apply Changes
5. Reset Order

### Plots tab (`ui/tabs/plots_tab/plots_tab.py`)

The plots area is split across several modules:

- `ui/tabs/plots_tab/plots_tab.py`: dispatch/orchestrator that routes each PNG by category.
- `ui/tabs/plots_tab/plots_happiness_tab.py`: happiness plot tabs.
- `ui/tabs/plots_tab/plots_spectrum_tab.py`: spectrum plot tabs.
- `ui/tabs/plots_tab/plots_team_tab.py`: team analysis plot tabs.
- `ui/tabs/plots_tab/plots_generic_tab.py`: fallback tabs for other plot files.
- `ui/tabs/plots_tab/plots_base_tab.py`: shared image tab rendering logic.

One tab per PNG file generated in the plots directory.

Each plot tab contains:

1. Plot title (top)
2. Scrollable/zoomable image canvas (center)
3. Horizontal and vertical scrollbars

## Setup Wizard (`ui/functions/setup_wizard.py`)

This file contains the dedicated first-run setup flow:

- XLSX setup paths and setup constants.
- First-run wizard and missing-value completion dialogs.
- XLSX writeback helper.

## Shared Functions (`ui/functions/tab_functions.py`)

This file centralizes standalone functions and shared constants:

- Splash window helper.
- Windows Tcl/Tk environment helper.
- Session Generation helper: round type priority ordering.
- Games Editor helper: happiness delta to color mapping.
- Session Games helper: out-of-place round counting.
- Plots helper: plot PNG file discovery.

## Shared Runtime Helpers (`ui/functions/ui_helpers.py`)

This file centralizes reusable runtime/UI infrastructure helpers used by the orchestrator and tabs, including:

- Module loading helper (`load_module`) for lazy core imports.
- App/window icon helper (`set_window_icon_from_logo`).
- Console output redirection helper (`ConsoleRedirector`).
- Progress UI helper (`ProgressDialog`).

## Compatibility and Entry Points

- Primary entrypoint: `ui.main.roundnet_matchmaking_ui:main`
- Command: `roundnet-matchmaking`
- Legacy module compatibility: `ui.main.player_selection_ui` forwards to the new entrypoint.

## Build Integration

`ui/main/build_exe.py` now uses:

- `ENTRYPOINT = "ui/main/roundnet_matchmaking_ui.py"`

and copies the split UI modules into the build output so runtime imports resolve correctly.