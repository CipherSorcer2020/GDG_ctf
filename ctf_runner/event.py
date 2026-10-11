"""Event/challenge models and on-disk storage (``event.json``).

Layout of an event directory::

    my-ctf/
      event.json              # metadata, flag hashes, solves (never plaintext flags)
      lobby.json              # who joined + admin token (created by the server)
      challenges/
        <name>/
          challenge.md        # player-facing text: story, hints, lesson
          flag.txt            # organizer's copy of the flag (do not ship!)
          files/              # attachments handed out to players
"""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .flags import DEFAULT_PREFIX, generate_flag, hash_flag, verify_flag
from .jsonfile import JsonFile
from .markup import ChallengeDoc, parse_challenge
from .templates import scaffold_challenge

EVENT_FILE = "event.json"
CHALLENGES_DIR = "challenges"
BACKUPS_TO_KEEP = 10
EVENT_LOG_MAX = 200      # recent solves kept for the live feed / "first solver" badges

CATEGORIES = ("crypto", "web", "pwn", "forensics", "rev", "misc")

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

# The guided tutorial game is a challenge too; its points shrink when players
# open "spoiler" hints.  Tune the rules here.
GAME_CHALLENGE = "webgame"
SPOILER_PENALTY = 50     # points lost per level whose spoiler hint was opened
MIN_GAME_AWARD = 100     # the game never pays less than this (or its full value if lower)

# Submit result statuses
CORRECT = "correct"
INCORRECT = "incorrect"
ALREADY_SOLVED = "already_solved"
UNKNOWN_CHALLENGE = "unknown_challenge"


class EventError(Exception):
    """User-facing error (bad input, missing event, duplicate names...)."""


def slugify(name: str) -> str:
    """Normalize a challenge name into a lowercase slug."""
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def game_award(points: int, spoilers: int) -> int:
    """Points the tutorial game pays after ``spoilers`` spoiler hints."""
    if spoilers <= 0:
        return points
    return max(min(MIN_GAME_AWARD, points), points - spoilers * SPOILER_PENALTY)


@dataclass
class Challenge:
    name: str
    title: str
    category: str
    points: int
    flag_hash: str


@dataclass
class Event:
    name: str
    flag_prefix: str = DEFAULT_PREFIX
    challenges: dict[str, Challenge] = field(default_factory=dict)
    # player name -> ordered list of solved challenge names
    solves: dict[str, list[str]] = field(default_factory=dict)
    # player name -> tutorial levels whose spoiler hint was opened (each costs once)
    spoilers_used: dict[str, list[int]] = field(default_factory=dict)
    # chronological solve log: {"t", "player", "challenge", "points"}
    events: list[dict] = field(default_factory=list)
    # club branding shown in the UI: {"club": ..., "tagline": ...}
    branding: dict = field(default_factory=dict)

    def first_solver(self, name: str) -> str:
        """Who solved challenge ``name`` first ('' if nobody yet)."""
        return next((e["player"] for e in self.events if e.get("challenge") == name), "")

    def award(self, player: str, name: str) -> int:
        """Points ``player`` gets (or got) for challenge ``name``."""
        challenge = self.challenges.get(name)
        if challenge is None:
            return 0
        if name == GAME_CHALLENGE:
            return game_award(challenge.points, len(self.spoilers_used.get(player, [])))
        return challenge.points

    def score(self, player: str) -> int:
        """Total score; the tutorial game is reduced by spoiler penalties."""
        return sum(self.award(player, name) for name in self.solves.get(player, []))


@dataclass
class SubmitResult:
    status: str
    message: str
    points_awarded: int = 0
    new_total: int = 0


@dataclass
class ScoreRow:
    player: str
    score: int
    solves: int


