"""Backward-compatible wrapper for the legacy module path."""

from ui.roundnet_matchmaking_ui import PlayerSelectionUI, main


__all__ = ["PlayerSelectionUI", "main"]


if __name__ == "__main__":
    main()
