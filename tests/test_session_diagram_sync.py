"""Validate that generated session diagram docs are in sync with registry."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    generator = (
        ROOT / "docs" / "diagrams" / "session_creation" / "generate_session_diagram.py"
    )
    command = [sys.executable, str(generator), "--check"]
    print("Checking generated session diagram freshness...")
    result = subprocess.run(command, cwd=ROOT, check=False)
    return result.returncode


def test_session_diagram_sync():
    """SESSION_CREATION_DIAGRAM.md must be in sync with session_diagram_registry.json."""
    assert main() == 0, (
        "Session diagram is out of sync with registry. "
        "Run: python docs/diagrams/session_creation/generate_session_diagram.py"
    )


if __name__ == "__main__":
    raise SystemExit(main())
