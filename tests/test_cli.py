import pytest

from ctf_runner import cli
from ctf_runner.cli import main
from ctf_runner.event import EventStore
from ctf_runner.lobby import LobbyStore


@pytest.fixture()
def evt(tmp_path, monkeypatch):
    assert main(["init", str(tmp_path / "e"), "--name", "T"]) == 0
    monkeypatch.chdir(tmp_path / "e")
    return EventStore(tmp_path / "e")


def test_new_list_show(evt, capsys):
    assert main(["new", "puzzle", "-c", "crypto", "-p", "50", "--flag", "flag{abc}"]) == 0
    assert main(["list"]) == 0
    assert main(["show", "puzzle"]) == 0
    out = capsys.readouterr().out
    assert "puzzle" in out and "crypto" in out


def test_show_unknown_challenge_is_a_clean_error(evt, capsys):
    assert main(["show", "nothere"]) == 2
    assert "no challenge named 'nothere'" in capsys.readouterr().err


def test_submit_exit_codes(evt):
    main(["new", "a", "--flag", "flag{x}"])
    assert main(["submit", "a", "flag{x}", "--player", "p"]) == 0
    assert main(["submit", "a", "flag{x}", "--player", "p"]) == 0       # already solved
    assert main(["submit", "a", "flag{no}", "--player", "q"]) == 1
    assert main(["scoreboard"]) == 0


def test_no_event_is_a_clean_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["list"]) == 2 and "no CTF event" in capsys.readouterr().err


def test_pack_skips_dotfiles_and_empty(evt, capsys):
    main(["new", "a"]); main(["new", "b"])
    (evt.challenge_dir("a") / "files" / "x.txt").write_text("hi")
    assert main(["pack"]) == 0
    assert (evt.root / "packages" / "a.zip").exists() and not (evt.root / "packages" / "b.zip").exists()


# ------------------------------------------------------------------ ctf serve

@pytest.fixture()
def played(evt, monkeypatch):
    _c, flag = evt.create_challenge("c1", points=50)
    evt.submit("alice", "c1", flag)
    evt.record_spoiler("alice", 3)
    lobby = LobbyStore(evt.root)
    lobby.join("alice"); lobby.start(lobby.load().admin_token)
    monkeypatch.setattr("ctf_runner.server.serve", lambda *a, **k: None)
    monkeypatch.setattr(cli, "_port_in_use", lambda *a: False)
    return evt, lobby


def test_serve_wipes_scores_and_lobby_but_keeps_challenges(played, capsys):
    evt, lobby = played
    old = lobby.load().admin_token
    assert main(["serve"]) == 0
    ev = evt.load()
    assert ev.solves == {} and ev.spoilers_used == {} and "c1" in ev.challenges
    lb = lobby.load()
    assert lb.state == "waiting" and lb.players == [] and lb.admin_token != old
    out = capsys.readouterr().out
    assert lb.admin_token in out                                         # printed in the console
    assert list(evt.root.glob("event.json.bak.*"))                       # old scores kept as a backup


def test_serve_backup_really_contains_the_old_scores(played):
    evt, _ = played
    main(["serve"])
    backup = sorted(evt.root.glob("event.json.bak.*"))[-1]
    assert '"alice"' in backup.read_text()


def test_serve_keep_preserves_progress(played):
    evt, lobby = played
    old = lobby.load().admin_token
    assert main(["serve", "--keep"]) == 0
    assert evt.load().solves == {"alice": ["c1"]}
    lb = lobby.load()
    assert lb.state == "active" and lb.players == ["alice"] and lb.admin_token != old


def test_serve_refuses_a_busy_port_with_help(evt, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_port_in_use", lambda *a: True)
    assert main(["serve", "--port", "8000"]) == 2
    err = capsys.readouterr().err
    assert "already in use" in err and "--port 8001" in err and "netstat" in err
