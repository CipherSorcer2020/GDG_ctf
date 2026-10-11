"""Command-line interface for ctf-runner."""

from __future__ import annotations

import argparse
import socket
import sys

from .event import (
    ALREADY_SOLVED,
    CATEGORIES,
    CORRECT,
    EventError,
    EventStore,
    slugify,
)

EXIT_OK = 0
EXIT_WRONG_FLAG = 1
EXIT_ERROR = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ctf",
        description="Local CTF challenge runner: create challenges, validate flags, track scores.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create a new event in a directory")
    p.add_argument("path", nargs="?", default=".", help="directory for the event (default: .)")
    p.add_argument("--name", help="event name (default: directory name)")
    p.add_argument("--prefix", default="flag", help="flag prefix: 'flag' produces flag{...}")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("new", help="create a challenge")
    p.add_argument("name", help="challenge name/slug, e.g. 'rsa-warmup'")
    p.add_argument("--title", help="display title (default: the name)")
    p.add_argument("--category", "-c", default="misc", choices=CATEGORIES)
    p.add_argument("--points", "-p", type=int, default=100, help="points (default: 100)")
    p.add_argument("--flag", help="use this flag instead of generating a random one")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("list", help="list challenges")
    p.add_argument("--category", "-c", choices=CATEGORIES, help="filter by category")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="show a challenge description")
    p.add_argument("name")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("submit", help="submit a flag", aliases=["check"])
    p.add_argument("challenge", help="challenge name")
    p.add_argument("flag", help="the flag you found")
    p.add_argument("--player", default="player", help="player name (default: player)")
    p.set_defaults(func=cmd_submit)

    p = sub.add_parser("scoreboard", help="show the scoreboard")
    p.set_defaults(func=cmd_scoreboard)

    p = sub.add_parser("lint", help="check challenges for leaked clues, leaked flags and broken files")
    p.add_argument("--strict", action="store_true", help="treat warnings as errors")
    p.set_defaults(func=cmd_lint)

    p = sub.add_parser("serve", help="run the web app (wipes scores + lobby first, see --keep)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument(
        "--keep",
        action="store_true",
        help="do NOT wipe: keep scores and joined players (crash recovery mid-event)",
    )
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("pack", help="zip challenge files for distribution to players")
    p.add_argument("name", nargs="?", default=None, help="challenge slug (default: all challenges)")
    p.add_argument("--output", "-o", default="packages", help="output directory (default: packages)")
    p.set_defaults(func=cmd_pack)

    return parser


# ------------------------------------------------------------------ commands


def cmd_init(args: argparse.Namespace) -> int:
    store = EventStore.init(args.path, name=args.name, flag_prefix=args.prefix)
    print(f"Created event '{store.load().name}' at {store.root}")
    print("Next: ctf new my-challenge --category crypto --points 100")
    return EXIT_OK


def cmd_new(args: argparse.Namespace) -> int:
    store = EventStore.discover()
    challenge, flag = store.create_challenge(
        args.name,
        category=args.category,
        points=args.points,
        title=args.title,
        flag=args.flag,
    )
    print(f"Created challenge '{challenge.name}' ({challenge.category}, {challenge.points} pts)")
    print(f"  dir:  {store.challenge_dir(challenge.name)}")
    print(f"  flag: {flag}   <- also saved to flag.txt (do not ship it to players!)")
    print(f"Edit {store.challenge_dir(challenge.name) / 'challenge.md'} to write the story and hints.")
    return EXIT_OK


def cmd_list(args: argparse.Namespace) -> int:
    store = EventStore.discover()
    event = store.load()
    rows = [c for c in event.challenges.values() if not args.category or c.category == args.category]

    if not rows:
        print("No challenges yet. Create one with: ctf new <name> --category crypto")
        return EXIT_OK

    print(f"Challenges in '{event.name}' ({len(rows)}):")
    name_w = max(len("NAME"), max(len(c.name) for c in rows))
    cat_w = max(len("CATEGORY"), max(len(c.category) for c in rows))
    print(f"{'NAME':<{name_w}}  {'CATEGORY':<{cat_w}}  {'PTS':>4}  {'SOLVES':>6}")
    for c in sorted(rows, key=lambda c: (c.points, c.name)):
        solves = sum(1 for solved in event.solves.values() if c.name in solved)
        print(f"{c.name:<{name_w}}  {c.category:<{cat_w}}  {c.points:>4}  {solves:>6}")
    return EXIT_OK


def cmd_show(args: argparse.Namespace) -> int:
    store = EventStore.discover()
    event = store.load()
    challenge = event.challenges.get(slugify(args.name))
    if challenge is None:
        raise EventError(f"no challenge named '{args.name}'")

    print(f"# {challenge.title}")
    print(f"category: {challenge.category}   points: {challenge.points}   name: {challenge.name}")
    print("-" * 40)
    print(store.read_description(challenge.name))
    return EXIT_OK


