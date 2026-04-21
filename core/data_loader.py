"""
data_loader.py — loads and processes the single combined Excel data source.

Exports:
    main_df  — processed player DataFrame (index = unique "NameSurname" key)

Expected columns in the xlsx (after normalisation):
    Name, Surname, Gender, Level,
    Prey, Equilibrist, Challenger, Chill, Hunter, Classist  (all optional → 5)
"""

import json
import pandas as pd
import re
import os
import sys
from difflib import SequenceMatcher

# Compute absolute path to the xlsx/ directory regardless of CWD.
if getattr(sys, "frozen", False):
    _xlsx_dir = os.path.join(os.path.dirname(sys.executable), "xlsx")
else:
    _xlsx_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "xlsx"
    )

# Config file written by the first-run setup wizard.
XLSX_CONFIG_PATH = os.path.join(_xlsx_dir, "xlsx_config.json")

_DEFAULT_FILENAME = "players.xlsx"

_SPEC_COLS = ["Prey", "Equilibrist", "Challenger", "Chill", "Hunter", "Classist"]

# Column aliases → canonical names (applied before any validation or loading).
_COL_ALIASES = {
    "Prénom - First name": "Name",
    "Prénom": "Name",
    "Nom - Surname": "Surname",
    "Nom": "Surname",
    "Genre - Gender": "Gender",
    "Genre": "Gender",
    "Niveau moyen": "Level",
    "Niveau": "Level",
    "Masochiste": "Prey",
    "Équilibré": "Equilibrist",
    "Sadique": "Hunter",
    "Alchimiste": "Classist",
}

# Required columns (canonical names, after alias rename).
_REQUIRED_COLUMNS = ["Name", "Surname", "Gender", "Level"]


def _apply_aliases(df: pd.DataFrame) -> pd.DataFrame:
    """Rename known aliases to canonical column names."""
    return df.rename(columns=_COL_ALIASES)


def validate_xlsx(path: str, role: str = "players") -> list[str]:
    """
    Validate the single players xlsx file.
    Returns a (possibly empty) list of human-readable error strings.
    Does NOT raise — let the caller decide.

    Accepted column names: exact canonical English names OR any known alias
    defined in _COL_ALIASES (after stripping leading/trailing whitespace).
    """
    errors: list[str] = []
    try:
        df = pd.read_excel(path)
    except Exception as exc:
        errors.append(f"Could not open file: {exc}")
        return errors

    if df.empty and len(df.columns) == 0:
        errors.append("File appears to be empty (no columns found).")
        return errors

    # Strip whitespace from column names, then apply aliases
    df.columns = [str(c).strip() for c in df.columns]
    df = _apply_aliases(df)
    raw_cols = set(df.columns)

    # Build the set of ALL accepted names for each canonical column
    accepted: dict[str, set[str]] = {req: {req} for req in _REQUIRED_COLUMNS}
    for alias, canonical in _COL_ALIASES.items():
        if canonical in accepted:
            accepted[canonical].add(alias)

    for req in _REQUIRED_COLUMNS:
        if not raw_cols.intersection(accepted[req]):
            known = "', '".join(sorted(accepted[req] - {req}))
            hint = f" (or '{known}')" if known else ""
            errors.append(f"Missing required column: '{req}'{hint}")

    if not errors and len(df) == 0:
        errors.append("File has column headers but no player rows.")

    return errors


def load_xlsx_config() -> dict:
    """Return {'players': filename} dict from xlsx_config.json, or default."""
    if os.path.exists(XLSX_CONFIG_PATH):
        try:
            with open(XLSX_CONFIG_PATH, "r", encoding="utf-8") as fh:
                cfg = json.load(fh)
            if "players" in cfg:
                return cfg
        except Exception:
            pass
    return {"players": _DEFAULT_FILENAME}


def _build_namesurname_index(df: pd.DataFrame) -> pd.Series:
    """
    Given a DataFrame with 'Name' and 'Surname' columns (already normalised),
    return a Series (same index) with disambiguated NameSurname keys.
    """
    keys = df["Name"].copy()  # start with first name
    # Detect collisions and append surname letters until unique
    changed = True
    extra = pd.Series([""] * len(df), index=df.index)
    ptr = pd.Series([0] * len(df), index=df.index, dtype=int)
    surnames = df["Surname"].copy()

    while changed:
        changed = False
        full = keys + extra
        for i in df.index:
            for j in df.index:
                if i >= j:
                    continue
                if full[i] == full[j]:
                    changed = True
                    for idx in (i, j):
                        s = str(surnames[idx])
                        p = int(ptr[idx])
                        if p < len(s):
                            extra[idx] = extra[idx] + s[p]
                            ptr[idx] = p + 1
                        else:
                            extra[idx] = extra[idx] + str(p)
                            ptr[idx] = p + 1
                    full = keys + extra  # recompute after update
    return keys + extra


def load_data() -> pd.DataFrame:
    """Read the single players xlsx, resolve missing data, return main_df."""
    cfg = load_xlsx_config()
    path = os.path.join(_xlsx_dir, cfg["players"])

    errs = validate_xlsx(path)
    if errs:
        raise ValueError("Players file failed validation:\n  • " + "\n  • ".join(errs))

    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]
    df = _apply_aliases(df)

    # Fuzzy-rename any remaining close matches for required columns
    for req in _REQUIRED_COLUMNS:
        if req not in df.columns:
            best_col, best_ratio = None, 0.0
            for col in df.columns:
                r = SequenceMatcher(None, req.lower(), col.lower()).ratio()
                if r > best_ratio:
                    best_ratio, best_col = r, col
            if best_ratio >= 0.5 and best_col:
                df.rename(columns={best_col: req}, inplace=True)

    # Normalise Name / Surname: strip spaces, capitalise
    for col in ("Name", "Surname"):
        df[col] = df[col].apply(lambda x: re.sub(r"\s+", "", str(x)).capitalize())

    # Build unique NameSurname index
    df["NameSurname"] = _build_namesurname_index(df)
    df.set_index("NameSurname", inplace=True)
    df.index.name = "NameSurname"

    # Normalise Gender: "Masculin" / "Male" / "M" → "Male", everything else → "Female"
    # NaN / empty → kept as NaN so the wizard can fill them in
    def _norm_gender(v):
        if pd.isna(v):
            return float("nan")
        s = str(v).strip().lower()
        if s in ("masculin", "male", "m", "homme", "man"):
            return "Male"
        if s in ("feminin", "féminin", "female", "f", "femme", "woman"):
            return "Female"
        return float("nan")  # unknown → wizard will ask

    df["Gender"] = df["Gender"].apply(_norm_gender)

    # Level: coerce to float, NaN → wizard will ask
    df["Level"] = pd.to_numeric(df["Level"], errors="coerce")

    # Drop rows with no Name at all
    df = df[df["Name"].notna() & (df["Name"] != "Nan")]

    # Spectrum columns: accept old French names, fill missing with 5
    for col in _SPEC_COLS:
        if col not in df.columns:
            df[col] = float("nan")
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df[_SPEC_COLS] = df[_SPEC_COLS].fillna(5)

    # Derived columns expected by the rest of the app
    df["Category"] = df["Level"]
    df["Happiness"] = 0
    df["Games played"] = 0
    df["Noisy level"] = 0

    return df


# Load data at module level so `from data_loader import main_df` works.
# If no config / files exist yet (first run, before wizard) set main_df=None.
try:
    main_df = load_data()
except Exception as _load_err:
    main_df = None  # type: ignore[assignment]
