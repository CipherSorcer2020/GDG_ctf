"""``ctf lint``: catch mistakes that leak clues (or break a challenge) before players see them."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .event import GAME_CHALLENGE, EventStore
from .flags import hash_flag
from .markup import parse_challenge

ERROR, WARN, INFO = "error", "warning", "info"

# Files that must never be handed to players.
FORBIDDEN_NAMES = {"flag.txt", "challenge.md", ".env", "event.json", "lobby.json"}
FORBIDDEN_SUFFIXES = {".pdb", ".bak", ".pyc", ".orig", ".swp"}
# Personal paths that build tools love to embed (and that reveal who made the file).
PERSONAL_PATH_RE = re.compile(rb"(?:[A-Za-z]:[\\/]+Users[\\/]+|/home/[a-z_][\w-]*/|/Users/[A-Za-z][\w-]*/)[^\x00\s\"']{0,40}")
# Words that name the technique; a story containing them gives the puzzle away.
TECHNIQUE_WORDS = ("caesar", "rot13", "md5", "sha1", "sha256", "exif", "steganography", "stego",
                   "base64", "xor", "cipher", "strings", "metadata", "view source", "robots.txt")
MAX_SCAN_BYTES = 8 * 1024 * 1024


@dataclass
class Finding:
    level: str
    challenge: str
    message: str


def _flag_needles(flag: str) -> list[str]:
    inner = re.search(r"\{(.*)\}", flag)
    needles = [flag]
    if inner and len(inner.group(1)) >= 6:
        needles.append(inner.group(1))
    return needles


def lint_event(store: EventStore) -> list[Finding]:
    out: list[Finding] = []
    event = store.load()

    for name, c in event.challenges.items():
        def add(level: str, msg: str, _n: str = name) -> None:
            out.append(Finding(level, _n, msg))

        cdir = store.challenge_dir(name)
        if not cdir.is_dir():
            add(ERROR, "challenge folder is missing")
            continue

        flag_path = cdir / "flag.txt"
        flag = flag_path.read_text(encoding="utf-8").strip() if flag_path.is_file() else ""
        if not flag:
            add(ERROR, "flag.txt is missing or empty")
        elif hash_flag(flag) != c.flag_hash:
            add(ERROR, "flag.txt does not match the flag hash in event.json (players could never solve it)")

        md_path = cdir / "challenge.md"
        if not md_path.is_file():
            add(ERROR, "challenge.md is missing")
            text = ""
        else:
            text = md_path.read_text(encoding="utf-8")

        if text:
            if flag and any(n in text for n in _flag_needles(flag)):
                add(ERROR, "the flag (or its inside) is written in challenge.md - hints must never contain it")
            doc = parse_challenge(text)
            if name == GAME_CHALLENGE:
                pass  # the tutorial game ships its own hints
            elif not doc.hints:
                add(WARN, "no hints - beginners will get stuck")
            elif len(doc.hints) != 3:
                add(INFO, f"{len(doc.hints)} hint(s) (3 is the usual: nudge, tool, walkthrough)")
            if "TODO" in text:
                add(ERROR, "challenge.md still contains TODO placeholders")
            story_plain = re.sub(r"<[^>]+>", " ", doc.story_html).lower() + " " + c.title.lower()
            for word in TECHNIQUE_WORDS:
                if re.search(rf"\b{re.escape(word)}", story_plain):
                    add(WARN, f"the story/title mentions '{word}' - that names the technique; move it to a hint")

        files_dir = cdir / "files"
        for f in sorted(files_dir.rglob("*")) if files_dir.is_dir() else []:
            if not f.is_file() or f.name == ".gitkeep":
                continue
            rel = f.relative_to(files_dir).as_posix()
            if f.name.lower() in FORBIDDEN_NAMES or f.suffix.lower() in FORBIDDEN_SUFFIXES:
                add(ERROR, f"files/{rel} must not be given to players")
            data = f.read_bytes()[:MAX_SCAN_BYTES]
            leak = PERSONAL_PATH_RE.search(data)
            if leak:
                shown = leak.group(0).decode("utf-8", "replace")[:40]
                add(ERROR, f"files/{rel} contains a personal path ('{shown}...') that reveals who built it")
            if flag and any(n.encode() in data for n in _flag_needles(flag)):
                add(INFO, f"files/{rel} contains the flag in plain text (fine if that is the puzzle)")

    return out
