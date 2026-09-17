"""End-to-end checks of the web API with a small generated session."""

import io
import json

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from webapp.server.app import app

client = TestClient(app)


@pytest.fixture(scope="module")
def players():
    rng = np.random.default_rng(3)
    df = pd.DataFrame(
        [
            {
                "Prénom": f"joueur {i}",
                "Nom": "Test",
                "Genre": "F" if i % 3 == 0 else "M",
                "Niveau": round(float(rng.uniform(1, 4)), 1),
                "Masochiste": 3,
            }
            for i in range(18)
        ]
    )
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    result = client.post(
        "/api/players/parse", files={"file": ("players.xlsx", buffer.getvalue())}
    ).json()
    assert result["errors"] == []
    return result["players"]


@pytest.fixture(scope="module")
def generated(players):
    body = {
        "players": players,
        "amount_of_rounds": 3,
        "type_preferences": ["balanced", "level", "balanced"],
        "gender_preferences": ["open", "mixed", "open"],
        "preferred_pairs": [
            {"players": [players[0]["id"], players[1]["id"]], "games": 1}
        ],
        "extra_parameters": {"last_seed": 1, "num_iter": 40},
    }
    events = []
    with client.stream("POST", "/api/sessions/generate", json=body) as response:
        for line in response.iter_lines():
            events.append(json.loads(line))
    return events


def test_parse_normalises_names(players):
    assert players[0]["id"] == "Joueur0"
    assert players[0]["Gender"] == "Female"
    assert players[0]["Prey"] == 3


def test_generate_streams_progress_and_result(generated):
    kinds = [e["type"] for e in generated]
    assert kinds.count("progress") == 2
    assert kinds[-1] == "result"
    view = generated[-1]["view"]
    assert len(view["rounds"]) == 3
    assert view["charts"]["team"]["partner_edges"]
    assert all(e["count"] >= 1 for e in view["charts"]["team"]["partner_edges"])


def test_view_is_stable_and_breakdown_adds_up(generated):
    document = generated[-1]["document"]
    view = client.post("/api/sessions/view", json={"document": document}).json()
    assert view["summary"]["score"] == pytest.approx(
        generated[-1]["view"]["summary"]["score"]
    )
    for round_ in view["rounds"]:
        for game in round_["games"]:
            for slot in game["team_a"] + game["team_b"]:
                assert slot["breakdown"]["total"] == pytest.approx(slot["gain"])


def test_exports(generated):
    document = generated[-1]["document"]
    assert (
        client.post("/api/sessions/xlsx", json={"document": document}).status_code
        == 200
    )
    assert (
        client.post(
            "/api/sessions/xlsx?read_only=true", json={"document": document}
        ).status_code
        == 200
    )
    png = client.post(
        "/api/sessions/png", json={"document": document, "show_levels": True}
    )
    assert png.headers["content-type"] == "image/png"


def test_generate_rejects_huge_budgets(players):
    body = {
        "players": players,
        "amount_of_rounds": 1,
        "type_preferences": ["balanced"],
        "gender_preferences": ["open"],
        "extra_parameters": {"num_iter": 10**7},
    }
    assert client.post("/api/sessions/generate", json=body).status_code == 422


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda d: d["rounds"][0]["games"][0]["team_a"].__setitem__(0, "Ghost"),
        lambda d: d["rounds"][0]["bench"].append(
            d["rounds"][0]["games"][0]["team_b"][0]
        ),
        lambda d: d["players"][0].__setitem__("Level", "nan"),
        lambda d: d["players"].append(dict(d["players"][0])),
        lambda d: d["rounds"][0].__setitem__("type_preference", "chaos"),
    ],
)
def test_invalid_documents_are_rejected_everywhere(generated, corrupt):
    import copy

    document = copy.deepcopy(generated[-1]["document"])
    corrupt(document)
    for path in (
        "/api/sessions/view",
        "/api/sessions/report",
        "/api/sessions/xlsx",
        "/api/sessions/png",
    ):
        assert client.post(path, json={"document": document}).status_code == 422


def test_views_are_identical_between_calls(generated):
    document = generated[-1]["document"]
    first = client.post("/api/sessions/view", json={"document": document}).json()
    second = client.post("/api/sessions/view", json={"document": document}).json()
    assert first == second


def test_too_many_games_per_round_is_rejected(players):
    body = {
        "players": players[:8],
        "amount_of_rounds": 1,
        "type_preferences": ["balanced"],
        "gender_preferences": ["open"],
        "games_per_round": 3,
    }
    assert client.post("/api/sessions/generate", json=body).status_code == 422
