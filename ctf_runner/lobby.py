"""Pre-game lobby: players pick a name, the organizer starts the game.

State lives in ``lobby.json`` next to ``event.json``::

    {"state": "waiting",            # "waiting" -> players can join; "active" -> game on
     "players": ["alice", "bob"],
     "admin_token": "..."}          # printed in the server console ONLY

``ctf serve`` issues a brand-new token every launch and prints it in the
organizer's console.  The /admin page never contains it - the organizer types
it in - so nobody else can start, reset or wipe the game.
"""

from __future__ import annotations

import hmac
import json
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from secrets import token_hex

from .jsonfile import JsonFile

LOBBY_FILE = "lobby.json"

WAITING = "waiting"
ACTIVE = "active"
STARTING = "starting"   # phase only: the organizer pressed Start, the countdown is running
MAX_COUNTDOWN = 60

MAX_NAME = 32
MAX_PLAYERS = 300  # guards lobby.json against bots flooding the join form

_CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")


def clean_name(raw: str) -> str:
    """Trim, collapse inner whitespace, drop control characters, cap the length."""
    return re.sub(r"\s+", " ", _CTRL_RE.sub("", raw or "")).strip()[:MAX_NAME]


@dataclass
class Lobby:
    state: str = WAITING
    players: list[str] = field(default_factory=list)
    admin_token: str = ""
    starts_at: float = 0.0  # epoch seconds; the game unlocks for everyone at this instant

    def is_active(self) -> bool:
        """True once the game is really on (the start countdown, if any, has finished)."""
        return self.state == ACTIVE and time.time() >= self.starts_at

    def phase(self) -> str:
        """waiting -> starting (countdown running) -> active."""
        if self.state != ACTIVE:
            return WAITING
        return ACTIVE if time.time() >= self.starts_at else STARTING

    def seconds_to_start(self) -> float:
        return max(0.0, self.starts_at - time.time()) if self.state == ACTIVE else 0.0

    def canonical(self, player: str) -> str | None:
        """The registered spelling of ``player`` (case-insensitive), or None."""
        key = clean_name(player).casefold()
        if not key:
            return None
        return next((p for p in self.players if p.casefold() == key), None)


@dataclass
class JoinResult:
    ok: bool
    name: str = ""
    reason: str = ""  # "", "invalid", "taken", "full"


class LobbyStore:
    """File-backed lobby state scoped to an event directory."""

    def __init__(self, root: Path):
        self.path = Path(root) / LOBBY_FILE
        self._file = JsonFile(self.path)
        self._lock = threading.RLock()

    # --------------------------------------------------------------- load/save

    def load_or_create(self) -> Lobby:
        with self._lock:
            try:
                raw = self._file.read()
            except FileNotFoundError:
                lobby = Lobby(admin_token=token_hex(16))
                self.save(lobby)
                return lobby
            except (json.JSONDecodeError, OSError):
                raw = {}
            token = raw.get("admin_token")
            lobby = Lobby(
                state=raw.get("state", WAITING),
                players=list(raw.get("players", [])),
                admin_token=token or token_hex(16),
                starts_at=float(raw.get("starts_at", 0) or 0),
            )
            if not token:
                self.save(lobby)
            return lobby

    def load(self) -> Lobby:
        return self.load_or_create()

    def save(self, lobby: Lobby) -> None:
        self._file.write(
            {
                "state": lobby.state,
                "players": lobby.players,
                "admin_token": lobby.admin_token,
                "starts_at": lobby.starts_at,
            }
        )

    # --------------------------------------------------------------- players

    def join(self, player: str) -> JoinResult:
        """Add ``player`` to the lobby (works before and after the game starts)."""
        name = clean_name(player)
        with self._lock:
            lobby = self.load_or_create()
            if not name:
                return JoinResult(False, reason="invalid")
            if lobby.canonical(name):
                return JoinResult(False, name=lobby.canonical(name) or name, reason="taken")
            if len(lobby.players) >= MAX_PLAYERS:
                return JoinResult(False, reason="full")
            lobby.players.append(name)
            self.save(lobby)
            return JoinResult(True, name=name)

    def register(self, player: str) -> tuple[Lobby, bool]:
        """Add *player*. Returns ``(lobby, was_added)``."""
        result = self.join(player)
        return self.load_or_create(), result.ok

    # --------------------------------------------------------------- admin

    def token_ok(self, admin_token: str) -> bool:
        """Constant-time check of an admin token."""
        expected = self.load_or_create().admin_token
        return bool(admin_token) and hmac.compare_digest(admin_token.encode(), expected.encode())

    def start(self, admin_token: str, countdown: int = 0) -> Lobby:
        """Organizer action: start the game, optionally after a synchronized countdown."""
        with self._lock:
            lobby = self.load_or_create()
            if not self.token_ok(admin_token):
                raise PermissionError("invalid admin token")
            if lobby.state != ACTIVE:
                lobby.state = ACTIVE
                lobby.starts_at = time.time() + max(0, min(int(countdown), MAX_COUNTDOWN)) if countdown else 0.0
                self.save(lobby)
            return lobby

    def reset(self, admin_token: str) -> Lobby:
        """Organizer action: back to waiting with no players (token is kept)."""
        with self._lock:
            lobby = self.load_or_create()
            if not self.token_ok(admin_token):
                raise PermissionError("invalid admin token")
            lobby.state = WAITING
            lobby.players = []
            lobby.starts_at = 0.0
            self.save(lobby)
            return lobby

    def fresh_start(self) -> Lobby:
        """Console-side reset used by ``ctf serve``: waiting, no players, NEW token."""
        with self._lock:
            lobby = Lobby(state=WAITING, players=[], admin_token=token_hex(16))
            self.save(lobby)
            return lobby

    def rotate_token(self) -> Lobby:
        """Issue a new admin token but keep state and players (``ctf serve --keep``)."""
        with self._lock:
            lobby = self.load_or_create()
            lobby.admin_token = token_hex(16)
            self.save(lobby)
            return lobby