class EventStore:
    """Loads/saves an event directory and implements game rules."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.event_path = self.root / EVENT_FILE
        self.challenges_path = self.root / CHALLENGES_DIR
        self._file = JsonFile(self.event_path)
        self._lock = threading.RLock()
        self._docs: dict[str, tuple[tuple[int, int], ChallengeDoc]] = {}

    # ------------------------------------------------------------------ setup

    @classmethod
    def discover(cls, start: Path | None = None) -> EventStore:
        """Find the nearest ancestor directory containing ``event.json``."""
        current = Path(start or Path.cwd()).resolve()
        for candidate in (current, *current.parents):
            if (candidate / EVENT_FILE).is_file():
                return cls(candidate)
        raise EventError(
            f"no CTF event found in '{current}' (missing {EVENT_FILE}). "
            "Run 'ctf init <dir>' first."
        )

    @classmethod
    def init(cls, root: Path, name: str | None = None, flag_prefix: str = DEFAULT_PREFIX) -> EventStore:
        store = cls(Path(root).resolve())
        if store.event_path.exists():
            raise EventError(f"'{store.event_path}' already exists - this is already an event")
        store.root.mkdir(parents=True, exist_ok=True)
        store.challenges_path.mkdir(exist_ok=True)
        store.save(Event(name=name or store.root.name, flag_prefix=flag_prefix))
        return store

    # ------------------------------------------------------------------ I/O

    def load(self) -> Event:
        try:
            raw = self._file.read()
        except FileNotFoundError:
            raise EventError(f"'{self.event_path}' not found - run 'ctf init' first") from None
        except json.JSONDecodeError as exc:
            raise EventError(f"'{self.event_path}' is not valid JSON: {exc}") from None

        challenges = {name: Challenge(**data) for name, data in raw.get("challenges", {}).items()}
        spoilers: dict[str, list[int]] = {}
        for player, used in raw.get("spoilers_used", {}).items():
            # older files stored a plain count; keep the count with placeholder levels
            spoilers[player] = list(range(-int(used), 0)) if isinstance(used, int) else [int(x) for x in used]
        return Event(
            name=raw.get("name", self.root.name),
            flag_prefix=raw.get("flag_prefix", DEFAULT_PREFIX),
            challenges=challenges,
            solves={p: list(solved) for p, solved in raw.get("solves", {}).items()},
            spoilers_used=spoilers,
            events=list(raw.get("events", [])),
            branding=dict(raw.get("branding", {})),
        )

    def save(self, event: Event) -> None:
        self._file.write(
            {
                "name": event.name,
                "flag_prefix": event.flag_prefix,
                "challenges": {
                    name: {
                        "name": c.name,
                        "title": c.title,
                        "category": c.category,
                        "points": c.points,
                        "flag_hash": c.flag_hash,
                    }
                    for name, c in event.challenges.items()
                },
                "solves": event.solves,
                "spoilers_used": event.spoilers_used,
                "events": event.events[-EVENT_LOG_MAX:],
                "branding": event.branding,
            }
        )

    def backup(self) -> Path | None:
        """Snapshot ``event.json`` as ``event.json.bak.<timestamp>`` (None if absent).

        Called by ``ctf serve`` before it wipes scores, so nothing is ever lost.
        Only the newest ``BACKUPS_TO_KEEP`` snapshots are kept.
        """
        if not self.event_path.exists():
            return None
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_path = self.root / f"{EVENT_FILE}.bak.{stamp}"
        backup_path.write_text(self.event_path.read_text(encoding="utf-8"), encoding="utf-8")
        old = sorted(self.root.glob(f"{EVENT_FILE}.bak.*"))[:-BACKUPS_TO_KEEP]
        for path in old:
            path.unlink(missing_ok=True)
        return backup_path

    def wipe_progress(self) -> int:
        """Erase all scores and spoiler usage. Challenges stay. Returns players wiped."""
        with self._lock:
            event = self.load()
            count = len(set(event.solves) | set(event.spoilers_used))
            event.solves = {}
            event.spoilers_used = {}
            event.events = []
            self.save(event)
            return count

    # ------------------------------------------------------------- challenges

    def challenge_dir(self, name: str) -> Path:
        return self.challenges_path / name

    def read_description(self, name: str) -> str:
        path = self.challenge_dir(name) / "challenge.md"
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def read_doc(self, name: str) -> ChallengeDoc:
        """Parsed + rendered ``challenge.md`` (cached until the file changes)."""
        path = self.challenge_dir(name) / "challenge.md"
        try:
            st = path.stat()
        except FileNotFoundError:
            return ChallengeDoc()
        stamp = (st.st_mtime_ns, st.st_size)
        cached = self._docs.get(name)
        if cached and cached[0] == stamp:
            return cached[1]
        doc = parse_challenge(path.read_text(encoding="utf-8"))
        self._docs[name] = (stamp, doc)
        return doc

    def list_files(self, name: str) -> list[dict]:
        """Player attachments of a challenge: ``files/`` minus dotfiles."""
        files_dir = self.challenge_dir(name) / "files"
        if not files_dir.is_dir():
            return []
        out = []
        for f in sorted(files_dir.rglob("*")):
            rel = f.relative_to(files_dir)
            if f.is_file() and not any(part.startswith(".") for part in rel.parts):
                out.append({"name": rel.as_posix(), "size": f.stat().st_size})
        return out

    def create_challenge(
        self,
        name: str,
        category: str = "misc",
        points: int = 100,
        title: str | None = None,
        flag: str | None = None,
    ) -> tuple[Challenge, str]:
        """Scaffold a new challenge. Returns ``(challenge, plaintext_flag)``."""
        with self._lock:
            event = self.load()

            slug = slugify(name)
            if not slug or not _NAME_RE.match(slug):
                raise EventError(f"invalid challenge name: '{name}'")
            if slug in event.challenges:
                raise EventError(f"challenge '{slug}' already exists")
            if category not in CATEGORIES:
                raise EventError(f"unknown category '{category}' (choose from: {', '.join(CATEGORIES)})")
            if points <= 0:
                raise EventError("points must be a positive number")

            plaintext = flag.strip() if flag else generate_flag(event.flag_prefix)
            if not plaintext:
                raise EventError("flag must not be empty")

            challenge = Challenge(
                name=slug,
                title=(title or name).strip(),
                category=category,
                points=points,
                flag_hash=hash_flag(plaintext),
            )
            event.challenges[slug] = challenge
            self.save(event)
        scaffold_challenge(
            self.challenge_dir(slug),
            title=challenge.title,
            category=challenge.category,
            flag=plaintext,
        )
        return challenge, plaintext

    # ------------------------------------------------------------------- play

    def submit(self, player: str, challenge_name: str, flag: str) -> SubmitResult:
        """Validate a flag submission and award points on first solve."""
        with self._lock:
            event = self.load()
            player = player.strip()
            if not player:
                raise EventError("player name must not be empty")

            slug = slugify(challenge_name)
            challenge = event.challenges.get(slug)
            if challenge is None:
                return SubmitResult(
                    status=UNKNOWN_CHALLENGE,
                    message=f"no challenge named '{challenge_name}'",
                )

            if not verify_flag(flag, challenge.flag_hash):
                return SubmitResult(status=INCORRECT, message="wrong flag, try again")

            solved = event.solves.get(player, [])
            if slug in solved:
                return SubmitResult(
                    status=ALREADY_SOLVED,
                    message=f"already solved '{challenge.title}' - no extra points",
                    new_total=event.score(player),
                )

            solved.append(slug)
            event.solves[player] = solved
            awarded = event.award(player, slug)
            event.events.append(
                {"t": round(time.time(), 3), "player": player, "challenge": slug, "points": awarded}
            )
            self.save(event)
            return SubmitResult(
                status=CORRECT,
                message=f"correct! +{awarded} points",
                points_awarded=awarded,
                new_total=event.score(player),
            )

    def record_spoiler(self, player: str, level: int) -> tuple[int, bool]:
        """Charge ``player`` for opening the spoiler hint of tutorial ``level``.

        Each level costs at most once, and nothing is charged once the player has
        already finished the tutorial game.  Returns ``(spoilers_used, newly_charged)``.
        """
        player = player.strip()
        if not player:
            raise EventError("player name must not be empty")
        with self._lock:
            event = self.load()
            used = event.spoilers_used.get(player, [])
            if GAME_CHALLENGE in event.solves.get(player, []) or level in used:
                return len(used), False
            used.append(level)
            event.spoilers_used[player] = used
            self.save(event)
            return len(used), True

    def scoreboard(self) -> list[ScoreRow]:
        """Players ranked by score (desc), then by name."""
        event = self.load()
        rows = [
            ScoreRow(player=p, score=event.score(p), solves=len(solved))
            for p, solved in event.solves.items()
        ]
        rows.sort(key=lambda r: (-r.score, r.player.lower()))
        return rows
