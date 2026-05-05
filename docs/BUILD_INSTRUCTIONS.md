# Building the Roundnet Matchmaking Executable

This repository is source-first. Generated artifacts are excluded from version control
and should be published through GitHub Releases.

Builds are supported on **Windows**, **macOS (arm64 and x86_64)**, and **Linux**.

## Prerequisites

1. Python 3.10 or higher with Tcl/Tk enabled.
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
python ui/main/build_exe.py
```

The build script creates a one-dir bundle under `ui/main/dist/`:

| Platform | Output |
|---|---|
| Windows | `ui/main/dist/RoundnetMatchmaking/RoundnetMatchmaking.exe` |
| macOS | `ui/main/dist/RoundnetMatchmaking/RoundnetMatchmaking.app` |
| Linux | `ui/main/dist/RoundnetMatchmaking/RoundnetMatchmaking` |

## Automated Multi-Platform Builds (GitHub Actions)

Pushing a tag matching `v*.*.*` triggers the `.github/workflows/build.yml` workflow.
Four parallel jobs run on:

| Job | Runner | Artifact suffix |
|---|---|---|
| Windows | `windows-latest` | `_win_x64.zip` |
| macOS Apple Silicon | `macos-latest` | `_mac_arm64.zip` |
| macOS Intel | `macos-13` | `_mac_x86.zip` |
| Linux | `ubuntu-latest` | `_linux_x86_64.zip` |

All four zips are uploaded automatically to the GitHub Release created by the tag.

## Distribution Workflow

1. Create and push a version tag: `git tag v1.2.0 && git push origin v1.2.0`.
2. GitHub Actions builds all four platform artifacts automatically.
3. Zips appear as assets on the GitHub Release page.

Do not commit generated folders such as:

- `ui/main/build/`
- `ui/main/dist/`
- `ui/main/OLD_dist/`

## macOS — Gatekeeper (Unsigned App)

The distributed `.app` bundle is not notarised. On first launch macOS shows
*"App can't be opened because it's from an unidentified developer"*.

Workaround for end users:
1. Right-click (or Control-click) the `.app` file.
2. Select **Open** from the context menu.
3. Click **Open** in the confirmation dialog.

To remove this friction entirely, notarisation requires an Apple Developer account ($99/year).

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
- Re-run `python ui/main/build_exe.py`.

## Notes for Maintainers

- Build behaviour is defined in `ui/main/build_exe.py`.
- Runtime sources copied into the executable bundle are configured in
  `FILES_TO_COPY` inside that script.
- The CI workflow is defined in `.github/workflows/build.yml`.
