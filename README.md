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

Preferred launch mode:
- Use the installed command `roundnet-matchmaking`.
- For development, use module execution from repo root: `python -m ui.player_selection_ui`.
- Avoid direct file execution (`python ui/player_selection_ui.py`) because it can bypass package import context.

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
