"""Hosting-day behaviour: lobby gating, security, downloads, limits, polling."""
import io
import zipfile

import pytest

from conftest import flag_of, start_game
from ctf_runner.server import MAX_WRONG_FLAGS

ALL_FLAGS = ["coffee-break", "vacation-snaps", "intercepted", "the-mole", "interns-backup", "webgame"]


# ------------------------------------------------------------------ pages / admin

def test_pages_load(client):
    assert client.get("/").status_code == 200
    assert client.get("/admin").status_code == 200
    assert client.get("/board").status_code == 200
    for asset in ("js/app.js", "js/common.js", "js/admin.js", "js/game.js", "js/theme.js", "js/fx.js", "js/board.js",
                  "css/theme.css", "css/app.css", "css/game.css", "css/board.css", "img/logo.svg",
                  "fonts/google-sans-latin-wght-normal.woff2", "fonts/google-sans-code-latin-wght-normal.woff2"):
        assert client.get(f"/static/{asset}").status_code == 200, asset


def test_admin_page_never_contains_the_token(client, lobby):
    assert lobby.load().admin_token not in client.get("/admin").text


def test_admin_actions_need_the_token(client, lobby):
    for path in ("/api/lobby/start", "/api/lobby/reset", "/api/event/reset"):
        r = client.post(path, json={"admin_token": "guess"}).json()
        assert r["success"] is False, path
    assert not lobby.load().is_active()


def test_event_reset_is_protected_and_works(client, lobby, demo_event):
    token = lobby.load().admin_token
    start_game(lobby, "p")
    client.post("/api/submit", json={"player": "p", "challenge": "coffee-break", "flag": flag_of(demo_event, "coffee-break")})
    assert demo_event.load().solves
    assert client.post("/api/event/reset", json={"admin_token": "x"}).json()["success"] is False
    assert demo_event.load().solves                      # an anonymous caller cannot wipe the scores
    assert client.post("/api/event/reset", json={"admin_token": token}).json()["success"] is True
    assert demo_event.load().solves == {}


def test_admin_token_brute_force_is_throttled(client, lobby):
    for _ in range(8):
        client.post("/api/lobby/start", json={"admin_token": "bad"})
    r = client.post("/api/lobby/start", json={"admin_token": lobby.load().admin_token}).json()
    assert r["success"] is False and "wait" in r["message"]


# ------------------------------------------------------------------ lobby gating

def test_everything_locked_while_waiting(client, demo_event):
    s = client.get("/api/state?player=x").json()
    assert s["phase"] == "waiting" and "challenges" not in s and "scoreboard" not in s
    for path in ("/game", "/profile", "/robots.txt", "/confidential-schedule.txt",
                 "/game/api/levels" if False else "/api/challenge/files/the-mole/mole.exe",
                 "/api/challenge/zip/interns-backup"):
        assert client.get(path).status_code == 403, path
    lvl = client.get("/game/api/levels").json()
    assert lvl["ok"] is False and lvl["levels"] == []
    r = client.post("/api/submit", json={"player": "p", "challenge": "coffee-break", "flag": flag_of(demo_event, "coffee-break")})
    assert r.json()["status"] == "error"
    assert client.post("/game/api/check", json={"level": 1, "answer": "GHOST"}).json()["ok"] is False
    assert client.post("/game/api/hint", json={"level": 1, "n": 1}).json()["ok"] is False
    assert "started" in client.post("/game/api/chat", json={"level": 5, "message": "hi"}).json()["reply"]
    assert client.post("/game/api/assemble", json={"answers": {}}).json()["status"] == "error"


def test_waiting_state_lists_players(client, lobby):
    lobby.join("Ana")
    s = client.get("/api/state?player=ana").json()
    assert s["players"] == ["Ana"] and s["me"] == {"name": "Ana", "registered": True}


def test_start_unlocks_everything(client, lobby):
    start_game(lobby, "p")
    s = client.get("/api/state?player=p").json()
    assert s["phase"] == "active" and len(s["challenges"]) == 6
    assert client.get("/game").status_code == 200 and client.get("/robots.txt").status_code == 200


# ------------------------------------------------------------------ the state payload

def test_state_never_leaks_flags_or_early_lessons(client, lobby, demo_event):
    start_game(lobby, "p")
    body = client.get("/api/state?player=p").text
    for name in ALL_FLAGS:
        assert flag_of(demo_event, name) not in body, name
    for c in client.get("/api/state?player=p").json()["challenges"]:
        assert c["lesson"] == "" and c["solved"] is False


def test_lesson_appears_only_after_solving(client, lobby, demo_event):
    start_game(lobby, "p", "q")
    client.post("/api/submit", json={"player": "p", "challenge": "intercepted", "flag": flag_of(demo_event, "intercepted")})
    mine = {c["name"]: c for c in client.get("/api/state?player=p").json()["challenges"]}
    theirs = {c["name"]: c for c in client.get("/api/state?player=q").json()["challenges"]}
    assert mine["intercepted"]["lesson"] and mine["intercepted"]["solved"]
    assert theirs["intercepted"]["lesson"] == "" and not theirs["intercepted"]["solved"]


def test_challenges_sorted_easiest_first(client, lobby):
    start_game(lobby, "p")
    pts = [c["points"] for c in client.get("/api/state?player=p").json()["challenges"]]
    assert pts == sorted(pts)


