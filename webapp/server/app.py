"""FastAPI server for the Roundnet Matchmaking web app.

The server is stateless: the browser keeps players, settings and sessions, and
sends a session document with every request. The engine in core/ does all the
matchmaking work.
"""

import asyncio
import copy
import io
import json
import math
import os
import queue
import random
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
    DEFAULT_PARAMS,
    PLAYER_FIELDS,
    decode_session,
    encode_session,
    players_dataframe,
)
from ui.functions.preferences_manager import _EXTRA_DEFAULTS, _UI_DEFAULTS  # noqa: E402
from webapp.server import analysis, console  # noqa: E402

console.install()

MAX_PLAYERS = 200
MAX_ROUNDS = 20
MAX_SEEDS = 30
MAX_NUM_ITER = 2000
MAX_WAITING_GENERATIONS = 3
ROUND_TYPES = {"balanced", "level"}
ROUND_GENDERS = {"open", "mixed"}

# The engine draws from Python's global random generator and matplotlib's pyplot
# state is global too: one engine call at a time keeps seeds reproducible.
_engine_lock = threading.Lock()
_waiting_lock = threading.Lock()
_waiting_generations = 0


class _Cancelled(Exception):
    pass


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
    level_gap_tol: float = 0.7
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


def _invalid(message):
    return HTTPException(422, f"Invalid session document: {message}")


def validate_document(document):
    """Reject documents the engine cannot rebuild, before touching it."""
    players = document.get("players")
    rounds = document.get("rounds")
    if not isinstance(players, list) or not 4 <= len(players) <= MAX_PLAYERS:
        raise _invalid(f"between 4 and {MAX_PLAYERS} players are required")
    if not isinstance(rounds, list) or not 1 <= len(rounds) <= MAX_ROUNDS:
        raise _invalid(f"between 1 and {MAX_ROUNDS} rounds are required")
    ids = []
    for player in players:
        if not isinstance(player, dict) or not isinstance(player.get("id"), str):
            raise _invalid("every player needs a text id")
        try:
            level = float(player.get("Level"))
        except (TypeError, ValueError):
            level = math.nan
        if not math.isfinite(level):
            raise _invalid(f"player {player['id']} has no valid level")
        ids.append(player["id"])
    known = set(ids)
    if len(known) != len(ids):
        raise _invalid("duplicate player ids")
    for index, round_ in enumerate(rounds, start=1):
        if not isinstance(round_, dict):
            raise _invalid(f"round {index} is malformed")
        if (
            round_.get("type_preference") not in ROUND_TYPES
            or round_.get("gender_preference") not in ROUND_GENDERS
        ):
            raise _invalid(f"round {index} has an unknown type or gender preference")
        names = list(round_.get("bench") or [])
        for game in round_.get("games") or []:
            team_a, team_b = game.get("team_a"), game.get("team_b")
            if not (isinstance(team_a, list) and isinstance(team_b, list)) or (
                len(team_a),
                len(team_b),
            ) != (2, 2):
                raise _invalid(f"round {index} has a game without two teams of two")
            names += team_a + team_b
        if len(set(names)) != len(names):
            raise _invalid(f"round {index} lists a player twice")
        if not set(names) <= known:
            raise _invalid(f"round {index} names an unknown player")


def _decode(document):
    """Validate and rebuild a session. The caller holds the engine lock."""
    validate_document(document)
    # Spectrum ties are broken at random: a fixed seed keeps every view identical.
    random.seed(0)
    return decode_session(document)


def session_view(document):
    """Everything the client displays for a session document."""
    session = _decode(document)
    params = document.get("params") or {}
    lambda_weight = float(params.get("lambda_weight", DEFAULT_PARAMS["lambda_weight"]))
    percentile = float(params.get("percentile", DEFAULT_PARAMS["percentile"]))
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
    if request.games_per_round and request.games_per_round > len(request.players) // 4:
        raise HTTPException(
            422,
            f"{len(request.players)} players allow at most {len(request.players) // 4} games per round.",
        )

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
        "games_per_round": (
            request.games_per_round if request.games_per_round is not None else "auto"
        ),
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
    cancelled = threading.Event()

    global _waiting_generations
    with _waiting_lock:
        if _waiting_generations >= MAX_WAITING_GENERATIONS:
            raise HTTPException(429, "The server is busy, please retry in a minute.")
        _waiting_generations += 1

    def progress(seed):
        if cancelled.is_set():
            raise _Cancelled()
        events.put(
            {"type": "progress", "seed": seed, "first": first_seed, "last": last_seed}
        )

    def run():
        global _waiting_generations
        try:
            with (
                _engine_lock,
                console.capture(lambda text: events.put({"type": "log", "text": text})),
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
                    preferred_pairs=pairs,
                    extra_parameters=extra,
                    first_seed=first_seed,
                    last_seed=last_seed,
                    spectrum=request.spectrum,
                    games_per_round_each_round=request.games_per_round
                    or len(players) // 4,
                    print_progress=bool(extra.get("print_progress", True)),
                    progress_callback=progress,
                )
                session._games_per_round_preference = params["games_per_round"]
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
                reloaded = _decode(document)
                print("=" * 80)
                print("SESSION RESULTS")
                print("=" * 80)
                reloaded.print_all_results(print_levels=True)
                result = {
                    "type": "result",
                    "document": document,
                    "view": session_view(document),
                }
            events.put(result)
        except _Cancelled:
            pass
        except Exception as exc:
            events.put({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        finally:
            with _waiting_lock:
                _waiting_generations -= 1
            events.put(None)

    threading.Thread(target=run, daemon=True).start()

    async def stream():
        try:
            while True:
                try:
                    event = events.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.05)
                    continue
                if event is None:
                    return
                yield json.dumps(event) + "\n"
        finally:
            # Runs when the client disconnects too: the generation stops at the next seed.
            cancelled.set()

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@app.post("/api/sessions/view")
def view(request: SessionRequest):
    with _engine_lock:
        return session_view(request.document)


@app.post("/api/sessions/report")
def report(request: SessionRequest):
    lines = []
    with _engine_lock, console.capture(lines.append):
        _decode(request.document).print_all_results(print_levels=True)
    return {"text": "".join(lines)}


@app.post("/api/sessions/xlsx")
def export_xlsx(request: SessionRequest, read_only: bool = False):
    with (
        _engine_lock,
        tempfile.TemporaryDirectory() as tmp,
        console.capture(lambda _t: None),
    ):
        session = _decode(request.document)
        session.export_to_excel(directory=tmp, filename="session.xlsx")
        name = "session_read_only.xlsx" if read_only else "session.xlsx"
        data = Path(tmp, name).read_bytes()
    return Response(
        data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.post("/api/sessions/png")
def export_png(request: PngRequest):
    with _engine_lock, tempfile.TemporaryDirectory() as tmp:
        session = _decode(request.document)
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
