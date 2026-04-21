"""Run repository script-style test files in a CI-friendly way."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPT_TESTS = [
    Path("tests/test_iterations.py"),
    Path("tests/test_post_processing.py"),
    Path("tests/test_pickle.py"),
    Path("tests/tests_fine_tuning.py"),
]


def run_script(script_path: Path) -> tuple[int, float]:
    full_path = ROOT / script_path
    if not full_path.exists():
        print(f"[MISSING] {script_path}")
        return 1, 0.0

    print(f"\n[RUN] {script_path}")
    started = time.perf_counter()
    result = subprocess.run([sys.executable, str(full_path)], cwd=ROOT, check=False)
    duration = time.perf_counter() - started

    if result.returncode == 0:
        print(f"[PASS] {script_path} ({duration:.2f}s)")
    else:
        print(f"[FAIL] {script_path} ({duration:.2f}s, exit={result.returncode})")

    return result.returncode, duration


def main() -> int:
    print("Script-based test runner")
    print(f"Python executable: {sys.executable}")

    failed = []
    total_seconds = 0.0

    for script in SCRIPT_TESTS:
        code, duration = run_script(script)
        total_seconds += duration
        if code != 0:
            failed.append((script, code))

    print("\nSummary")
    print(f"Total scripts: {len(SCRIPT_TESTS)}")
    print(f"Failed scripts: {len(failed)}")
    print(f"Total duration: {total_seconds:.2f}s")

    if failed:
        for script, code in failed:
            print(f" - {script} (exit={code})")
        return 1

    print("All script-based tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