def cmd_submit(args: argparse.Namespace) -> int:
    store = EventStore.discover()
    result = store.submit(args.player, args.challenge, args.flag)

    if result.status == CORRECT:
        print(f"[+] {result.message} (total: {result.new_total})")
        return EXIT_OK
    if result.status == ALREADY_SOLVED:
        print(f"[=] {result.message} (total: {result.new_total})")
        return EXIT_OK
    print(f"[x] {result.message}")
    return EXIT_WRONG_FLAG


def cmd_scoreboard(args: argparse.Namespace) -> int:
    store = EventStore.discover()
    rows = store.scoreboard()

    print(f"Scoreboard - {store.load().name}")
    if not rows:
        print("No solves yet.")
        return EXIT_OK
    print(f"{'#':>2}  {'PLAYER':<20}  {'SCORE':>6}  {'SOLVES':>6}")
    for i, row in enumerate(rows, start=1):
        print(f"{i:>2}  {row.player:<20}  {row.score:>6}  {row.solves:>6}")
    return EXIT_OK


def cmd_lint(args: argparse.Namespace) -> int:
    from .lint import ERROR, INFO, WARN, lint_event

    store = EventStore.discover()
    findings = lint_event(store)
    icons = {ERROR: "[ERROR]", WARN: "[warn] ", INFO: "[info] "}
    for f in sorted(findings, key=lambda f: (f.challenge, f.level != ERROR, f.level != WARN)):
        print(f"{icons[f.level]} {f.challenge}: {f.message}")
    errors = sum(f.level == ERROR for f in findings)
    warns = sum(f.level == WARN for f in findings)
    total = len(store.load().challenges)
    print(f"\nChecked {total} challenge(s): {errors} error(s), {warns} warning(s).")
    if errors or (args.strict and warns):
        return EXIT_ERROR
    print("All good - nothing here gives the game away.")
    return EXIT_OK


def cmd_pack(args: argparse.Namespace) -> int:
    """Zip each challenge's ``files/`` directory for player distribution."""
    import zipfile

    store = EventStore.discover()
    event = store.load()

    target = args.name
    if target is not None:
        slug = slugify(target)
        if slug not in event.challenges:
            raise EventError(f"no challenge named '{target}'")
        names = [slug]
    else:
        names = list(event.challenges.keys())

    if not names:
        print("No challenges to pack.")
        return EXIT_OK

    out_dir = store.root / args.output
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Packing {len(names)} challenge(s) to {out_dir}")
    for name in names:
        files = store.list_files(name)
        zip_path = out_dir / f"{name}.zip"
        if not files:
            print(f"  {name}: no files - skipping")
            continue
        files_dir = store.challenge_dir(name) / "files"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                zf.write(files_dir / f["name"], f["name"])
        print(f"  {name}: {len(files)} file(s) -> {zip_path.name}")
    return EXIT_OK


def _port_in_use(host: str, port: int) -> bool:
    probe = "127.0.0.1" if host in ("0.0.0.0", "", "::") else host
    try:
        with socket.create_connection((probe, port), timeout=0.5):
            return True
    except OSError:
        return False


def cmd_serve(args: argparse.Namespace) -> int:
    from .lobby import LobbyStore

    store = EventStore.discover()

    if _port_in_use(args.host, args.port):
        print(f"error: port {args.port} is already in use - probably an old server is still running.", file=sys.stderr)
        print(f"  Close its window (or press Ctrl+C there), or use another port: ctf serve --port {args.port + 1}",
              file=sys.stderr)
        print(f"  Windows: find it with  netstat -ano | findstr :{args.port}  then  taskkill /PID <pid> /F",
              file=sys.stderr)
        return EXIT_ERROR

    from .server import serve  # imported lazily so the CLI works without fastapi

    # Safety net first: snapshot event.json (scores included) before wiping it.
    backup = store.backup()
    if backup is not None:
        print(f"Backed up previous progress to {backup.name}")

    lobby = LobbyStore(store.root)
    if args.keep:
        lb = lobby.rotate_token()
        print("--keep: scores and joined players were NOT wiped.")
    else:
        wiped = store.wipe_progress()
        lb = lobby.fresh_start()
        print(f"Fresh start: wiped the scores of {wiped} player(s) and reset the lobby.")

    print(f"\nServing '{store.load().name}' at http://{args.host}:{args.port}   (Ctrl+C to stop)\n")
    print("  ADMIN TOKEN  (private - it is shown here and nowhere else):")
    print(f"      {lb.admin_token}\n")
    print(f"  Organizer panel: http://localhost:{args.port}/admin")
    if lb.state == "waiting":
        print("  Players can join now but see nothing until you press 'Start game' there.")
    else:
        print("  The game is already ACTIVE (--keep).")
    print()
    serve(store, host=args.host, port=args.port)
    return EXIT_OK


# --------------------------------------------------------------------- entry


def main(argv: list[str] | None = None) -> int:
    # Windows consoles use legacy codepages (cp1252...): never crash on
    # characters a description happens to contain, just replace them.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, OSError, ValueError):
            pass

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except EventError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except KeyboardInterrupt:
        print("\nbye")
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
