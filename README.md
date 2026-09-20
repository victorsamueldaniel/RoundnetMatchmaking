# Roundnet Matchmaking

Roundnet Matchmaking builds balanced roundnet sessions: several rounds of 2 vs 2 games where
every player gets a fair share of games, partners and opponents, based on their level, gender and
spectrum preferences.

Version 2.0.0 is the first release where the full app is available both as a desktop application
and as a web app backed by the same Python engine.

The project ships two front ends on top of the same Python engine (`core/`):

- **Web app** (`webapp/`): works on a phone or a computer, and can be deployed on Railway.
- **Desktop app** (`ui/`): the original Tkinter application, packaged as an executable.

## Features

- Import players from an Excel file (French or English column names), fill in missing gender or
  level, add or edit players.
- Round preferences: number of rounds, games per round, `balanced` or `level` rounds, `open` or
  `mixed` gender rules.
- Optimization parameters: weight of the least happy players (bottom x%), maximal level gap,
  female level shift, spectrum on/off, preferred pairs forced together for 1 to 4 games, and
  advanced knobs (`extra_parameters`).
- Seed search with live progress and console output.
- Games editor: swap players inside a round, live preview of each player's happiness change,
  detailed happiness breakdown, undo, apply, score history with version restore.
- Session games view: reorder rounds, show levels, download the games image, the Excel files
  (editable and read-only), the session file and a text report.
- Charts: happiness overview, spectrum analysis, team analysis (partnership and opponent networks).

## Release highlights in 2.0.0

- Full web app with mobile-friendly workflows and Railway deployment support.
- JSON session documents for portable, safer web session storage and reloads.
- Better balanced-round search and multiple engine correctness fixes around histories,
  post-processing, exports, and image generation.
- CI coverage for both the Python backend and the web frontend build.

## Player file format

| Column | Required | Accepted names | Values |
|---|---|---|---|
| Name | yes | `Name`, `Prénom`, `Prénom - First name` | text |
| Surname | yes | `Surname`, `Nom`, `Nom - Surname` | text |
| Gender | yes | `Gender`, `Genre`, `Genre - Gender` | `Male`/`Female`, `M`/`F`, `Masculin`/`Féminin`, `Homme`/`Femme` |
| Level | yes | `Level`, `Niveau`, `Niveau moyen` | number, e.g. 1.0 to 5.0 |
| Prey, Equilibrist, Challenger, Chill, Hunter, Classist | no | `Masochiste` (Prey), `Équilibré` (Equilibrist), `Sadique` (Hunter), `Alchimiste` (Classist) | 0 to 10, blank means 5 |

Players with a missing gender or level are asked for right after the import.

## Web app

### Run it locally

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

### Deploy on Railway

1. Create a Railway project from this GitHub repository.
2. Railway picks up `railway.json` and builds the `Dockerfile` (client build, then Python image).
3. No environment variable is needed: the server listens on `$PORT` and `/api/health` is the
   health check.

To check the image locally:

```bash
docker build -t roundnet-matchmaking-web .
docker run --rm -p 8000:8000 roundnet-matchmaking-web
```

### Where data lives

The server stores nothing. Players, settings, advanced parameters and sessions are kept in the
browser (`localStorage`), and every request sends the data it needs. A session can be downloaded
as a `.json` file and loaded again later, on any device. See [docs/WEBAPP.md](docs/WEBAPP.md) for
the architecture and the differences with the desktop app.

## Desktop app

```bash
python -m pip install -e ".[dev]"
roundnet-matchmaking
```

- For development, run the module from the repo root: `python -m ui.main.roundnet_matchmaking_ui`.
- Avoid direct file execution (`python ui/main/roundnet_matchmaking_ui.py`), which bypasses the
  package import context.
- The desktop app still supports historical pickle-based session workflows. The web app does not:
  it uses JSON session documents only.
- Pre-built executables for Windows, macOS and Linux are attached to the
  [GitHub Releases](../../releases). To build one yourself:
  `python -m pip install -e ".[ui]"` then `python ui/main/build_exe.py` (output in `ui/main/dist/`).

### macOS first launch

The `.app` bundle is not signed. On first launch, right-click the app, choose **Open**, then
confirm with **Open**. Later launches work normally.

### Windows: `TclError: Can't find a usable init.tcl`

The active Python interpreter cannot find its Tcl/Tk files.

1. Check the interpreter: `python -c "import sys; print(sys.executable)"`.
2. Recreate the venv from a full Python install that includes Tcl/Tk, then reinstall the project.
3. Check tkinter: `python -c "import tkinter as tk; r = tk.Tk(); r.destroy(); print('tk ok')"`.

As a temporary workaround, point `TCL_LIBRARY` and `TK_LIBRARY` to your Python `tcl` folders.

## Development

```bash
pytest -q                                  # engine and web API tests
cd webapp/frontend && npm run build        # type check and build the client
```

For a full local web-app stack during development, run the FastAPI server and the Vite dev server
side by side as shown above in the Web app section.

## Repository layout

- `core/`: matchmaking engine, charts, Excel export, JSON session documents.
- `ui/`: desktop UI and executable build script.
- `webapp/server/`: FastAPI server used by the web app.
- `webapp/frontend/`: React + TypeScript client.
- `tests/`, `webapp/tests/`: automated tests.
- `docs/`: technical documentation.
