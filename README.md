# ctf-runner — a beginner-friendly CTF you host from your own PC

A small web app for running a friendly capture-the-flag event: players join a lobby,
you press **Start**, they work through challenges with 3 tiers of hints, and a live
scoreboard shows who is ahead. No database, no accounts, no build step.

```
setup.bat / setup.sh   one-time install            run.bat / run.sh   start an event
demo/                  the ready-made event        ctf_runner/        the program
```

## Hosting day (20–40 players from your own PC)

1. **Once:** run `setup.bat` (Windows) or `./setup.sh`. For internet play install the free
   tunnel: `winget install cloudflare.cloudflared`.
2. **Check your content:** open a terminal in `demo/` and run `ctf lint` (see below).
3. **Start:** run `run.bat` / `./run.sh`. It opens the server window and a Cloudflare tunnel.
   Send players the `https://….trycloudflare.com` link.
4. **Admin token:** it is printed in the **ctf-server** window and **nowhere else**. Open
   `http://localhost:8000/admin` on your PC, paste the token.
5. Players open the link, pick a name and wait in the lobby (they see no challenges, files or
   tutorial game yet). When everybody is in, press **Start game**.

What the launcher does for you every time:

| | |
|---|---|
| **Wipes the database** | `ctf serve` erases all scores + the lobby and issues a new admin token. The previous `event.json` is saved first as `event.json.bak.<time>` (last 10 kept). |
| **Crash recovery** | Server died mid-event? Start with `set KEEP_STATE=1` (or `ctf serve --keep`) to keep scores and players. |
| **Busy port** | Tells you plainly (and how to fix it) instead of crashing. |
| **Same-wifi play** | `set HOST=0.0.0.0` and share `http://<your-LAN-ip>:8000`. |

A normal PC handles 40 players easily (tested: 40 simultaneous clients, 0 errors, ~0.1 s responses).

## Make it yours: GDG branding, logo, projector screen

* **Look & feel** – Google's four colors, **Google Sans** (open-licensed, bundled in `ctf_runner/web/fonts/`
  so it works offline), light *and* dark mode (follows the phone, with a toggle), phone-friendly layout.
* **Your logo** – drop `logo.svg` (best) or `logo.png` into `demo/brand/` (your event folder, see the
  README there). It replaces the placeholder in the header, lobby, admin panel, projector screen and browser tab
  immediately - no code changes, no restart.
* **Club name / tagline** – `demo/event.json` -> `"branding": {"club": "GDG Universiapolis", ...}`.
  The event name itself is the `"name"` field.
* **Start countdown** – in the organizer panel pick 5 / 10 seconds: every screen shows the same 3-2-1-GO,
  and the challenges unlock for everybody at the same instant (the server enforces it).
* **Projector scoreboard** – open `http://localhost:8000/board` on the TV: big animated leaderboard,
  live feed of solves, per-challenge progress and the join address.
* **Little joys for players** – confetti and a "+150 pts" toast on every solve, first-blood trophy, live
  "Sara just solved Intercepted" toasts, progress bar, All / To do / Solved filter, medals, colored avatars,
  a beginner "how it works" card, chat bubbles with a typing indicator in the tutorial game, and a hidden
  easter egg (click the logo 5 times).

## How the game works

* **Lobby gate** – until you press Start, challenges, downloads, flag submission and the tutorial
  game all answer "not started". Names are unique (case-insensitive) and only joined players can score.
* **Hints** – every challenge has 3 hints (nudge → tool → walkthrough). The tutorial game hands out
  hints on demand; its **hint 3** is a *spoiler* that costs 50 points, **once per level**.
* **Lessons** – the "what you just learned" text is withheld until the player solves the challenge.
* **Downloads** – each card lists its files with download links (plus a `.zip` for several files).
  Only a challenge's `files/` folder is ever served.
* **Fair play** – wrong flags are rate-limited (10/min per player+challenge), admin-token guesses are
  throttled, `/api/event/reset` and friends need the token.
* **Smooth** – one lightweight poll every 2 s in the lobby / 6 s in-game (paused in hidden tabs,
  `304 Not Modified` when nothing changed); the page only redraws cards that changed, so open hints
  and half-typed flags are never lost.

## Writing challenges

```
ctf new my-puzzle --category crypto --points 150 --title "Sunday Radio"
```

creates `challenges/my-puzzle/` with `challenge.md`, `flag.txt` (yours — **never ship it**) and `files/`.
Edit `challenge.md`:

```markdown
# Sunday Radio
The story. What the player sees first. Do NOT name the technique here.
- `message.txt` - what they get

## Hints
<details><summary>Hint 1</summary> a gentle nudge </details>
<details><summary>Hint 2</summary> the tool or idea </details>
<details><summary>Hint 3 (walkthrough)</summary> step by step - but never the flag </details>

## What you just learned
One friendly paragraph. Hidden until they solve it.
```

Put the player's files in `files/`, then check everything:

```
ctf lint            # errors: flag in a hint, wrong flag.txt, TODO left, .pdb / personal paths in files,
                    #         flag.txt shipped.   warnings: story/title names the technique
ctf list | show <name> | scoreboard | submit <name> <flag> --player <you> | pack
```

**Ground rules for friendly, non-spoiling challenges**

* Titles and stories describe a *situation*, not a technique ("Intercepted", not "Caesar Cipher").
* Hint 1 nudges, hint 2 names the tool, hint 3 is a walkthrough that stops **before** the flag.
* Test your own hint 3 end-to-end (the repo's tests do this for the demo).
* Before shipping a compiled file: no `.pdb`/debug files — they contain the build folder and your username.

## The demo event (easiest → hardest)

| Challenge | Category | Pts | Idea (organizer's eyes only) |
|---|---|---:|---|
| Coffee Break | web | 100 | developer tools / page source |
| Vacation Snaps | forensics | 100 | photo metadata (XP/User Comment) |
| Intercepted | crypto | 150 | Caesar shift 7 |
| The Mole | rev | 150 | `strings` on an exe |
| The Intern's Backup | crypto | 200 | dictionary attack on MD5 |
| Acme Corp: Your First Hack | misc | 500 | 8-level guided tutorial game |

Tune the scoring in `ctf_runner/event.py` (`SPOILER_PENALTY`, `MIN_GAME_AWARD`).

## Project layout

```
ctf_runner/
  cli.py      commands            lint.py     `ctf lint`
  event.py    scoring + storage   lobby.py    lobby, admin token
  server.py   web API             game.py     tutorial game (levels, hints, bots)
  markup.py   challenge.md -> story / hints / lesson     jsonfile.py  atomic, cached JSON
  web/        index/admin/board/game .html, css/, js/, fonts/, img/   (plain files, no build step)
tests/        139 tests incl. "every demo hint really leads to its flag"
```

Run the tests: `pytest -q`.
