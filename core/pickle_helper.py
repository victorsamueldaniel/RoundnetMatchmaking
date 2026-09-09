# %%
"""
Helper module for safely pickling and unpickling SessionOfRounds objects.
This ensures proper handling of the class definitions and avoids the
"it's not the same object" pickle error.
"""

import pickle
import os
from datetime import datetime


def save_session(session_of_rounds, folder="session", filename=None):
    """
    Safely save a SessionOfRounds object to a pickle file.

    Parameters:
    - session_of_rounds: The SessionOfRounds object to save
    - folder: Directory to save the file (default: "session")
    - filename: Custom filename (default: uses current date)

    Returns:
    - str: Path to the saved file
    """
    # Get current date in day_month_year format

    # Generate filename if not provided
    if filename is None:
        filename = "session_of_rounds.pkl"

    # Ensure .pkl extension
    if not filename.endswith(".pkl"):
        filename += ".pkl"

    # Save the session_of_rounds as a pkl element in the dated folder
    file_path = os.path.join(folder, filename)

    try:
        with open(file_path, "wb") as f:
            pickle.dump(session_of_rounds, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"Session saved successfully to: {file_path}")
        return file_path
    except Exception as e:
        print(f"Error saving session: {e}")
        raise


def load_session(file_path):
    """
    Safely load a SessionOfRounds object from a pickle file.

    Parameters:
    - file_path: Path to the pickle file

    Returns:
    - SessionOfRounds: The loaded session object
    """
    # Ensure core models are importable for pickle deserialization
    import core.main as _main  # noqa: F401

    try:
        with open(file_path, "rb") as f:
            session_of_rounds = pickle.load(f)
        print(f"Session loaded successfully from: {file_path}")
        return session_of_rounds
    except Exception as e:
        print(f"Error loading session: {e}")
        print(f"\nIf you see 'it's not the same object' error, try:")
        print("1. Restarting your Python kernel")
        print("2. Re-importing the main module")
        print("3. Not reloading the main module between save and load")
        raise


def find_latest_session(folder="session"):
    """
    Find the most recent session file in the session folder.

    Parameters:
    - folder: Directory to search (default: "session")

    Returns:
    - str: Path to the most recent session file, or None if not found
    """
    if not os.path.exists(folder):
        print(f"Folder {folder} does not exist")
        return None

    # Find all pickle files recursively
    pkl_files = []
    for root, dirs, files in os.walk(folder):
        for file in files:
            if file.endswith(".pkl"):
                file_path = os.path.join(root, file)
                pkl_files.append((file_path, os.path.getmtime(file_path)))

    if not pkl_files:
        print(f"No pickle files found in {folder}")
        return None

    # Sort by modification time and return the most recent
    pkl_files.sort(key=lambda x: x[1], reverse=True)
    latest_file = pkl_files[0][0]
    print(f"Latest session file: {latest_file}")
    return latest_file


# %% Example usage
if __name__ == "__main__":
    # Example: Save a session
    # save_session(session_of_rounds)

    # Example: Load the latest session
    # latest = find_latest_session()
    # if latest:
    #     session = load_session(latest)

    # Example: Load a specific session
    # session = load_session("session/11_11_2025/session_of_rounds.pkl")
    pass
