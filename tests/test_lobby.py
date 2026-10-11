import pytest

from ctf_runner.lobby import MAX_PLAYERS, LobbyStore, clean_name


def test_clean_name():
    assert clean_name("  Al   ice\t\n") == "Al ice"
    assert clean_name("a\x00b\x07c") == "abc"
    assert len(clean_name("x" * 100)) == 32
    assert clean_name("   ") == ""


def test_join_rules(lobby):
    assert lobby.join("Alice").ok
    dup = lobby.join("aLiCe")
    assert not dup.ok and dup.reason == "taken" and dup.name == "Alice"
    assert lobby.join("   ").reason == "invalid"
    assert lobby.load().players == ["Alice"]


def test_lobby_full(lobby, monkeypatch):
    monkeypatch.setattr("ctf_runner.lobby.MAX_PLAYERS", 2)
    lobby.join("a"); lobby.join("b")
    assert lobby.join("c").reason == "full"


def test_canonical_is_case_insensitive(lobby):
    lobby.join("Bob")
    lb = lobby.load()
    assert lb.canonical("  bOB ") == "Bob" and lb.canonical("nobody") is None and lb.canonical("") is None


def test_start_and_reset_need_the_token(lobby):
    token = lobby.load().admin_token
    with pytest.raises(PermissionError):
        lobby.start("wrong")
    assert lobby.start(token).is_active()
    lobby.join("x")
    with pytest.raises(PermissionError):
        lobby.reset("wrong")
    lb = lobby.reset(token)
    assert lb.state == "waiting" and lb.players == [] and lb.admin_token == token   # token is kept


def test_start_with_wrong_token_even_when_already_active(lobby):
    token = lobby.load().admin_token
    lobby.start(token)
    with pytest.raises(PermissionError):
        lobby.start("nope")


def test_fresh_start_and_rotate(lobby):
    old = lobby.load().admin_token
    lobby.join("a"); lobby.start(old)
    kept = lobby.rotate_token()
    assert kept.admin_token != old and kept.players == ["a"] and kept.is_active()
    fresh = lobby.fresh_start()
    assert fresh.admin_token != kept.admin_token and fresh.players == [] and fresh.state == "waiting"


def test_token_ok_is_exact(lobby):
    token = lobby.load().admin_token
    assert lobby.token_ok(token) and not lobby.token_ok("") and not lobby.token_ok(token[:-1])


def test_corrupt_lobby_file_recovers(tmp_path):
    (tmp_path / "lobby.json").write_text("{not json")
    lb = LobbyStore(tmp_path).load_or_create()
    assert lb.state == "waiting" and lb.admin_token


def test_state_survives_a_new_store_instance(lobby):
    lobby.join("persist")
    assert LobbyStore(lobby.path.parent).load().players == ["persist"]
