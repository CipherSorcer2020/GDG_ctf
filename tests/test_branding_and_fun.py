"""Club branding, synchronized start countdown, live feed, first-solver badge."""
import time

import pytest

from conftest import flag_of, start_game
from ctf_runner.event import EVENT_LOG_MAX


# ------------------------------------------------------------------ branding / logo

def test_state_carries_the_club_branding(client):
    s = client.get("/api/state").json()
    assert s["brand"]["club"] == "GDG Universiapolis" and s["event"]["name"]


def test_logo_placeholder_then_custom_logo(client, demo_event):
    r = client.get("/brand/logo")
    assert r.status_code == 200 and b"<svg" in r.content
    (demo_event.root / "brand").mkdir(exist_ok=True)
    (demo_event.root / "brand" / "logo.png").write_bytes(b"\x89PNG-fake")
    assert client.get("/brand/logo").content == b"\x89PNG-fake"      # picked up with no restart


def test_the_pages_use_google_sans_and_the_four_google_colours():
    from ctf_runner.server import WEB_DIR
    css = (WEB_DIR / "css" / "theme.css").read_text()
    for token in ("Google Sans", "#4285f4", "#ea4335", "#fbbc04", "#34a853"):
        assert token in css
    assert (WEB_DIR / "fonts" / "LICENSE-GoogleSans-OFL.txt").exists()       # font licence ships with the font


def test_fonts_are_self_hosted_no_external_requests():
    from ctf_runner.server import WEB_DIR
    for f in list(WEB_DIR.rglob("*.html")) + list(WEB_DIR.rglob("*.css")) + list(WEB_DIR.rglob("*.js")):
        text = f.read_text(encoding="utf-8")
        assert "fonts.googleapis" not in text and "fonts.gstatic" not in text and "cdn." not in text, f.name


# ------------------------------------------------------------------ countdown

def test_countdown_phases_and_locking(client, lobby):
    lobby.join("p")
    token = lobby.load().admin_token
    r = client.post("/api/lobby/start", json={"admin_token": token, "countdown": 5}).json()
    assert r["success"] and r["phase"] == "starting"
    s = client.get("/api/state?player=p").json()
    assert s["phase"] == "starting" and 3000 < s["starts_in_ms"] <= 5000 and "challenges" not in s
    assert client.get("/game").status_code == 403                              # still locked during the countdown
    assert client.get("/api/challenge/files/the-mole/mole.exe").status_code == 403
    assert client.post("/api/submit", json={"player": "p", "challenge": "coffee-break", "flag": "x"}).json()["status"] == "error"


def test_countdown_unlocks_when_it_reaches_zero(client, lobby, monkeypatch):
    lobby.join("p")
    client.post("/api/lobby/start", json={"admin_token": lobby.load().admin_token, "countdown": 5})
    real = time.time
    monkeypatch.setattr("ctf_runner.lobby.time.time", lambda: real() + 6)
    s = client.get("/api/state?player=p").json()
    assert s["phase"] == "active" and len(s["challenges"]) == 6
    assert client.get("/game").status_code == 200


def test_no_countdown_means_instant_start_and_validation(client, lobby):
    lobby.join("p")
    token = lobby.load().admin_token
    assert client.post("/api/lobby/start", json={"admin_token": token, "countdown": 999}).status_code == 422
    client.post("/api/lobby/start", json={"admin_token": token})
    assert client.get("/api/state?player=p").json()["phase"] == "active"


def test_reset_clears_a_running_countdown(client, lobby):
    token = lobby.load().admin_token
    client.post("/api/lobby/start", json={"admin_token": token, "countdown": 30})
    client.post("/api/lobby/reset", json={"admin_token": token})
    assert client.get("/api/state").json()["phase"] == "waiting"


# ------------------------------------------------------------------ feed / first blood

def test_feed_and_first_blood(client, lobby, demo_event):
    start_game(lobby, "ana", "ben")
    flag = flag_of(demo_event, "coffee-break")
    a = client.post("/api/submit", json={"player": "ana", "challenge": "coffee-break", "flag": flag}).json()
    b = client.post("/api/submit", json={"player": "ben", "challenge": "coffee-break", "flag": flag}).json()
    assert a["first_blood"] is True and b["first_blood"] is False
    s = client.get("/api/state?player=ben").json()
    assert [f["player"] for f in s["feed"]] == ["ben", "ana"]                  # newest first
    assert s["feed"][0]["title"] == "Coffee Break" and s["feed"][0]["points"] == 100
    card = next(c for c in s["challenges"] if c["name"] == "coffee-break")
    assert card["first"] == "ana" and card["solves"] == 2


def test_feed_is_empty_before_any_solve_and_cleared_by_wipe(client, lobby, demo_event):
    start_game(lobby, "ana")
    assert client.get("/api/state?player=ana").json()["feed"] == []
    client.post("/api/submit", json={"player": "ana", "challenge": "coffee-break", "flag": flag_of(demo_event, "coffee-break")})
    assert demo_event.load().events
    demo_event.wipe_progress()
    assert demo_event.load().events == []


def test_event_log_is_capped(demo_event):
    ev = demo_event.load()
    ev.events = [{"t": i, "player": "p", "challenge": "x", "points": 1} for i in range(EVENT_LOG_MAX + 50)]
    demo_event.save(ev)
    assert len(demo_event.load().events) == EVENT_LOG_MAX


def test_projector_board_needs_no_login_and_shows_scores(client, lobby, demo_event):
    start_game(lobby, "ana")
    client.post("/api/submit", json={"player": "ana", "challenge": "coffee-break", "flag": flag_of(demo_event, "coffee-break")})
    s = client.get("/api/state").json()                                      # no ?player= : exactly what /board polls
    assert s["scoreboard"][0] == {"player": "ana", "score": 100, "solves": 1} and s["challenges"] and s["feed"]


def test_installed_package_ships_every_web_asset():
    """`pip install .` (not just an editable install) must include fonts and images."""
    import tomllib
    from pathlib import Path
    from ctf_runner.server import WEB_DIR

    cfg = tomllib.loads((Path(WEB_DIR).parents[1] / "pyproject.toml").read_text())
    patterns = cfg["tool"]["setuptools"]["package-data"]["ctf_runner"]
    for f in WEB_DIR.rglob("*"):
        if f.is_file():
            rel = f.relative_to(WEB_DIR.parent).as_posix()
            assert any(Path(rel).match(p) for p in patterns), f"{rel} would be missing from a normal install"
