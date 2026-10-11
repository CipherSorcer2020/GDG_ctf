import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ctf_runner.event import EventStore
from ctf_runner.lobby import LobbyStore
from ctf_runner.server import create_app

DEMO = Path(__file__).resolve().parent.parent / "demo"


@pytest.fixture()
def demo_event(tmp_path):
    """A private copy of the demo event, wiped like `ctf serve` would."""
    root = tmp_path / "evt"
    shutil.copytree(DEMO, root)
    store = EventStore(root)
    store.wipe_progress()
    return store


@pytest.fixture()
def lobby(demo_event):
    lb = LobbyStore(demo_event.root)
    lb.fresh_start()
    return lb


@pytest.fixture()
def client(demo_event, lobby):
    return TestClient(create_app(demo_event))


def start_game(lobby, *players):
    for name in players:
        lobby.join(name)
    lobby.start(lobby.load().admin_token)


def flag_of(store, name):
    return (store.challenge_dir(name) / "flag.txt").read_text().strip()
