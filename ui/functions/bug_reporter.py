"""Bug report collector for Roundnet Matchmaking.

Creates BUG/bug_YYYY-MM-DD_HH-MM-SS/ packages containing:
  - app.log                  (copy of BUG/app_current.log)
  - bug_info.json            (metadata + optional traceback)
  - players_anonymized.xlsx  (Name/Surname replaced by Player_N)
  - ui_accessible.json
  - extra_parameters.json
  - session/                 (copy of most-recent session folder)

Public API
----------
  init_log_file()                -> str   call once in main() before tk.Tk()
  collect_bug_report(app, ...)   -> str   path to the created package folder
"""

from __future__ import annotations

import datetime
import json
import os
import platform
import re
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# BUG directory resolution  (same frozen/dev pattern as ui_helpers.py)
# ---------------------------------------------------------------------------


def _resolve_bug_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "BUG")
    project_root = Path(__file__).resolve().parents[2]
    return str(project_root / "BUG")


BUG_DIR: str = _resolve_bug_dir()
_CURRENT_LOG_PATH: str = os.path.join(BUG_DIR, "app_current.log")

# ---------------------------------------------------------------------------
# Log file initialisation
# ---------------------------------------------------------------------------


def init_log_file() -> str:
    """Ensure BUG/ exists, truncate app_current.log, wire path into ui_helpers.
    Also writes startup_info.json, last_prefs/, and players_anonymized.xlsx so
    that useful debug state is always present even if the app crashes silently.

    Call once at the very start of main(), before tk.Tk().
    Returns the absolute path to the log file.
    """
    os.makedirs(BUG_DIR, exist_ok=True)

    # Truncate (overwrite) the rolling log on each new launch.
    with open(_CURRENT_LOG_PATH, "w", encoding="utf-8") as fh:
        fh.write(
            f"[log] Session started: "
            f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"[log] Python {sys.version}\n"
            f"[log] Platform: {platform.platform()}\n"
        )

    # Tell ConsoleRedirector where to tee stdout output.
    try:
        import ui.functions.ui_helpers as _ui_helpers  # noqa: PLC0415

        _ui_helpers._log_file_path = _CURRENT_LOG_PATH
    except Exception:
        pass

    # Resolve project root from this file's location (ui/functions/bug_reporter.py
    # → project root is two levels up).
    project_root = str(Path(__file__).resolve().parents[2])

    # ── startup_info.json ─────────────────────────────────────────────────
    try:
        startup_info = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "app_version": _read_app_version(project_root),
            "python_version": sys.version,
            "platform": platform.platform(),
        }
        with open(
            os.path.join(BUG_DIR, "startup_info.json"), "w", encoding="utf-8"
        ) as fh:
            json.dump(startup_info, fh, indent=2, ensure_ascii=False)
    except Exception:
        pass

    # ── last_prefs/ snapshot ──────────────────────────────────────────────
    try:
        prefs_dir = os.path.join(project_root, "ui", "user_preferences")
        last_prefs_dir = os.path.join(BUG_DIR, "last_prefs")
        os.makedirs(last_prefs_dir, exist_ok=True)
        for fname in ("ui_accessible.json", "extra_parameters.json"):
            src = os.path.join(prefs_dir, fname)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(last_prefs_dir, fname))
    except Exception:
        pass

    # ── players_anonymized.xlsx ───────────────────────────────────────────
    try:
        players_src = _resolve_players_xlsx(project_root)
        if players_src:
            _anonymize_xlsx(
                players_src, os.path.join(BUG_DIR, "players_anonymized.xlsx")
            )
    except Exception:
        pass

    return _CURRENT_LOG_PATH


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _read_app_version(project_root: str) -> str:
    """Extract version from pyproject.toml; return 'unknown' on failure."""
    try:
        toml_path = os.path.join(project_root, "pyproject.toml")
        with open(toml_path, "r", encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r'^\s*version\s*=\s*"([^"]+)"', line)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return "unknown"


def _anonymize_xlsx(src: str, dst: str) -> tuple[bool, str]:
    """Copy src xlsx to dst with Name/Surname columns replaced by Player_N.

    Returns (True, "") on success, (False, error_message) on failure.
    On failure a raw (non-anonymized) copy is placed at dst.
    """
    # Same alias map as core/data_loader.py — keeps the two in sync.
    _NAME_ALIASES = {"Name", "Prénom", "Prénom - First name"}
    _SURNAME_ALIASES = {"Surname", "Nom", "Nom - Surname"}
    _NAMESURNAME_ALIASES = {"NameSurname"}
    try:
        import pandas as pd  # noqa: PLC0415

        df = pd.read_excel(src)
        # Match data_loader: strip whitespace from column headers before matching.
        df.columns = [str(c).strip() for c in df.columns]
        n = len(df)
        player_ids = [f"Player_{i + 1}" for i in range(n)]
        for col in list(df.columns):
            if col in _NAME_ALIASES:
                df[col] = player_ids
            elif col in _SURNAME_ALIASES:
                df[col] = ""
            elif col in _NAMESURNAME_ALIASES:
                df[col] = player_ids
        df.to_excel(dst, index=False)
        return True, ""
    except Exception as exc:  # noqa: BLE001
        shutil.copy2(src, dst)
        return False, str(exc)


