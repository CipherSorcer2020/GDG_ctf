"""Challenge scaffolding: the ``challenge.md`` skeleton and starter files."""

from __future__ import annotations

from pathlib import Path

# Per-category story starter. Keep the story free of technique names - the
# whole point of the puzzle is working out *how* to attack it.
STORIES: dict[str, str] = {
    "crypto": "A message was intercepted, but it makes no sense. Can you read it?\n\n"
              "- `message.txt` - what we captured\n",
    "web": "A website is hiding something. Take a good look around.\n\n"
           "- `index.html` - the page\n",
    "pwn": "A program is running somewhere and it trusts you too much.\n\n"
           "- `program` - a copy of the program\n",
    "forensics": "A suspicious file was found. There is more to it than meets the eye.\n\n"
                 "- `evidence.dat` - the file\n",
    "rev": "Here is a program that guards a secret. What is the secret?\n\n"
           "- `program` - the program\n",
    "misc": "Describe the puzzle here.\n",
}

TEMPLATE = """\
<!-- Organizer: this file is what players see.
     - Keep the story free of technique names (no "Caesar", "MD5", "EXIF"...).
     - Hints go from gentle (1) to a walkthrough (3). NEVER put the flag in a hint.
     - The lesson is hidden until the player solves the challenge.
     - The flag itself lives in flag.txt - never ship that file. -->

{story}
## Hints

<details>
<summary>Hint 1</summary>

TODO: a gentle nudge in the right direction.
</details>

<details>
<summary>Hint 2</summary>

TODO: name the tool or idea they should look at.
</details>

<details>
<summary>Hint 3 (walkthrough)</summary>

TODO: step by step - but stop before the flag itself.
</details>

## What you just learned

TODO: one or two friendly sentences about the real-world idea behind this puzzle.
"""


def render_description(category: str) -> str:
    return TEMPLATE.format(story=STORIES.get(category, STORIES["misc"]))


def scaffold_challenge(challenge_dir: Path, title: str, category: str, flag: str) -> None:
    """Create the challenge directory with description, flag and files/ folder."""
    challenge_dir.mkdir(parents=True, exist_ok=True)
    (challenge_dir / "challenge.md").write_text(render_description(category), encoding="utf-8")
    (challenge_dir / "flag.txt").write_text(flag + "\n", encoding="utf-8")
    files_dir = challenge_dir / "files"
    files_dir.mkdir(exist_ok=True)
    (files_dir / ".gitkeep").write_text("", encoding="utf-8")
