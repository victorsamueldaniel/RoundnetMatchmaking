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

## Development
Run tests:
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
