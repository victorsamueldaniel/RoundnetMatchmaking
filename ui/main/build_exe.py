"""
Simple build script for Roundnet Matchmaking.

Usage:
    python build_exe.py [--version VERSION]

Examples:
    python build_exe.py
    python build_exe.py --version 1.2.0
        -> dist folder: RoundnetMatchmaking_1_2_0/
        -> Windows exe: RoundnetMatchmaking_1_2_0.exe
        -> macOS app:   RoundnetMatchmaking_1_2_0.app
        -> Linux bin:   RoundnetMatchmaking_1_2_0

What it does:
- builds a one-dir executable with PyInstaller (cross-platform)
- uses logo.ico (Windows/Linux) or logo.icns (macOS) as app icon
- copies required data files/modules next to the executable
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

APP_NAME = "RoundnetMatchmaking"
ENTRYPOINT = "ui/main/roundnet_matchmaking_ui.py"
ICON_ICO = "ui/logo.ico"
ICON_ICNS = "ui/logo.icns"
ICON_PNG = "ui/logo.png"

FILES_TO_COPY = [
    # NOTE: xlsx/ data files are NOT bundled here.
    # On first launch the app shows a setup wizard where the user selects their
    # own Excel files.  Those files are copied into xlsx/ at runtime.
    # xlsx_config.json is also written at runtime — do NOT pre-bundle it.
    # Core logic package
    "core/__init__.py",
    "core/data_loader.py",
    "core/models.py",
    "core/charts.py",
    "core/algorithm.py",
    "core/str_to_ascii.py",
    "core/pickle_helper.py",
    "core/main.py",
    "core/fine_tuning_functions.py",
    # UI package
    "ui/__init__.py",
    "ui/main/__init__.py",
    "ui/main/roundnet_matchmaking_ui.py",
    "ui/main/player_selection_ui.py",  # compatibility wrapper
    "ui/main/build_exe.py",
    "ui/tabs/__init__.py",
    "ui/tabs/session_generation_tab.py",
    "ui/tabs/games_editor_tab.py",
    "ui/tabs/session_games_tab.py",
    "ui/tabs/plots_tab/__init__.py",
    "ui/tabs/plots_tab/plots_tab.py",
    "ui/tabs/plots_tab/plots_base_tab.py",
    "ui/tabs/plots_tab/plots_happiness_tab.py",
    "ui/tabs/plots_tab/plots_spectrum_tab.py",
    "ui/tabs/plots_tab/plots_team_tab.py",
    "ui/tabs/plots_tab/plots_generic_tab.py",
    "ui/functions/__init__.py",
    "ui/functions/tab_functions.py",
    "ui/functions/setup_wizard.py",
    "ui/functions/ui_helpers.py",
    "ui/functions/bug_reporter.py",
    "ui/logo.png",
]

# Explicit hidden imports kept from previous build spirit.
HIDDEN_IMPORTS = [
    "tkinter",
    "tkinter.ttk",
    "tkinter.messagebox",
    "tkinter.scrolledtext",
    "_tkinter",
    "pandas",
    "numpy",
    "openpyxl",
    "seaborn",
    "networkx",
    "difflib",  # used by data_loader.validate_xlsx / SequenceMatcher
]

# Modules from the dev environment that must NOT be bundled.
# The Jupyter/IPython stack is the biggest culprit on machines with Jupyter installed.
EXCLUDE_MODULES = [
    # Jupyter / IPython stack
    "IPython",
    "ipython_genutils",
    "jedi",
    "parso",
    "jupyter_client",
    "jupyter_core",
    "ipykernel",
    "ipywidgets",
    "nbformat",
    "nbconvert",
    "nbclient",
    "traitlets",
    "comm",
    "debugpy",
    "prompt_toolkit",
    # ZMQ / async server bits Jupyter drags in
    "zmq",
    "tornado",
    "trio",
    "anyio",
    "sniffio",
    # Process / system monitoring (not used at runtime)
    "psutil",
    # Packaging helpers (not needed inside a frozen app)
    # NOTE: "distutils" must NOT be excluded – PyInstaller 6.x vendors it
    # internally and excluding it causes a ValueError during Analysis.
    "setuptools",
    "pkg_resources",
    # pytz ships ~600 timezone city files; the app only needs datetime.datetime.now()
    "pytz",
    # Scientific computing — not imported anywhere (transitive from numpy/matplotlib)
    "scipy",
    "scipy.libs",
    # Windows COM automation — not used
    "win32",
    "win32api",
    "win32com",
    "win32event",
    "win32trace",
    "win32pdh",
    "Pythonwin",
    "pywintypes",
    "pythoncom",
    "pywin32_system32",
    # SSL / network helpers — no HTTPS in the app
    "certifi",
    "charset_normalizer",
    "_ssl",
    "ssl",
    # Timezone data — only datetime.now() is used
    "tzdata",
    # SQLite — no database usage
    "_sqlite3",
    "sqlite3",
    # Jinja2 / MarkupSafe — template engine, not used
    "markupsafe",
    "jinja2",
]

REQUIRED_PYTHON_MODULES: dict[str, str] = {}


def _find_versioned_dir(parent: Path | None, prefix: str) -> Path | None:
    if parent is None or not parent.is_dir():
        return None

    candidates = [
        child
        for child in parent.iterdir()
        if child.is_dir() and child.name.lower().startswith(prefix.lower())
    ]
    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0]


def get_tk_bundle_args() -> list[str]:
    """Return PyInstaller args to package Tcl/Tk runtime data on Windows."""
    args: list[str] = []
    tcl_dir: Path | None = None
    tk_dir: Path | None = None

    try:
        import tkinter

        tcl_dir_raw = tkinter.Tcl().eval("info library")
        tcl_dir = Path(tcl_dir_raw)
    except Exception:
        tcl_dir = None

    search_roots = []
    for root in (sys.base_prefix, sys.prefix):
        if root and root not in search_roots:
            search_roots.append(root)

    if tcl_dir and tcl_dir.is_dir():
        tcl_parent = tcl_dir.parent
    else:
        tcl_parent = None
        for root in search_roots:
            candidate = Path(root) / "tcl"
            if candidate.is_dir():
                tcl_parent = candidate
                break
        tcl_dir = _find_versioned_dir(tcl_parent, "tcl") if tcl_parent else None

    if tcl_parent:
        tk_dir = _find_versioned_dir(tcl_parent, "tk")

    if tcl_dir and tcl_dir.is_dir():
        args.append(f"--add-data={tcl_dir}{os.pathsep}_tcl_data")
    if tk_dir and tk_dir.is_dir():
        args.append(f"--add-data={tk_dir}{os.pathsep}_tk_data")

    if os.name == "nt":
        for root in search_roots:
            dll_dir = Path(root) / "DLLs"
            if not dll_dir.is_dir():
                continue
            for dll_name in ("tcl86t.dll", "tk86t.dll", "tcl87t.dll", "tk87t.dll"):
                dll_path = dll_dir / dll_name
                if dll_path.is_file():
                    args.append(f"--add-binary={dll_path}{os.pathsep}.")

    tk_ext_spec = importlib.util.find_spec("_tkinter")
    if tk_ext_spec and tk_ext_spec.origin:
        tk_ext_path = Path(tk_ext_spec.origin)
        if tk_ext_path.is_file():
            args.append(f"--add-binary={tk_ext_path}{os.pathsep}.")

    return args


def ensure_pyinstaller() -> None:
    if importlib.util.find_spec("PyInstaller") is not None:
        return

    print("PyInstaller not found. Installing it...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def ensure_tkinter() -> None:
    try:
        import tkinter  # noqa: F401
        import _tkinter  # noqa: F401
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "tkinter is unavailable in this Python environment. "
            "Install/enable Tcl/Tk, then retry."
        ) from exc


def ensure_required_python_modules() -> None:
    missing_installs: list[str] = []
    for module_name, pip_spec in REQUIRED_PYTHON_MODULES.items():
        if importlib.util.find_spec(module_name) is None:
            missing_installs.append(pip_spec)

    if not missing_installs:
        return

    print(f"Installing missing Python modules: {', '.join(missing_installs)}")
    subprocess.check_call([sys.executable, "-m", "pip", "install", *missing_installs])


def ensure_icon(project_root: Path) -> Path | None:
    png_path = project_root / ICON_PNG

    if sys.platform == "darwin":
        icns_path = project_root / ICON_ICNS
        if icns_path.exists():
            return icns_path
        if not png_path.exists():
            return None
        try:
            from PIL import Image

            img = Image.open(png_path).convert("RGBA")
            img.save(icns_path, format="ICNS")
            print("Created logo.icns from logo.png")
            return icns_path
        except Exception as exc:
            print(f"[WARN] Could not generate logo.icns from logo.png: {exc}")
            return None

    # Windows / Linux: use .ico
    ico_path = project_root / ICON_ICO
    if ico_path.exists():
        return ico_path
    if not png_path.exists():
        return None
    try:
        from PIL import Image

        img = Image.open(png_path).convert("RGBA")
        sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
        img.save(ico_path, format="ICO", sizes=sizes)
        print("Created logo.ico from logo.png")
        return ico_path
    except Exception as exc:
        print(f"[WARN] Could not generate logo.ico from logo.png: {exc}")
        return None


def _remove_path_with_retries(path: Path, retries: int = 5) -> bool:
    for _ in range(retries):
        try:
            if path.exists():
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path, onerror=_on_rm_error)
                else:
                    os.chmod(path, stat.S_IWRITE)
                    path.unlink()
            return True
        except Exception:
            time.sleep(0.4)
    return not path.exists()


def _on_rm_error(func, path, exc_info) -> None:
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _rotate_dist_to_old(build_root: Path) -> None:
    dist_dir = build_root / "dist"
    old_dist_dir = build_root / "OLD_dist"

    if not old_dist_dir.exists() and not dist_dir.exists():
        return

    if old_dist_dir.exists() and not _remove_path_with_retries(old_dist_dir):
        raise RuntimeError(
            "Could not remove OLD_dist. Close Explorer windows and running EXEs, then retry."
        )

    if dist_dir.exists():
        try:
            dist_dir.replace(old_dist_dir)
            print("Renamed dist to OLD_dist")
        except Exception as exc:
            raise RuntimeError(f"Could not rename dist to OLD_dist: {exc}") from exc


def clean_previous_outputs(build_root: Path, project_root: Path, app_name: str) -> None:
    build_dir = build_root / "build"
    spec_file = build_root / f"{app_name}.spec"
    dist_dir = build_root / "dist"
    output_dir = dist_dir / app_name

    if build_dir.exists():
        shutil.rmtree(build_dir)
    if spec_file.exists():
        spec_file.unlink()

    _rotate_dist_to_old(build_root)
    dist_dir.mkdir(parents=True, exist_ok=True)

    # Safety net: ensure target output dir does not exist before PyInstaller starts.
    if output_dir.exists() and not _remove_path_with_retries(output_dir):
        raise RuntimeError(
            f"Could not remove existing output folder: {output_dir}. "
            "Close Explorer windows and running EXEs, then retry."
        )


def pyinstaller_command(
    build_root: Path, project_root: Path, icon_path: Path | None, app_name: str
) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        f"--name={app_name}",
        "--onedir",
        "--windowed",
        "--clean",
        "--noconfirm",
        f"--distpath={build_root / 'dist'}",
        f"--workpath={build_root / 'build'}",
        f"--specpath={build_root}",
    ]

    for module in HIDDEN_IMPORTS:
        cmd.append(f"--hidden-import={module}")

    # Do NOT use --collect-all/--collect-submodules for tkinter here.
    # get_tk_bundle_args() handles DLLs + data; adding collect-all duplicates tcl8/.

    for module in EXCLUDE_MODULES:
        cmd.append(f"--exclude-module={module}")
    cmd.extend(get_tk_bundle_args())

    if icon_path is not None:
        cmd.append(f"--icon={icon_path}")

    cmd.append(str(project_root / ENTRYPOINT))
    return cmd


# Sub-directories inside _internal/ that are safe to delete after the build.
STRIP_DIRS = [
    "_tk_data/demos",
    "matplotlib/mpl-data/sample_data",
    "matplotlib/mpl-data/plot_directive",
]


def strip_bloat(dist_app_dir: Path) -> None:
    """Remove known-unnecessary sub-directories from the built _internal/ folder."""
    internal = dist_app_dir / "_internal"
    if not internal.is_dir():
        return
    for rel in STRIP_DIRS:
        target = internal / rel.replace("/", os.sep)
        if target.exists():
            shutil.rmtree(target, onerror=_on_rm_error)
            print(f"  [STRIPPED] _internal/{rel}")


def copy_runtime_files(project_root: Path, dist_app_dir: Path) -> None:
    print("Copying required files...")
    for relative_name in FILES_TO_COPY:
        source = project_root / relative_name
        dest = dist_app_dir / relative_name
        if source.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            print(f"  [OK] {relative_name}")
        else:
            print(f"  [WARN] Missing: {relative_name}")


def build_exe(version: str | None = None) -> bool:
    # build_root = ui/main/ folder — build/, dist/, OLD_dist/ are created here
    build_root = Path(__file__).resolve().parent
    # project_root = workspace root — source files are relative to here
    project_root = build_root.parent.parent

    app_name = f"{APP_NAME}_{version.replace('.', '_')}" if version else APP_NAME
    dist_app_dir = build_root / "dist" / app_name

    print(f"Building {app_name}...")
    print(f"Python: {sys.executable}")

    ensure_pyinstaller()
    ensure_tkinter()
    ensure_required_python_modules()

    icon_path = ensure_icon(project_root)
    clean_previous_outputs(build_root, project_root, app_name)

    cmd = pyinstaller_command(build_root, project_root, icon_path, app_name)
    print("Running:")
    print(" ".join(cmd))

    try:
        subprocess.check_call(cmd, cwd=project_root)
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] Build failed: {exc}")
        return False

    if not dist_app_dir.exists():
        print(f"[ERROR] Expected output folder not found: {dist_app_dir}")
        return False

    copy_runtime_files(project_root, dist_app_dir)
    strip_bloat(dist_app_dir)

    # Create a zip archive next to the output folder.
    zip_path = build_root / "dist" / app_name
    print(f"\nCreating zip archive: {zip_path}.zip ...")
    shutil.make_archive(
        str(zip_path), "zip", root_dir=build_root / "dist", base_dir=app_name
    )
    print(f"  [OK] {zip_path}.zip")

    if sys.platform == "darwin":
        exe_path = dist_app_dir / f"{app_name}.app"
    elif sys.platform == "win32":
        exe_path = dist_app_dir / f"{app_name}.exe"
    else:
        exe_path = dist_app_dir / app_name
    print("\nBuild completed.")
    print(f"Executable: {exe_path}")
    print("Distribute the full folder or the zip:")
    print(f"  {dist_app_dir}")
    print(f"  {zip_path}.zip")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"Build {APP_NAME} executable.")
    parser.add_argument(
        "--version",
        metavar="VERSION",
        default=None,
        help="Optional version string (e.g. 1.2.0). Dots are replaced by underscores "
        "in the folder and exe name.",
    )
    args = parser.parse_args()
    version = args.version
    if version is None:
        version = input("Version (leave blank for none): ").strip() or None
    raise SystemExit(0 if build_exe(version=version) else 1)
# %%
