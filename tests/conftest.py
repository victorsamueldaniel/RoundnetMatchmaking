"""Pytest shared configuration and shared fixtures."""

from __future__ import annotations

import sys
import os

# Ensure the project root is importable whether or not the package is installed.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Shared DataFrames
# ---------------------------------------------------------------------------


def _make_df_8() -> pd.DataFrame:
    """8-player DataFrame: 4 male / 4 female, levels 1–3."""
    data = {
        "Name": ["Alice", "Bob", "Charlie", "David", "Eve", "Frank", "Grace", "Hugo"],
        "Surname": ["A", "B", "C", "D", "E", "F", "G", "H"],
        "Level": [1.0, 2.0, 3.0, 2.0, 1.0, 3.0, 2.0, 1.0],
        "Noisy level": [0.0] * 8,
        "Gender": [
            "Female",
            "Male",
            "Male",
            "Female",
            "Female",
            "Male",
            "Female",
            "Male",
        ],
        "Games played": [0] * 8,
        "Happiness": [0.0] * 8,
    }
    df = pd.DataFrame(data)
    df.set_index("Name", inplace=True)
    return df


def _make_df_6() -> pd.DataFrame:
    """6-player DataFrame: 3 male / 3 female, levels 1–3."""
    data = {
        "Name": ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"],
        "Surname": ["A", "B", "C", "D", "E", "F"],
        "Level": [1.0, 2.0, 3.0, 2.0, 1.0, 3.0],
        "Noisy level": [0.0] * 6,
        "Gender": ["Female", "Male", "Male", "Female", "Female", "Male"],
        "Games played": [0] * 6,
        "Happiness": [0.0] * 6,
    }
    df = pd.DataFrame(data)
    df.set_index("Name", inplace=True)
    return df


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def df_8() -> pd.DataFrame:
    return _make_df_8()


@pytest.fixture
def players_8(df_8):
    from core.models import Player

    return [Player(df_8.iloc[i]) for i in range(8)]


@pytest.fixture
def df_6() -> pd.DataFrame:
    return _make_df_6()


@pytest.fixture
def players_6(df_6):
    from core.models import Player

    return [Player(df_6.iloc[i]) for i in range(6)]