def _find_most_recent_session(app, project_root: str) -> str | None:
    """Return path to the most-recent session folder, or None."""
    # Prefer the active session tracked by the running UI.
    active = getattr(app, "_active_session_folder", None)
    if active and os.path.isdir(active):
        return active

    # Fall back to the most-recently-modified subfolder in sessions/.
    for candidate in (
        os.path.join(project_root, "sessions"),
        os.path.join(os.getcwd(), "sessions"),
    ):
        if os.path.isdir(candidate):
            subdirs = [
                os.path.join(candidate, d)
                for d in os.listdir(candidate)
                if os.path.isdir(os.path.join(candidate, d))
            ]
            if subdirs:
                return max(subdirs, key=os.path.getmtime)
    return None


def _resolve_players_xlsx(project_root: str) -> str | None:
    """Return absolute path to the configured players xlsx, or None."""
    try:
        xlsx_dir = os.path.join(project_root, "ui", "xlsx")
        config_path = os.path.join(xlsx_dir, "xlsx_config.json")
        with open(config_path, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
        filename = cfg.get("players", "players.xlsx")
        full = os.path.join(xlsx_dir, filename)
        return full if os.path.isfile(full) else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def collect_bug_report(app, traceback_str: str | None = None) -> str:
    """Collect a bug report package and return the path to the new folder.

    Parameters
    ----------
    app:
        The running PlayerSelectionUI instance.  Used to locate the active
        session folder and read the project root via current_dir.
    traceback_str:
        Formatted traceback string for crash-triggered reports.
        Pass None (default) for manually-triggered reports from the UI.
    """
    from ui.functions.ui_helpers import current_dir  # noqa: PLC0415

    project_root = current_dir
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    pkg_dir = os.path.join(BUG_DIR, f"bug_{timestamp}")
    os.makedirs(pkg_dir, exist_ok=True)

    warnings: list[str] = []

    # ── 1. app.log ────────────────────────────────────────────────────────
    if os.path.isfile(_CURRENT_LOG_PATH):
        shutil.copy2(_CURRENT_LOG_PATH, os.path.join(pkg_dir, "app.log"))
    else:
        warnings.append("app_current.log not found — app.log omitted")

    # ── 2. players_anonymized.xlsx ────────────────────────────────────────
    players_src = _resolve_players_xlsx(project_root)
    if players_src:
        dst = os.path.join(pkg_dir, "players_anonymized.xlsx")
        ok = _anonymize_xlsx(players_src, dst)
        if not ok:
            warnings.append(
                "WARNING_NOT_ANONYMIZED: anonymization failed, raw xlsx copied"
            )
    else:
        warnings.append("players xlsx not found — omitted")

    # ── 3 & 4. preference JSONs ───────────────────────────────────────────
    prefs_dir = os.path.join(project_root, "ui", "user_preferences")
    for fname in ("ui_accessible.json", "extra_parameters.json"):
        src = os.path.join(prefs_dir, fname)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(pkg_dir, fname))
        else:
            warnings.append(f"{fname} not found — omitted")

    # ── 5. session/ ───────────────────────────────────────────────────────
    session_src = _find_most_recent_session(app, project_root)
    if session_src:
        dst_session = os.path.join(pkg_dir, "session")
        shutil.copytree(session_src, dst_session)
    else:
        warnings.append("no session folder found — omitted")

    # ── 6. bug_info.json  (written last so it can include all warnings) ───
    bug_info = {
        "timestamp": timestamp,
        "app_version": _read_app_version(project_root),
        "python_version": sys.version,
        "platform": platform.platform(),
        "trigger": "crash" if traceback_str else "manual",
        "traceback": traceback_str or None,
        "warnings": warnings,
    }
    with open(os.path.join(pkg_dir, "bug_info.json"), "w", encoding="utf-8") as fh:
        json.dump(bug_info, fh, indent=2, ensure_ascii=False)

    print(f"[bug] Report saved: {pkg_dir}")
    return pkg_dir
