# Building the Roundnet Matchmaking Executable

This repository is source-first. Generated artifacts are excluded from version control
and should be published through GitHub Releases.

## Prerequisites

1. Python 3.10 or higher.
2. A virtual environment (recommended).
3. Project dependencies installed with UI/build extras.

## Install Build Dependencies

From the repository root:

```bash
python -m pip install -e ".[ui]"
```

## Build Command

From the repository root:

```bash
python ui/build_exe.py
```

The build script creates a one-dir bundle at:

```text
ui/dist/RoundnetMatchmaking/
```

## Distribution Workflow

1. Build locally with `python ui/build_exe.py`.
2. Zip the folder `ui/dist/RoundnetMatchmaking/`.
3. Upload the zip as a GitHub Release artifact.

Do not commit generated folders such as:

- `ui/build/`
- `ui/dist/`
- `ui/OLD_dist/`

## Troubleshooting

### tkinter not available

- Error example: `ModuleNotFoundError: No module named 'tkinter'`
- Fix: reinstall Python with Tcl/Tk enabled, then rebuild.

### `TclError: Can't find a usable init.tcl`

- Error example:

```text
TclError: Can't find a usable init.tcl ...
This probably means that Tcl wasn't installed properly.
```

- Cause: the active interpreter cannot locate its Tcl/Tk runtime folders.
- Fix order:
  1. Confirm interpreter path: `python -c "import sys; print(sys.executable)"`
  2. Recreate the venv from a Python installation that includes Tcl/Tk.
  3. Reinstall project dependencies: `python -m pip install -e ".[dev,ui]"`
  4. Validate tkinter in that shell:
     `python -c "import tkinter as tk; r = tk.Tk(); r.destroy(); print('tk ok')"`

- Optional temporary workaround before launch (PowerShell):

```powershell
$env:TCL_LIBRARY = "C:\Path\To\Python\tcl\tcl8.6"
$env:TK_LIBRARY  = "C:\Path\To\Python\tcl\tk8.6"
```

### Using notebooks with a venv (optional)

If you run project scripts from notebooks, install and register the kernel from
the same virtual environment:

```bash
python -m pip install ipykernel
python -m ipykernel install --user --name roundnet-matchmaking --display-name "Python (RoundnetMatchmaking)"
```

### Build fails because of missing packages

- Reinstall extras:

```bash
python -m pip install -e ".[ui]"
```

### Locked output folder on Windows

- Close explorer windows or running executables from prior builds.
- Re-run `python ui/build_exe.py`.

## Notes for Maintainers

- Build behavior is defined in `ui/build_exe.py`.
- Runtime sources copied into the executable bundle are configured in
  `FILES_TO_COPY` inside that script.