def test_etag_gives_304_until_something_changes(client, lobby, demo_event):
    start_game(lobby, "p")
    r = client.get("/api/state?player=p")
    etag = r.headers["etag"]
    assert client.get("/api/state?player=p", headers={"if-none-match": etag}).status_code == 304
    client.post("/api/submit", json={"player": "p", "challenge": "coffee-break", "flag": flag_of(demo_event, "coffee-break")})
    assert client.get("/api/state?player=p", headers={"if-none-match": etag}).status_code == 200


# ------------------------------------------------------------------ submitting

def test_only_registered_names_score_and_spelling_is_canonical(client, lobby, demo_event):
    start_game(lobby, "Alice")
    flag = flag_of(demo_event, "coffee-break")
    bad = client.post("/api/submit", json={"player": "mallory", "challenge": "coffee-break", "flag": flag}).json()
    assert bad["status"] == "error" and "Join" in bad["message"]
    ok = client.post("/api/submit", json={"player": "aLICE", "challenge": "coffee-break", "flag": flag}).json()
    assert ok["status"] == "correct"
    assert list(demo_event.load().solves) == ["Alice"]


def test_late_joiner_can_play(client, lobby, demo_event):
    start_game(lobby)
    assert client.post("/api/lobby/register", json={"player": "late"}).json()["success"]
    r = client.post("/api/submit", json={"player": "late", "challenge": "coffee-break", "flag": flag_of(demo_event, "coffee-break")})
    assert r.json()["status"] == "correct"


def test_wrong_flag_rate_limit_is_per_player_and_challenge(client, lobby, demo_event):
    start_game(lobby, "bad", "good")
    body = {"player": "bad", "challenge": "coffee-break", "flag": "flag{wrong}"}
    for _ in range(MAX_WRONG_FLAGS):
        assert client.post("/api/submit", json=body).json()["status"] == "incorrect"
    blocked = client.post("/api/submit", json=body).json()
    assert blocked["status"] == "error" and "wait" in blocked["message"]
    other_player = client.post("/api/submit", json={**body, "player": "good", "flag": flag_of(demo_event, "coffee-break")})
    assert other_player.json()["status"] == "correct"
    other_challenge = client.post("/api/submit", json={**body, "challenge": "the-mole"})
    assert other_challenge.json()["status"] == "incorrect"


def test_oversized_inputs_are_rejected(client, lobby):
    start_game(lobby, "p")
    assert client.post("/api/submit", json={"player": "x" * 500, "challenge": "c", "flag": "f"}).status_code == 422
    assert client.post("/api/submit", json={"player": "p", "challenge": "c", "flag": "f" * 5000}).status_code == 422
    assert client.post("/game/api/chat", json={"level": 5, "message": "x" * 5000}).status_code == 422


# ------------------------------------------------------------------ downloads

def test_state_lists_only_player_files(client, lobby):
    start_game(lobby, "p")
    cards = {c["name"]: c for c in client.get("/api/state?player=p").json()["challenges"]}
    assert [f["name"] for f in cards["the-mole"]["files"]] == ["mole.exe"]      # no pdb, no .gitkeep
    assert {f["name"] for f in cards["interns-backup"]["files"]} == {"hashes.txt", "wordlist.txt"}
    assert cards["webgame"]["files"] == []


def test_download_file_and_zip(client, lobby):
    start_game(lobby, "p")
    r = client.get("/api/challenge/files/interns-backup/hashes.txt")
    assert r.status_code == 200 and b"password-hash" in r.content and "attachment" in r.headers["content-disposition"]
    z = client.get("/api/challenge/zip/interns-backup")
    assert z.status_code == 200
    assert sorted(zipfile.ZipFile(io.BytesIO(z.content)).namelist()) == ["hashes.txt", "wordlist.txt"]
    assert client.get("/api/challenge/zip/webgame").status_code == 404


@pytest.mark.parametrize("path", [
    "/api/challenge/files/the-mole/flag.txt",
    "/api/challenge/files/the-mole/..%2fflag.txt",
    "/api/challenge/files/the-mole/%2e%2e/flag.txt",
    "/api/challenge/files/the-mole/..%2f..%2fevent.json",
    "/api/challenge/files/the-mole/..%2f..%2f..%2flobby.json",
    "/api/challenge/files/the-mole/mole.pdb",
    "/api/challenge/files/the-mole/.gitkeep",
    "/api/challenge/files/nochallenge/x",
    "/api/challenge/files/..%2fthe-mole/mole.exe",
    "/api/challenge/zip/nochallenge",
])
def test_no_path_traversal_or_secret_leaks(client, lobby, demo_event, path):
    start_game(lobby, "p")
    r = client.get(path)
    assert r.status_code in (403, 404)
    for name in ALL_FLAGS:
        assert flag_of(demo_event, name).encode() not in r.content


def test_zip_cache_notices_changed_files(client, lobby, demo_event):
    start_game(lobby, "p")
    first = client.get("/api/challenge/zip/interns-backup").content
    (demo_event.challenge_dir("interns-backup") / "files" / "extra.txt").write_text("new")
    second = client.get("/api/challenge/zip/interns-backup").content
    assert "extra.txt" in zipfile.ZipFile(io.BytesIO(second)).namelist() and first != second
