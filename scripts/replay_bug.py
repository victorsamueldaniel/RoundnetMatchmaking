#!/usr/bin/env python3
"""Replay a bug report: install its environment and relaunch the app.

Usage
-----
    python scripts/replay_bug.py <path_to_bug_folder>

What it does
------------
1. Prints the bug_info.json summary (timestamp, version, OS, traceback).
2. Backs up the current preference JSONs and xlsx_config.json.
3. Installs the bug report's ui_accessible.json and extra_parameters.json.
4. Copies players_anonymized.xlsx -> ui/xlsx/players_debug.xlsx and writes a
   temporary xlsx_config.json pointing to it.
5. Prints the session pkl path so you can load it via the UI's Load Session
   button.
6. Launches the app with subprocess.
7. After the app closes, restores every backed-up file and removes the
   temporary players_debug.xlsx.

This script is dev-only and intentionally has no imports from the app package.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_bug_info(bug_dir: Path) -> None:
    info_path = bug_dir / "bug_info.json"
    if not info_path.is_file():
        print("[replay] WARNING: bug_info.json not found")
        return

    info = json.loads(info_path.read_text(encoding="utf-8"))
    print("\n" + "=" * 60)
    print("  Bug Report Summary")
    print("=" * 60)
    for key in ("timestamp", "app_version", "platform", "python_version", "trigger"):
        print(f"  {key:16s}: {info.get(key, 'n/a')}")

    tb = info.get("traceback")
    if tb:
        print("\n  Traceback:")
        for line in tb.splitlines():
            print(f"    {line}")

    warnings = info.get("warnings") or []
    if warnings:
        print("\n  Warnings:")
        for w in warnings:
            print(f"    ! {w}")

    print("=" * 60 + "\n")


def _find_session_pkl(bug_dir: Path) -> Path | None:
    session_dir = bug_dir / "session"
    if not session_dir.is_dir():
        return None
    for p in session_dir.rglob("*.pkl"):
        if not p.name.endswith("_read_only.pkl"):
            return p
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/replay_bug.py <path_to_bug_folder>")
        sys.exit(1)

    bug_dir = Path(sys.argv[1]).resolve()
    if not bug_dir.is_dir():
        print(f"[replay] ERROR: '{bug_dir}' is not a directory")
        sys.exit(1)

    # Resolve project root — scripts/ sits one level below it.
    project_root = Path(__file__).resolve().parent.parent
    prefs_dir = project_root / "ui" / "user_preferences"
    xlsx_dir = project_root / "ui" / "xlsx"
    xlsx_config_path = xlsx_dir / "xlsx_config.json"

    _print_bug_info(bug_dir)

    # Print session pkl for manual loading.
    pkl = _find_session_pkl(bug_dir)
    if pkl:
        print(f"[replay] Session pkl : {pkl}")
        print("[replay] Use the 'Load Session' button inside the app to open it.\n")
    else:
        print("[replay] No session pkl found in bug folder.\n")

    # ── Backup current config files ──────────────────────────────────────
    backups: list[tuple[Path, Path]] = []  # (original, backup_copy)

    def _backup(src: Path) -> None:
        if src.is_file():
            bak = src.with_suffix(src.suffix + ".replay_bak")
            shutil.copy2(src, bak)
            backups.append((src, bak))
            print(f"[replay] Backed up   {src.name}")

    _backup(prefs_dir / "ui_accessible.json")
    _backup(prefs_dir / "extra_parameters.json")
    _backup(xlsx_config_path)

    # Track extra files created during replay so we can clean up.
    created: list[Path] = []

    try:
        # ── Install bug-report preferences ───────────────────────────────
        for fname in ("ui_accessible.json", "extra_parameters.json"):
            src = bug_dir / fname
            if src.is_file():
                dst = prefs_dir / fname
                shutil.copy2(src, dst)
                print(f"[replay] Installed   {fname}")
            else:
                print(f"[replay] WARNING: {fname} not in bug folder — skipped")

        # ── Install players xlsx ─────────────────────────────────────────
        players_src = bug_dir / "players_anonymized.xlsx"
        if players_src.is_file():
            players_dst = xlsx_dir / "players_debug.xlsx"
            shutil.copy2(players_src, players_dst)
            created.append(players_dst)
            print("[replay] Installed   players_debug.xlsx")

            xlsx_config_path.write_text(
                json.dumps({"players": "players_debug.xlsx"}, indent=2),
                encoding="utf-8",
            )
            print("[replay] Updated     xlsx_config.json\n")
        else:
            print(
                "[replay] WARNING: players_anonymized.xlsx not in bug folder — skipped\n"
            )

        # ── Launch app ───────────────────────────────────────────────────
        print("[replay] Launching app …\n")
        subprocess.run(
            [sys.executable, "-m", "ui.main.roundnet_matchmaking_ui"],
            cwd=str(project_root),
        )

    finally:
        # ── Restore original files ───────────────────────────────────────
        print("\n[replay] Restoring original environment …")
        for original, bak in backups:
            shutil.copy2(bak, original)
            bak.unlink(missing_ok=True)
            print(f"[replay] Restored    {original.name}")
        for p in created:
            if p.is_file():
                p.unlink()
                print(f"[replay] Removed     {p.name}")
        print("[replay] Done. Environment restored.")


if __name__ == "__main__":
    main()
