"""FastAPI server for the Roundnet Matchmaking web app.

The server is stateless: the browser keeps players, settings and sessions, and
sends a session document with every request. The engine in core/ does all the
matchmaking work.
"""

import copy
import io
import json
import math
import os
import queue
import tempfile
import threading
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import pandas as pd  # noqa: E402
from fastapi import FastAPI, File, HTTPException, UploadFile  # noqa: E402
from fastapi.concurrency import run_in_threadpool  # noqa: E402
from fastapi.responses import FileResponse, Response, StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from core.algorithm import (  # noqa: E402
    apply_preferred_pairs_happiness,
    force_preferred_pairs_in_session,
    run_session_generation_with_seed_optimization,
)
from core.charts import create_session_games_png  # noqa: E402
from core.data_loader import load_players_frame  # noqa: E402
from core.happiness_breakdown import round_breakdown  # noqa: E402
from core.models import mean_min_max_happiness_objective  # noqa: E402
from core.session_codec import (  # noqa: E402
    PLAYER_FIELDS,
    decode_session,
    encode_session,
    players_dataframe,
)
from ui.functions.preferences_manager import _EXTRA_DEFAULTS, _UI_DEFAULTS  # noqa: E402
from webapp.server import analysis, console  # noqa: E402

console.install()

MAX_PLAYERS = 200
MAX_SEEDS = 50
MAX_NUM_ITER = 5000
# matplotlib's pyplot state is global, so figure rendering is serialised.
_render_lock = threading.Lock()
# Generations are CPU heavy; extra requests wait for a free slot.
_generation_slots = threading.BoundedSemaphore(2)

app = FastAPI(title="Roundnet Matchmaking")


def _deep_merge(base, override):
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _clean(value):
    """Replace NaN with None so pandas values serialise as JSON."""
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "item"):
        return _clean(value.item())
    return value


class GenerateRequest(BaseModel):
    players: list[dict] = Field(min_length=4, max_length=MAX_PLAYERS)
    amount_of_rounds: int = Field(ge=1, le=10)
    type_preferences: list[str]
    gender_preferences: list[str]
    games_per_round: int | None = Field(default=None, ge=1, le=50)
    level_gap_tol: float = 1.1
    lambda_weight: float = 2.0
    percentile: float = Field(default=33, ge=0, le=100)
    female_shift: float = 0.0
    spectrum: bool = True
    preferred_pairs: list[dict] = []
    extra_parameters: dict = {}


class SessionRequest(BaseModel):
    document: dict


class PngRequest(BaseModel):
    document: dict
    show_levels: bool = False


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/defaults")
def defaults():
    return {
        "ui": _UI_DEFAULTS,
        "extra_parameters": _EXTRA_DEFAULTS,
        "player_fields": PLAYER_FIELDS,
    }


@app.post("/api/players/parse")
async def parse_players(file: UploadFile = File(...)):
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "File too large (5 MB max).")

    def parse():
        try:
            df = load_players_frame(io.BytesIO(content))
        except ValueError as exc:
            return {"errors": str(exc).split("\n  • ")[1:] or [str(exc)]}
        except Exception as exc:
            return {"errors": [f"Could not open file: {exc}"]}
        players = []
        for key, row in df.iterrows():
            player = {"id": str(key)}
            for field in PLAYER_FIELDS:
                player[field] = _clean(row.get(field))
            players.append(player)
        return {"errors": [], "players": players}

    return await run_in_threadpool(parse)


@app.post("/api/players/export")
def export_players(players: list[dict]):
    columns = ["NameSurname"] + PLAYER_FIELDS
    rows = [
        {"NameSurname": p.get("id"), **{f: p.get(f) for f in PLAYER_FIELDS}}
        for p in players
    ]
    buffer = io.BytesIO()
    pd.DataFrame(rows, columns=columns).to_excel(buffer, index=False)
    return Response(
        buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="players.xlsx"'},
    )


def _apply_female_shift(players, shift):
    """Shift female levels before matchmaking, like the desktop app."""
    if not shift:
        return players
    shifted = []
    for p in players:
        p = dict(p)
        if str(p.get("Gender") or "").strip().lower() in {"female", "f"}:
            p["Level"] = round(float(p.get("Level") or 0) + shift, 1)
        shifted.append(p)
    return shifted


def _pairs(entries):
    pairs = []
    for entry in entries:
        names = entry.get("players") or []
        if len(set(names)) == 2:
            pairs.append((frozenset(names), max(1, min(4, int(entry.get("games", 1))))))
    return pairs


def session_view(document):
    """Everything the client displays for a session document."""
    session = decode_session(document)
    params = document.get("params") or {}
    lambda_weight = float(params.get("lambda_weight", 2.0))
    percentile = float(params.get("percentile", 33))
    pair_awards = getattr(session, "_pair_happiness_per_round", {})
    rounds = analysis.rounds_view(session)
    for r_idx, round_obj in enumerate(session.rounds):
        breakdown = round_breakdown(round_obj, r_idx)
        for game in rounds[r_idx]["games"]:
            for player in game["team_a"] + game["team_b"]:
                player["breakdown"] = breakdown.get(player["name"])
                player["pair_bonus"] = pair_awards.get(
                    player["name"], [0] * len(rounds)
                )[r_idx]
    return {
        "summary": analysis.session_summary(session, lambda_weight, percentile),
        "rounds": rounds,
        "charts": {
            "happiness": analysis.happiness_overview(session),
            "team": analysis.team_analysis(session),
            "spectrum": analysis.spectrum_analysis(session),
        },
        "repetitions": analysis.repetitions(session),
    }


