# UI Structure

This document describes the new UI module layout and how the desktop app is composed.

## Overview

The UI has been split into a coordinator + tab modules architecture:

- `ui/roundnet_matchmaking_ui.py`: main orchestrator and startup entrypoint.
- `ui/session_generation_tab.py`: Session Generation tab controller.
- `ui/games_editor_tab.py`: Games Editor tab controller.
- `ui/session_games_tab.py`: Session Games tab controller.
- `ui/plots_tab.py`: Plots tab controller.
- `ui/tab_functions.py`: shared standalone functions (startup/setup helpers and shared constants), grouped by functional area.
- `ui/player_selection_ui.py`: backward-compatible wrapper that forwards to the new orchestrator.

## Startup Flow

1. `main()` in `ui/roundnet_matchmaking_ui.py` runs.
2. `_ensure_windows_tcl_env()` is called (from `ui/tab_functions.py`) before creating Tk root.
3. First-run wizard runs when `xlsx/xlsx_config.json` is missing.
4. Splash window is shown while core modules are loaded lazily.
5. `core/main.py` is loaded via `load_module` and injected into tab modules.
6. `PlayerSelectionUI` is instantiated (composed from tab mixins).
7. Main window is shown and event loop starts.

## Coordinator

`PlayerSelectionUI` in `ui/roundnet_matchmaking_ui.py` is composed from mixins:

- `SessionGenerationTabMixin`
- `GamesEditorTabMixin`
- `SessionGamesTabMixin`
- `PlotsTabMixin`

This keeps tab logic isolated while preserving a single shared state object (`self`) across tabs.

## Tab Layout (visual ordering)

### Session Generation tab (`ui/session_generation_tab.py`)

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

### Games Editor tab (`ui/games_editor_tab.py`)

Top-to-bottom:

1. Title
2. Instructions and pending changes display
3. Score history strip
4. Action buttons (Undo, Apply)
5. Scrollable rounds/games content

Left-to-right inside each round column:

- Team A panel
- VS center
- Team B panel
- Not Playing panel (when present)

### Session Games tab (`ui/session_games_tab.py`)

Two display modes:

- Fallback mode: one combined image with zoom/scroll.
- Interactive mode: stacked round images on the left, control panel on the right.

Interactive mode right panel order:

1. Round Order label
2. Usage instructions
3. Status label
4. Apply Changes
5. Reset Order

### Plots tab (`ui/plots_tab.py`)

One tab per PNG file generated in the plots directory.

Each plot tab contains:

1. Plot title (top)
2. Scrollable/zoomable image canvas (center)
3. Horizontal and vertical scrollbars

## Shared Functions (`ui/tab_functions.py`)

This file centralizes standalone functions and shared constants:

- XLSX setup paths and setup constants.
- First-run wizard and missing-value completion dialogs.
- XLSX writeback helper.
- Splash window helper.
- Windows Tcl/Tk environment helper.

## Compatibility and Entry Points

- Primary entrypoint: `ui.roundnet_matchmaking_ui:main`
- Command: `roundnet-matchmaking`
- Legacy module compatibility: `ui.player_selection_ui` forwards to the new entrypoint.

## Build Integration

`ui/build_exe.py` now uses:

- `ENTRYPOINT = "ui/roundnet_matchmaking_ui.py"`

and copies the split UI modules into the build output so runtime imports resolve correctly.