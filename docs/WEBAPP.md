# Web app

The web app brings every feature of the desktop app to the browser, on a phone or a computer.
Both apps call the same Python engine (`core/`) with the same parameters, so the matchmaking
logic is shared; only the screens differ.

This became the headline addition in version 2.0.0 and is now extended in 2.1.1
with compact mixed editor+games history persistence.

## Run it locally

Requirements: Python 3.11+ and Node.js 20.19+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev,web]"

cd webapp/frontend
npm ci
npm run build
cd ../..

uvicorn webapp.server.app:app --port 8000
```

Open http://localhost:8000. On a phone connected to the same network, start uvicorn with
`--host 0.0.0.0` and open `http://<computer-ip>:8000`.

The server is stateless: players, settings, advanced parameters, and recent sessions stay in the
browser unless you export them.

For frontend development with hot reload, run the API and the Vite dev server side by side:

Terminal 1, repo root:
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev,web]"

cd webapp/frontend
npm ci
npm run build
cd ../..

uvicorn webapp.server.app:app --port 8000 --reload   
```
Terminal 2:
```
cd webapp/frontend 
npm run dev                    
```
Then open http://localhost:5173.

The Vite dev server forwards `/api` calls to port 8000.


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
- The engine uses Python's global random generator, so engine calls run one at a time: a seed
  always gives the same session, even when several people generate at once. Up to 3 generations
  can wait in line; beyond that the server answers 429 ("busy, retry in a minute").
- A generation stops at the next seed when the browser disconnects.
- Inputs are bounded (200 players, 20 rounds, 30 seeds, `num_iter` up to 2000, 5 MB Excel files),
  and session documents are validated before use (unknown or repeated players, invalid levels).

## Release notes context

- The web app is intended to cover the same user workflows as the desktop app while avoiding
  desktop-only persistence assumptions.
- Session upload intentionally uses JSON documents only. Pickle support remains a desktop-only
  compatibility feature.
- Deployment is documented for Railway because the server is stateless and does not require a
  database or background worker.

### Session documents (`core/session_codec.py`)

A session is saved as JSON instead of a pickle file:

```json
{
  "version": 3,
  "seed": 3,
  "players": [{"id": "Alice", "Name": "Alice", "Level": 2.5, "Gender": "Female", "Prey": 5, "...": 5}],
  "availability": {"Alice": [true, true, false, true], "Bob": [true, true, true, true]},
  "params": {"lambda_weight": 2.0, "percentile": 33, "level_gap_tol": 0.7, "extra_parameters": {}},
  "preferred_pairs": [{"players": ["Alice", "Bob"], "games": 2}],
  "editor_and_games_history": {
    "initial_score": 31.42,
    "applies": [
      {
        "kind": "player_swaps",
        "score": 32.10,
        "swaps": [{"round_idx": 0, "player1_id": "Alice", "player2_id": "Bob"}]
      },
      {"kind": "round_reorder", "score": 31.95, "order": [1, 0, 2, 3]}
    ],
    "current_index": 1
  },
  "rounds": [
    {"type_preference": "balanced", "gender_preference": "open",
     "games": [{"team_a": ["Alice", "Bob"], "team_b": ["Chloe", "David"]}],
     "bench": ["Emile"], "not_available": ["Alice"]}
  ]
}
```

Only inputs and round structure are stored. Happiness, histories and statistics are recomputed
from the structure in chronological order, which is also what the desktop app does after
reordering rounds. `tests/test_session_codec.py` checks that a generated session reloads with
exactly the same happiness for every player.
When `editor_and_games_history` is present, applies are replayed in order across both editor swaps
and session-games round reorders. Loading JSON without this key stays compatible and simply
starts with no editor/games apply history.

Availability is encoded in the same round order as the saved `rounds` array, so the Session tab
matrix and Editor tab `not_available` data stay consistent after generation/reordering.
When partial participation reduces the number of available players in a round, generation now
auto-reduces that round's game count to the maximum feasible value instead of forcing an empty
round.
Benching fairness is evaluated in the same round order shown in the Session tab (display order),
so availability and bench balancing are consistent with what users see.
Roster spread `R` is computed at generation time from the full app roster (including players not
selected for the generated session), then stored in the session parameters for reproducible reloads.

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
| Player grid, info panel, add/edit dialog | Same, plus a name filter; the ✎ button replaces right click on touch screens; Selected players info includes an empty-by-default participation matrix (names as rows, rounds as columns), alphabetical add-player buttons, row removal by clicking name, and undo |
| Round preferences, parameter sliders, spectrum toggle | Same ranges and defaults |
| Preferred pairs dialog | Same (2 players, 1 to 4 forced games) |
| `extra_parameters_temp.json` edited by hand | "Advanced" dialog with a JSON editor, import, download, reset |
| Console output | Same text, with the ANSI colors rendered |
| Games Editor tab | Same interactions; on a phone one round at a time and a "Details" tap mode for the breakdown tooltip; "Benched out" and read-only "Not available" sections are shown separately |
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
