"""Local web app: lobby, flag submission and live scoreboard (FastAPI).

Hosting model: the organizer runs ``ctf serve`` on their own PC.  The admin
token is printed in that console only; /admin asks for it.  Until the
organizer presses "Start Game" players wait in the lobby: challenges, files,
submissions and the tutorial game are all locked.

The front end is plain HTML/CSS/JS in ``ctf_runner/web`` - no build step.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .event import EventError, EventStore, slugify
from .game import add_game_routes
from .lobby import MAX_NAME, LobbyStore, clean_name
from .ratelimit import RateLimiter, client_key

WEB_DIR = Path(__file__).parent / "web"

# Wrong-flag limit per (player, challenge) and failed admin-token limit.
MAX_WRONG_FLAGS = 10
WRONG_FLAG_WINDOW = 60


class SubmitPayload(BaseModel):
    player: str = Field(min_length=1, max_length=64)
    challenge: str = Field(min_length=1, max_length=64)
    flag: str = Field(min_length=1, max_length=300)


class JoinPayload(BaseModel):
    player: str = Field(min_length=1, max_length=64)


class AdminPayload(BaseModel):
    admin_token: str = Field(max_length=200)


class StartPayload(AdminPayload):
    countdown: int = Field(default=0, ge=0, le=60)   # seconds of synchronized "3, 2, 1" before unlock


LOGO_NAMES = ("logo.svg", "logo.png", "logo.webp", "logo.jpg", "logo.jpeg", "logo.gif")
FEED_SIZE = 8


def _load_pages() -> dict[str, str]:
    names = {"index": "index.html", "admin": "admin.html", "game": "game.html",
             "profile": "profile.html", "locked": "locked.html", "board": "board.html"}
    return {key: (WEB_DIR / fn).read_text(encoding="utf-8") for key, fn in names.items()}


def _json_response(request: Request, payload: dict) -> Response:
    """JSON with an ETag: unchanged state costs players a tiny 304, not a full body."""
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    etag = '"' + hashlib.sha1(body.encode("utf-8")).hexdigest()[:20] + '"'
    headers = {"ETag": etag, "Cache-Control": "no-cache"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(body, media_type="application/json", headers=headers)


def create_app(store: EventStore) -> FastAPI:
    app = FastAPI(title="ctf-runner", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(GZipMiddleware, minimum_size=700)
    lobby = LobbyStore(store.root)
    pages = _load_pages()
    flag_limiter = RateLimiter(MAX_WRONG_FLAGS, WRONG_FLAG_WINDOW)
    admin_limiter = RateLimiter(8, 60)
    zip_cache: dict[str, tuple[tuple, bytes]] = {}

    def started() -> bool:
        return lobby.load_or_create().is_active()

    @app.middleware("http")
    async def static_cache_headers(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"  # revalidate (cheap 304)
        return response

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    # ------------------------------------------------------------- pages

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return pages["index"]

    @app.get("/board", response_class=HTMLResponse)
    def board_page() -> str:
        """Fullscreen scoreboard for a projector / TV."""
        return pages["board"]

    @app.get("/brand/logo")
    def brand_logo():
        """The club logo: drop logo.svg/png into <event folder>/brand/ to replace the placeholder."""
        for name in LOGO_NAMES:
            custom = store.root / "brand" / name
            if custom.is_file():
                return FileResponse(custom, headers={"Cache-Control": "no-cache"})
        return FileResponse(WEB_DIR / "img" / "logo.svg", headers={"Cache-Control": "no-cache"})

    @app.get("/admin", response_class=HTMLResponse)
    def admin_page() -> str:
        # The token is NOT in this page: the organizer types it in.
        return pages["admin"]

    # ------------------------------------------------------------- state

    def _challenges(player: str | None) -> list[dict]:
        event = store.load()
        solved = set(event.solves.get(player, [])) if player else set()
        solves_count: dict[str, int] = {}
        for done in event.solves.values():
            for name in done:
                solves_count[name] = solves_count.get(name, 0) + 1
        first = {}
        for e in event.events:
            first.setdefault(e.get("challenge"), e.get("player", ""))
        items = []
        for c in event.challenges.values():
            doc = store.read_doc(c.name)
            is_solved = c.name in solved
            items.append({
                "name": c.name,
                "title": c.title,
                "category": c.category,
                "points": c.points,
                "story": doc.story_html,
                "hints": [{"title": h.title, "html": h.html} for h in doc.hints],
                "lesson": doc.lesson_html if is_solved else "",
                "files": store.list_files(c.name),
                "solves": solves_count.get(c.name, 0),
                "solved": is_solved,
                "first": first.get(c.name, ""),
            })
        items.sort(key=lambda c: (c["points"], c["name"]))  # easiest first
        return items

    def _feed(event) -> list[dict]:
        titles = {c.name: c.title for c in event.challenges.values()}
        cats = {c.name: c.category for c in event.challenges.values()}
        recent = event.events[-FEED_SIZE:][::-1]
        return [
            {"id": f"{e['t']}-{e['player']}-{e['challenge']}", "player": e["player"],
             "title": titles.get(e["challenge"], e["challenge"]), "category": cats.get(e["challenge"], "misc"),
             "points": e.get("points", 0)}
            for e in recent
        ]

    @app.get("/api/state")
    def api_state(request: Request, player: str = ""):
        """The one endpoint players poll: lobby while waiting, game once active."""
        lb = lobby.load_or_create()
        name = lb.canonical(player)
        try:
            event = store.load()
        except EventError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from None
        brand = event.branding or {}
        phase = lb.phase()
        payload: dict = {
            "phase": phase,
            "event": {"name": event.name},
            "brand": {"club": brand.get("club", ""), "tagline": brand.get("tagline", "")},
            "me": {"name": name or "", "registered": name is not None},
        }
        if phase == "starting":
            payload["starts_in_ms"] = int(lb.seconds_to_start() * 1000)
        if phase == "active":
            payload["challenges"] = _challenges(name)
            payload["scoreboard"] = [
                {"player": r.player, "score": r.score, "solves": r.solves}
                for r in store.scoreboard()
            ]
            payload["feed"] = _feed(event)
        else:
            payload["players"] = lb.players
        return _json_response(request, payload)

    # ------------------------------------------------------------- play

    @app.post("/api/submit")
    def api_submit(payload: SubmitPayload) -> dict:
        lb = lobby.load_or_create()
        if not lb.is_active():
            return {"status": "error", "message": "The game hasn't started yet."}
        name = lb.canonical(payload.player)
        if name is None:
            return {"status": "error", "message": "Join the game first - reload the page and pick a name."}
        key = (name.casefold(), payload.challenge.strip().casefold())
        wait = flag_limiter.retry_after(key)
        if wait:
            return {"status": "error", "message": f"Too many wrong tries - wait {wait}s and think it over."}
        try:
            result = store.submit(name, payload.challenge, payload.flag)
        except EventError as exc:
            return {"status": "error", "message": str(exc)}
        if result.status == "incorrect":
            flag_limiter.hit(key)
        first_blood = False
        if result.status == "correct":
            first_blood = store.load().first_solver(slugify(payload.challenge)) == name
        return {
            "status": result.status,
            "message": result.message,
            "points_awarded": result.points_awarded,
            "new_total": result.new_total,
            "first_blood": first_blood,
        }

    # ------------------------------------------------------------- downloads
    # Only a challenge's files/ folder is ever served - never flag.txt,
    # challenge.md or anything outside it.

    def _require_started() -> None:
        if not started():
            raise HTTPException(status_code=403, detail="The game hasn't started yet.")

    def _files_dir(challenge: str) -> Path:
        if challenge not in store.load().challenges:
            raise HTTPException(status_code=404, detail="not found")
        return (store.challenge_dir(challenge) / "files").resolve()

    @app.get("/api/challenge/files/{challenge}/{filename:path}")
    def download_file(challenge: str, filename: str):
        _require_started()
        files_dir = _files_dir(challenge)
        target = (files_dir / filename).resolve()
        try:
            rel = target.relative_to(files_dir)
        except ValueError:
            raise HTTPException(status_code=404, detail="not found") from None
        if any(part.startswith(".") for part in rel.parts) or not target.is_file():
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(target, filename=target.name, media_type="application/octet-stream")

    @app.get("/api/challenge/zip/{challenge}")
    def download_zip(challenge: str):
        _require_started()
        files_dir = _files_dir(challenge)
        files = store.list_files(challenge)
        if not files:
            raise HTTPException(status_code=404, detail="no files for this challenge")
        stamp = tuple((f["name"], f["size"], (files_dir / f["name"]).stat().st_mtime_ns) for f in files)
        cached = zip_cache.get(challenge)
        if cached is None or cached[0] != stamp:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in files:
                    zf.write(files_dir / f["name"], f["name"])
            zip_cache[challenge] = cached = (stamp, buf.getvalue())
        return Response(
            cached[1],
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{challenge}.zip"'},
        )

    # ------------------------------------------------------------- lobby

    @app.get("/api/lobby/state")
    def api_lobby_state(request: Request):
        lb = lobby.load_or_create()
        return _json_response(request, {"state": lb.state, "phase": lb.phase(), "players": lb.players})

    @app.post("/api/lobby/register")
    def api_lobby_register(payload: JoinPayload) -> dict:
        result = lobby.join(payload.player)
        lb = lobby.load_or_create()
        if result.ok:
            return {"success": True, "message": "joined", "player": result.name, "players": lb.players}
        messages = {
            "invalid": "Please type a name.",
            "taken": "That name is already taken - pick another one.",
            "full": "The lobby is full.",
        }
        return {"success": False, "message": messages.get(result.reason, "Could not join."),
                "reason": result.reason, "players": lb.players}

    # ------------------------------------------------------------- admin
    # Every organizer action needs the console-only token; failed tries are throttled.

    def _admin(payload: AdminPayload, request: Request) -> str | None:
        """Return an error message, or None when the token is right."""
        key = client_key(request)
        wait = admin_limiter.retry_after(key)
        if wait:
            return f"Too many wrong tokens - wait {wait}s."
        if lobby.token_ok(payload.admin_token):
            return None
        admin_limiter.hit(key)
        return "invalid admin token"

    @app.post("/api/lobby/start")
    def api_lobby_start(payload: StartPayload, request: Request) -> dict:
        if (err := _admin(payload, request)):
            return {"success": False, "message": err}
        lb = lobby.start(payload.admin_token, countdown=payload.countdown)
        return {"success": True, "state": lb.state, "phase": lb.phase()}

    @app.post("/api/lobby/reset")
    def api_lobby_reset(payload: AdminPayload, request: Request) -> dict:
        if (err := _admin(payload, request)):
            return {"success": False, "message": err}
        lb = lobby.reset(payload.admin_token)
        return {"success": True, "state": lb.state, "players": lb.players}

    @app.post("/api/event/reset")
    def api_event_reset(payload: AdminPayload, request: Request) -> dict:
        """Clear every score (challenges stay). Needs the admin token."""
        if (err := _admin(payload, request)):
            return {"success": False, "message": err}
        store.wipe_progress()
        flag_limiter.reset()
        return {"success": True, "message": "Scores cleared. Challenges and points are untouched."}

    add_game_routes(app, store, lobby, pages, is_active=started)
    return app


def serve(store: EventStore, host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run(create_app(store), host=host, port=port, log_level="warning")


__all__ = ["create_app", "serve", "clean_name", "MAX_NAME"]
