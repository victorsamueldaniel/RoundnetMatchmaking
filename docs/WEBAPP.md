# Web app

The web app brings every feature of the desktop app to the browser, on a phone or a computer.
It reuses the Python engine in `core/` unchanged, so both apps produce the same sessions.

## Architecture

```
browser (React + TypeScript, webapp/frontend)
  │  players, settings, sessions kept in localStorage
  │  JSON over HTTP
  ▼
FastAPI server (webapp/server/app.py), stateless
  │
  ▼
core/ engine: generation, happiness, charts data, Excel and PNG export
```

- The server keeps no state and needs no database. Each request carries the players or the
  session document it works on.
- The heavy work (seed search) streams progress events as newline-delimited JSON, so the client
  shows the same progress bar and console output as the desktop app.
- At most two generations run at the same time; the next requests wait for a free slot.
- Inputs are bounded (200 players, 50 seeds, `num_iter` up to 5000, 5 MB Excel files).

### Session documents (`core/session_codec.py`)

A session is saved as JSON instead of a pickle file:

```json
{
  "version": 1,
  "seed": 3,
  "players": [{"id": "Alice", "Name": "Alice", "Level": 2.5, "Gender": "Female", "Prey": 5, "...": 5}],
  "params": {"lambda_weight": 2.0, "percentile": 33, "level_gap_tol": 1.1, "extra_parameters": {}},
  "preferred_pairs": [{"players": ["Alice", "Bob"], "games": 2}],
  "rounds": [
    {"type_preference": "balanced", "gender_preference": "open",
     "games": [{"team_a": ["Alice", "Bob"], "team_b": ["Chloe", "David"]}],
     "bench": ["Emile"]}
  ]
}
```

Only inputs and round structure are stored. Happiness, histories and statistics are recomputed
from the structure in chronological order, which is also what the desktop app does after
reordering rounds. `tests/test_session_codec.py` checks that a generated session reloads with
exactly the same happiness for every player.

Loading a JSON document cannot run code, unlike `pickle.load`.

### API

| Method and path | Purpose |
|---|---|
| `GET /api/health` | health check |
| `GET /api/defaults` | default UI settings and `extra_parameters` |
| `POST /api/players/parse` | validate and normalise a players Excel file |
| `POST /api/players/export` | players list to Excel |
| `POST /api/sessions/generate` | run the seed search, stream `progress`, `log`, then `result` |
| `POST /api/sessions/view` | recompute a session: summary, rounds with happiness breakdown, chart data |
| `POST /api/sessions/report` | text report (`print_all_results`) |
| `POST /api/sessions/xlsx?read_only=` | Excel export, editable or protected |
| `POST /api/sessions/png` | session games image |

## Screens and parity with the desktop app

| Desktop | Web |
|---|---|
| First-run wizard, missing values dialog | Same flow on the Session tab when no players are stored |
| Player grid, info panel, add/edit dialog | Same, plus a name filter; the ✎ button replaces right click on touch screens |
| Round preferences, parameter sliders, spectrum toggle | Same ranges and defaults |
| Preferred pairs dialog | Same (2 players, 1 to 4 forced games) |
| `extra_parameters_temp.json` edited by hand | "Advanced" dialog with a JSON editor, import, download, reset |
| Console output | Same text, with the ANSI colors rendered |
| Games Editor tab | Same interactions; on a phone one round at a time and a "Details" tap mode for the breakdown tooltip |
| Session Games tab | Same round swap, reset, show levels, apply; downloads for PNG, Excel, read-only Excel, JSON, report |
| Happiness / Spectrum / Team plot tabs | Same 12 charts, interactive (zoom, hover) |
| Contact tab and bug report folder | Same contact card; the bug report is a downloadable JSON file |
| Load Session (`.pkl`) | Load a `.json` session file, or reopen a recent session stored in the browser |
| Close dialog for selected players, female shift, pairs | A banner offers "Save as default" or "Discard" while they differ from the saved values |

### Intentional differences

- **Pickle sessions are not accepted.** Uploading a `.pkl` to a public server would let anyone run
  code on it. Sessions use the JSON format above.
- **Player edits and added players persist in the browser** until reset or until a new file is
  imported. "Export players" writes them back to an Excel file.
- **Spectrum types chosen during games** is a horizontal bar chart with percentages instead of a
  pie chart: the values are close to each other and easier to compare on bars.
- **Happiness evolution by round** draws every player in gray and lets you highlight one player,
  instead of a legend with up to 40 colors.
- **Session games view** is an HTML table on screen; the PNG download is the same image as the
  desktop app.

### Desktop bugs that the web app does not reproduce

- Round order swaps recompute every player's happiness history in the new order.
- The preferred-pair bonus in the editor uses the pairs stored in the session, not the pairs
  currently selected in the UI.
- Session statistics always match the players' happiness (the Excel summary was computed before
  the final recompute).
- Team A and B keep the same order in the Excel file as on screen.
- The bug report replaces every player name, including in the session.
