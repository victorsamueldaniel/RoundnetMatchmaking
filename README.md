# Roundnet Matchmaking

Roundnet Matchmaking is a Python desktop application that generates balanced sessions and matchups from player skill and preference data.

## Features
- Session generation with optimization-based balancing.
- Spreadsheet-driven player import.
- Desktop UI for setup and execution.
- Chart generation and post-session artifacts.

## Quick Start
1. Create and activate a virtual environment.
2. Install the project in editable mode:
   ```bash
   python -m pip install -e ".[dev]"
   ```
3. Start the application:
   ```bash
   roundnet-matchmaking
   ```

If you run project code from Jupyter/VS Code notebooks, also install and register
the venv kernel:

```bash
python -m pip install ipykernel
python -m ipykernel install --user --name roundnet-matchmaking --display-name "Python (RoundnetMatchmaking)"
```

Then select that kernel before running notebook cells.

Preferred launch mode:
- Use the installed command `roundnet-matchmaking`.
- For development, use module execution from repo root: `python -m ui.roundnet_matchmaking_ui`.
- Legacy compatibility path is still available: `python -m ui.player_selection_ui`.
- Avoid direct file execution (`python ui/roundnet_matchmaking_ui.py`) because it can bypass package import context.
- For the desktop UI, prefer launching from a terminal (not from a notebook cell).

## UI Troubleshooting (Windows)

### `TclError: Can't find a usable init.tcl`

Error example:

```text
TclError: Can't find a usable init.tcl ...
This probably means that Tcl wasn't installed properly.
```

This means the active Python interpreter cannot find its Tcl/Tk runtime files.

Recommended fix order:

1. Verify which interpreter is active:
   ```bash
   python -c "import sys; print(sys.executable)"
   ```
2. Recreate the venv from a full Python install that includes Tcl/Tk.
3. Reinstall dependencies:
   ```bash
   python -m pip install -e ".[dev]"
   python -m pip install -e ".[ui]"
   ```
4. Quick tkinter check:
   ```bash
   python -c "import tkinter as tk; r = tk.Tk(); r.destroy(); print('tk ok')"
   ```

If needed as a temporary workaround, set these environment variables to your
Python Tcl directories before launching:

```powershell
$env:TCL_LIBRARY = "C:\Path\To\Python\tcl\tcl8.6"
$env:TK_LIBRARY  = "C:\Path\To\Python\tcl\tk8.6"
```

## Development
Run script-based validation (CI baseline):
```bash
python tests/run_script_tests.py
```

Run pytest-native tests (optional while migration is in progress):
```bash
pytest -q
```

## Build Windows Executable
Install UI/build extras and run the build script:
```bash
python -m pip install -e ".[ui]"
python ui/build_exe.py
```
The build output is created under `ui/dist/RoundnetMatchmaking/`.

## Release Model
- Build artifacts are not committed to source control.
- Publish executable bundles through GitHub Releases.

## Repository Layout
- `core/`: matchmaking engine and domain logic.
- `ui/`: desktop UI and executable build script.
- `tests/`: automated test suite.
- `docs/`: technical and build documentation.
