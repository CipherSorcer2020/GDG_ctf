import json

import pytest

from ctf_runner.event import (
    GAME_CHALLENGE, MIN_GAME_AWARD, SPOILER_PENALTY, CORRECT, ALREADY_SOLVED, INCORRECT,
    EventError, EventStore, game_award,
)


@pytest.fixture()
def store(tmp_path):
    return EventStore.init(tmp_path / "evt", name="Test CTF")


def test_init_layout_and_no_double_init(store):
    assert store.event_path.is_file() and store.challenges_path.is_dir()
    with pytest.raises(EventError):
        EventStore.init(store.root)


def test_discover_walks_up(store):
    sub = store.root / "challenges"
    assert EventStore.discover(sub).root == store.root


def test_discover_without_event(tmp_path):
    with pytest.raises(EventError):
        EventStore.discover(tmp_path)


def test_create_challenge_scaffolds_files_and_hides_flag(store):
    ch, flag = store.create_challenge("Rsa Warmup", category="crypto", points=50)
    d = store.challenge_dir(ch.name)
    assert (d / "challenge.md").is_file() and (d / "files").is_dir()
    assert (d / "flag.txt").read_text().strip() == flag
    assert flag not in store.event_path.read_text()          # only the hash is stored


def test_scaffold_description_has_hints_section(store):
    store.create_challenge("x", category="crypto")
    doc = store.read_doc("x")
    assert len(doc.hints) == 3 and doc.lesson_html and doc.story_html


@pytest.mark.parametrize("kwargs", [{"name": "x", "category": "nope"}, {"name": "!!!"}, {"name": "x", "points": 0}])
def test_bad_challenge_input(store, kwargs):
    with pytest.raises(EventError):
        store.create_challenge(**kwargs)


def test_duplicate_challenge_fails(store):
    store.create_challenge("a")
    with pytest.raises(EventError):
        store.create_challenge("a")


def test_submit_flow(store):
    _c, flag = store.create_challenge("a", points=70)
    assert store.submit("p", "a", "flag{wrong}").status == INCORRECT
    ok = store.submit("p", "a", flag)
    assert ok.status == CORRECT and ok.points_awarded == 70 and ok.new_total == 70
    again = store.submit("p", "a", flag)
    assert again.status == ALREADY_SOLVED and again.new_total == 70
    assert store.submit("p", "nope", flag).status == "unknown_challenge"
    with pytest.raises(EventError):
        store.submit("  ", "a", flag)


def test_scoreboard_ranking_and_persistence(store):
    _a, fa = store.create_challenge("a", points=10)
    _b, fb = store.create_challenge("b", points=30)
    store.submit("zed", "a", fa)
    store.submit("amy", "b", fb)
    store.submit("amy", "a", fa)
    rows = EventStore(store.root).scoreboard()      # new instance = reload from disk
    assert [(r.player, r.score) for r in rows] == [("amy", 40), ("zed", 10)]


def test_backup_and_pruning(store):
    first = store.backup()
    assert first and first.read_text() == store.event_path.read_text()
    for _ in range(15):
        store.backup()
    assert len(list(store.root.glob("event.json.bak.*"))) == 10


def test_backup_without_event(tmp_path):
    assert EventStore(tmp_path / "none").backup() is None


def test_event_file_is_written_atomically(store):
    store.create_challenge("a")
    assert not list(store.root.glob("*.tmp"))
    json.loads(store.event_path.read_text())


def test_external_edit_is_picked_up(store):
    """The cache must notice when someone edits event.json by hand."""
    store.create_challenge("a")
    raw = json.loads(store.event_path.read_text())
    raw["name"] = "Renamed by hand"
    store.event_path.write_text(json.dumps(raw))
    assert store.load().name == "Renamed by hand"


def test_wipe_progress_keeps_challenges(store):
    _c, flag = store.create_challenge("a")
    store.submit("p", "a", flag)
    store.record_spoiler("p", 1)
    assert store.wipe_progress() == 1
    ev = store.load()
    assert ev.solves == {} and ev.spoilers_used == {} and "a" in ev.challenges


# ---- tutorial game scoring: the old code charged retroactively and floored the TOTAL

@pytest.fixture()
def game_store(store):
    store.create_challenge("other", points=1000)
    _c, flag = store.create_challenge(GAME_CHALLENGE, points=500)
    return store, flag


def test_game_award_formula():
    assert game_award(500, 0) == 500
    assert game_award(500, 2) == 500 - 2 * SPOILER_PENALTY
    assert game_award(500, 99) == MIN_GAME_AWARD
    assert game_award(60, 99) == 60          # never pays more than its face value


def test_spoiler_costs_once_per_level(game_store):
    store, _ = game_store
    assert store.record_spoiler("p", 3) == (1, True)
    assert store.record_spoiler("p", 3) == (1, False)        # same level again: free
    assert store.record_spoiler("p", 4) == (2, True)


def test_spoiler_penalty_only_hits_the_game_not_the_total(game_store):
    store, flag = game_store
    for lvl in range(1, 8):
        store.record_spoiler("p", lvl)                      # 7 spoilers
    other_flag = (store.challenge_dir("other") / "flag.txt").read_text().strip()
    store.submit("p", "other", other_flag)
    res = store.submit("p", GAME_CHALLENGE, flag)
    assert res.points_awarded == game_award(500, 7)
    assert store.load().score("p") == 1000 + game_award(500, 7)   # 'other' keeps all 1000


def test_no_retroactive_charge_after_finishing_the_game(game_store):
    store, flag = game_store
    store.submit("p", GAME_CHALLENGE, flag)
    assert store.record_spoiler("p", 1) == (0, False)
    assert store.load().score("p") == 500


def test_old_count_format_still_loads(game_store):
    store, _ = game_store
    raw = json.loads(store.event_path.read_text())
    raw["spoilers_used"] = {"p": 2}
    store.event_path.write_text(json.dumps(raw))
    assert len(store.load().spoilers_used["p"]) == 2
