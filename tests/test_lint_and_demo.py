"""`ctf lint` + proof that every demo challenge is solvable and leaks nothing."""
import hashlib
import re
import subprocess
import sys

import pytest

from ctf_runner.event import EventStore
from ctf_runner.lint import ERROR, WARN, lint_event
from ctf_runner.flags import hash_flag
from conftest import DEMO, flag_of

EXPECTED = {"coffee-break", "vacation-snaps", "intercepted", "the-mole", "interns-backup", "webgame"}


# ------------------------------------------------------------------ the shipped demo

def test_demo_is_clean():
    problems = [f for f in lint_event(EventStore(DEMO)) if f.level in (ERROR, WARN)]
    assert problems == []


def test_demo_set_and_points_ramp():
    ev = EventStore(DEMO).load()
    assert set(ev.challenges) == EXPECTED
    assert ev.solves == {} and ev.spoilers_used == {}
    assert all(c.flag_hash == hash_flag(flag_of(EventStore(DEMO), n)) for n, c in ev.challenges.items())


def test_titles_do_not_name_the_technique():
    titles = " ".join(c.title.lower() for c in EventStore(DEMO).load().challenges.values())
    for word in ("caesar", "exif", "hash", "md5", "strings", "xor"):
        assert word not in titles


def test_no_hint_story_or_lesson_contains_a_flag():
    store = EventStore(DEMO)
    for name in store.load().challenges:
        flag = flag_of(store, name)
        inner = re.search(r"\{(.*)\}", flag).group(1)
        text = store.read_description(name)
        assert flag not in text and inner not in text, name
        doc = store.read_doc(name)
        blob = doc.story_html + "".join(h.html for h in doc.hints) + doc.lesson_html
        assert inner not in blob, name


def test_every_challenge_has_story_three_hints_and_a_lesson():
    store = EventStore(DEMO)
    for name in EXPECTED - {"webgame"}:
        doc = store.read_doc(name)
        assert doc.story_html and len(doc.hints) == 3 and doc.lesson_html, name


def test_players_never_receive_build_leftovers():
    store = EventStore(DEMO)
    for name in EXPECTED:
        for f in store.list_files(name):
            assert not f["name"].endswith((".pdb", ".bak", ".pyc")), f
    blob = b"".join(p.read_bytes() for p in (DEMO / "challenges").rglob("files/*") if p.is_file())
    assert b"mehdi" not in blob.lower() and b"C:\\Users" not in blob and b"C:/Users" not in blob


# ------------------------------------------------------------------ solvability: follow the hints for real

def test_intercepted_hint3_script_prints_the_flag():
    store = EventStore(DEMO)
    hint3 = store.read_description("intercepted").split("```python")[1].split("```")[0]
    out = subprocess.run([sys.executable, "-c", hint3], cwd=DEMO / "challenges/intercepted/files",
                         capture_output=True, text=True, check=True).stdout
    assert flag_of(store, "intercepted") in out


def test_interns_backup_hint3_script_cracks_all_four_and_root_verifies():
    store = EventStore(DEMO)
    d = DEMO / "challenges/interns-backup/files"
    script = store.read_description("interns-backup").split("```python")[1].split("```")[0]
    out = subprocess.run([sys.executable, "-c", script], cwd=d, capture_output=True, text=True, check=True).stdout
    cracked = dict(re.findall(r"(\w+) -> (\w+)", out))
    assert list(cracked) == ["alice", "bob", "carol", "dave"]
    flag = "flag{" + "_".join(cracked[u] for u in ("alice", "bob", "carol", "dave")) + "}"
    assert flag == flag_of(store, "interns-backup")
    root = re.search(r"^root\s+(\w{32})$", (d / "hashes.txt").read_text(), re.M).group(1)
    assert hashlib.md5(flag.encode()).hexdigest() == root


def test_vacation_photo_shows_the_flag_in_standard_exif_fields():
    PIL = pytest.importorskip("PIL.Image")
    flag = flag_of(EventStore(DEMO), "vacation-snaps")
    img = PIL.open(DEMO / "challenges/vacation-snaps/files/vacation.jpg")
    exif = img.getexif()
    assert exif.get(0x9C9C).decode("utf-16le").rstrip("\x00") == flag          # XP Comment ("Comments" on Windows)
    assert flag.encode() in exif.get_ifd(0x8769)[0x9286]                       # User Comment


def test_coffee_break_flag_is_in_the_page_script():
    store = EventStore(DEMO)
    html = (DEMO / "challenges/coffee-break/files/index.html").read_text()
    assert re.search(r"FLAG\s*=\s*['\"]" + re.escape(flag_of(store, "coffee-break")), html)


def test_mole_flag_is_readable_with_strings_and_pdb_is_gone():
    store = EventStore(DEMO)
    data = (DEMO / "challenges/the-mole/files/mole.exe").read_bytes()
    assert flag_of(store, "the-mole").encode() in data
    assert not (DEMO / "challenges/the-mole/files/mole.pdb").exists()


# ------------------------------------------------------------------ the linter itself

@pytest.fixture()
def fresh(tmp_path):
    return EventStore.init(tmp_path / "e")


def findings(store, level):
    return [f.message for f in lint_event(store) if f.level == level]


def test_lint_catches_flag_in_hint_and_todo(fresh):
    _c, flag = fresh.create_challenge("a")
    msgs = findings(fresh, ERROR)
    assert any("TODO" in m for m in msgs)
    md = fresh.challenge_dir("a") / "challenge.md"
    md.write_text(md.read_text().replace("TODO: step by step - but stop before the flag itself.", f"The flag is {flag}"))
    assert any("flag" in m and "challenge.md" in m for m in findings(fresh, ERROR))


def test_lint_catches_wrong_flag_file_and_forbidden_files_and_paths(fresh):
    fresh.create_challenge("a", flag="flag{secret_value}")
    d = fresh.challenge_dir("a")
    (d / "flag.txt").write_text("flag{something_else}\n")
    (d / "files" / "game.pdb").write_bytes(b"x")
    (d / "files" / "prog.exe").write_bytes(b"junk C:\\Users\\someone\\Documents\\proj\\main.c junk")
    (d / "files" / "flag.txt").write_text("oops")
    msgs = " | ".join(findings(fresh, ERROR))
    assert "does not match" in msgs and "game.pdb" in msgs and "personal path" in msgs and "files/flag.txt" in msgs


def test_lint_warns_when_the_story_names_the_technique(fresh):
    fresh.create_challenge("a", title="Caesar Salad")
    md = fresh.challenge_dir("a") / "challenge.md"
    text = md.read_text().replace("Describe the puzzle here.", "This is a classic Caesar cipher puzzle.")
    md.write_text(text)
    assert any("caesar" in m.lower() for m in findings(fresh, WARN))


def test_ctf_lint_command_exit_code(monkeypatch, fresh):
    from ctf_runner.cli import main
    monkeypatch.chdir(fresh.root)
    fresh.create_challenge("a")                    # still has TODO placeholders -> error
    assert main(["lint"]) == 2