@app.post("/api/sessions/generate")
def generate(request: GenerateRequest):
    if (
        len(request.type_preferences) != request.amount_of_rounds
        or len(request.gender_preferences) != request.amount_of_rounds
    ):
        raise HTTPException(422, "One type and one gender preference per round.")
    ids = [p.get("id") for p in request.players]
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "Duplicate player ids.")

    extra = _deep_merge(_EXTRA_DEFAULTS, request.extra_parameters)
    first_seed = int(extra.get("first_seed", 0))
    last_seed = int(extra.get("last_seed", 9))
    if last_seed < first_seed or last_seed - first_seed + 1 > MAX_SEEDS:
        raise HTTPException(422, f"Seed range must contain 1 to {MAX_SEEDS} seeds.")

    if not 1 <= int(extra.get("num_iter", 435)) <= MAX_NUM_ITER:
        raise HTTPException(422, f"num_iter must be between 1 and {MAX_NUM_ITER}.")

    players = _apply_female_shift(request.players, request.female_shift)
    pairs = _pairs(request.preferred_pairs)
    params = {
        "level_gap_tol": request.level_gap_tol,
        "num_iter": int(extra["num_iter"]),
        "lambda_weight": request.lambda_weight,
        "percentile": request.percentile,
        "weight_same_teammate": extra["weight_same_teammate"],
        "never_met_bonus_per_player": extra["never_met_bonus_per_player"],
        "never_met_bonus_cap": extra["never_met_bonus_cap"],
        "spectrum": request.spectrum,
        "female_shift": request.female_shift,
        "extra_parameters": extra,
    }
    priority = {"level": 0, "balanced": 1}
    generated_order = sorted(
        range(request.amount_of_rounds),
        key=lambda i: (priority.get(request.type_preferences[i], 2), i),
    )
    reordering = [generated_order.index(i) + 1 for i in range(request.amount_of_rounds)]
    events = queue.Queue()

    def run():
        _generation_slots.acquire()
        try:
            with console.capture(
                lambda text: events.put({"type": "log", "text": text})
            ):
                print("Starting session generation...")
                print(f"Testing seeds {first_seed} to {last_seed}\n")
                session, seed = run_session_generation_with_seed_optimization(
                    df=players_dataframe(players),
                    amount_of_rounds=request.amount_of_rounds,
                    type_preferences=request.type_preferences,
                    gender_preferences=request.gender_preferences,
                    rounds_reordering=reordering,
                    level_gap_tol=request.level_gap_tol,
                    num_iter=params["num_iter"],
                    lambda_weight=request.lambda_weight,
                    objective_function=lambda x: mean_min_max_happiness_objective(
                        x,
                        lambda_weight=request.lambda_weight,
                        percentile=request.percentile,
                    ),
                    weight_same_teammate=params["weight_same_teammate"],
                    never_met_bonus_per_player=params["never_met_bonus_per_player"],
                    never_met_bonus_cap=params["never_met_bonus_cap"],
                    extra_parameters=extra,
                    first_seed=first_seed,
                    last_seed=last_seed,
                    spectrum=request.spectrum,
                    games_per_round_each_round=request.games_per_round
                    or len(players) // 4,
                    print_progress=bool(extra.get("print_progress", True)),
                    progress_callback=lambda s: events.put(
                        {
                            "type": "progress",
                            "seed": s,
                            "first": first_seed,
                            "last": last_seed,
                        }
                    ),
                )
                if pairs:
                    tolerance = extra["post_processing"][
                        "force_preferred_pairs_in_session"
                    ]
                    force_preferred_pairs_in_session(
                        session,
                        pairs,
                        lambda_weight=request.lambda_weight,
                        score_tolerance=float(tolerance.get("score_tolerance", 0.10)),
                    )
                    apply_preferred_pairs_happiness(session, pairs)
                params["rounds_reordering"] = reordering
                document = encode_session(session, players, params, pairs, seed=seed)
                reloaded = decode_session(document)
                print("=" * 80)
                print("SESSION RESULTS")
                print("=" * 80)
                reloaded.print_all_results(print_levels=True)
            events.put(
                {"type": "result", "document": document, "view": session_view(document)}
            )
        except Exception as exc:
            events.put({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        finally:
            _generation_slots.release()
            events.put(None)

    threading.Thread(target=run, daemon=True).start()

    def stream():
        while True:
            event = events.get()
            if event is None:
                return
            yield json.dumps(event) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@app.post("/api/sessions/view")
def view(request: SessionRequest):
    try:
        return session_view(request.document)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(422, f"Invalid session document: {exc}")


@app.post("/api/sessions/report")
def report(request: SessionRequest):
    lines = []
    session = decode_session(request.document)
    with console.capture(lines.append):
        session.print_all_results(print_levels=True)
    return {"text": "".join(lines)}


@app.post("/api/sessions/xlsx")
def export_xlsx(request: SessionRequest, read_only: bool = False):
    session = decode_session(request.document)
    session.rounds_reordering = (request.document.get("params") or {}).get(
        "rounds_reordering"
    )
    with tempfile.TemporaryDirectory() as tmp, console.capture(lambda _t: None):
        session.export_to_excel(directory=tmp, filename="session.xlsx")
        name = "session_read_only.xlsx" if read_only else "session.xlsx"
        data = Path(tmp, name).read_bytes()
    return Response(
        data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.post("/api/sessions/png")
def export_png(request: PngRequest):
    session = decode_session(request.document)
    with tempfile.TemporaryDirectory() as tmp, _render_lock:
        path = os.path.join(tmp, "session_games.png")
        create_session_games_png(session, path, show_levels=request.show_levels)
        data = Path(path).read_bytes()
    return Response(data, media_type="image/png")


_static_dir = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if _static_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = (_static_dir / path).resolve()
        if path and candidate.is_file() and _static_dir in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(_static_dir / "index.html")
