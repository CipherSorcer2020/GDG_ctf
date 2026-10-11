"""Turn ``challenge.md`` into safe HTML, split into story / hints / lesson.

Why this lives on the server: players should only receive what they are
allowed to see *right now*.  The lesson ("what you just learned") names the
technique, so it is withheld until the player has solved the challenge.

Expected ``challenge.md`` layout (every part after the story is optional)::

    # Title
    The story - what the player sees first. No technique names here!

    - `attachment.txt` - what it is

    ## Hints
    <details><summary>Hint 1</summary>a gentle nudge</details>
    <details><summary>Hint 2</summary>more specific</details>
    <details><summary>Hint 3</summary>a walkthrough - but never the flag itself</details>

    ## What you just learned
    The lesson. Shown only after the challenge is solved.

All text is HTML-escaped; only the small markdown subset below is supported:
paragraphs, ``#`` headings, fenced code, ``inline code``, **bold**, *italic*,
``-`` / ``1.`` lists, ``>`` quotes and ``---`` rules.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_DETAILS_RE = re.compile(
    r"<details[^>]*>\s*<summary[^>]*>(.*?)</summary>(.*?)</details>", re.S | re.I
)
_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")
_ULI_RE = re.compile(r"^\s*[-*]\s+(.*)$")
_OLI_RE = re.compile(r"^\s*\d+[.)]\s+(.*)$")


# --------------------------------------------------------------- rendering


def _inline(text: str) -> str:
    """Escape, then apply `code`, **bold**, *italic* (code is protected first)."""
    parts = text.split("`")
    if len(parts) % 2 == 0:  # unmatched backtick: treat the last one as plain text
        parts = parts[:-2] + [parts[-2] + "`" + parts[-1]]
    out: list[str] = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            out.append(f"<code>{html.escape(part)}</code>")
        else:
            seg = html.escape(part)
            seg = _BOLD_RE.sub(r"<strong>\1</strong>", seg)
            seg = _ITALIC_RE.sub(r"<em>\1</em>", seg)
            out.append(seg)
    return "".join(out)


def render_markdown(text: str) -> str:
    """Render the supported markdown subset to safe HTML."""
    lines = _COMMENT_RE.sub("", text).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    para: list[str] = []
    i = 0

    def flush() -> None:
        if para:
            out.append("<p>" + _inline(" ".join(s.strip() for s in para)) + "</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):  # fenced code block
            flush()
            i += 1
            code: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1  # closing fence (or EOF)
            out.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
            continue

        if not stripped:
            flush()
            i += 1
            continue

        if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", stripped):
            flush()
            out.append("<hr>")
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush()
            level = min(max(len(m.group(1)) + 1, 3), 5)  # h3..h5 inside a card
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            i += 1
            continue

        if stripped.startswith(">"):
            flush()
            quote: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append("<blockquote>" + _inline(" ".join(quote)) + "</blockquote>")
            continue

        ul, ol = _ULI_RE.match(line), _OLI_RE.match(line)
        if ul or ol:
            flush()
            rx, tag = (_ULI_RE, "ul") if ul else (_OLI_RE, "ol")
            items: list[str] = []
            while i < len(lines):
                mm = rx.match(lines[i])
                if mm:
                    items.append(mm.group(1))
                    i += 1
                elif lines[i].startswith("  ") and lines[i].strip() and items:
                    items[-1] += " " + lines[i].strip()  # wrapped continuation line
                    i += 1
                else:
                    break
            out.append(f"<{tag}>" + "".join(f"<li>{_inline(x)}</li>" for x in items) + f"</{tag}>")
            continue

        para.append(line)
        i += 1

    flush()
    return "\n".join(out)


# --------------------------------------------------------------- splitting


@dataclass
class Hint:
    title: str
    html: str


@dataclass
class ChallengeDoc:
    story_html: str = ""
    hints: list[Hint] = field(default_factory=list)
    lesson_html: str = ""


def _label(heading: str) -> str:
    h = heading.strip().lower()
    if h.startswith("hint"):
        return "hints"
    if h.startswith("what you") or h.startswith("lesson") or h.startswith("what we"):
        return "lesson"
    return ""


def _strip_rules(md: str) -> str:
    """Drop leading/trailing ``---`` separators left over from the source."""
    return re.sub(r"^\s*(?:-{3,}\s*\n)+|(?:\n\s*-{3,}\s*)+\s*$", "", md.strip()).strip()


def parse_challenge(text: str) -> ChallengeDoc:
    """Split ``challenge.md`` into story / hints / lesson and render each part."""
    text = _COMMENT_RE.sub("", text).replace("\r\n", "\n").replace("\r", "\n")

    # Drop the leading "# Title" line: the card already shows the title.
    text = re.sub(r"\A\s*#\s+[^\n]*\n", "", text, count=1)

    marks = [(m.start(), m.end(), _label(m.group(1))) for m in _HEADING_RE.finditer(text)]
    marks = [m for m in marks if m[2]]
    story_end = marks[0][0] if marks else len(text)
    story_md = text[:story_end]

    hints_md = lesson_md = ""
    for idx, (_start, end, label) in enumerate(marks):
        stop = marks[idx + 1][0] if idx + 1 < len(marks) else len(text)
        body = text[end:stop]
        if label == "hints":
            hints_md += body
        else:
            lesson_md += body

    hints: list[Hint] = []
    for n, m in enumerate(_DETAILS_RE.finditer(hints_md), start=1):
        title = re.sub(r"\(.*?\)", "", m.group(1)).strip() or f"Hint {n}"
        hints.append(Hint(title=html.unescape(re.sub(r"<[^>]+>", "", title)), html=render_markdown(_strip_rules(m.group(2)))))
    if not hints and hints_md.strip():
        hints.append(Hint(title="Hint", html=render_markdown(_strip_rules(hints_md))))

    # A lesson wrapped in <details><summary>..</summary>..</details> -> keep the inside only.
    dm = _DETAILS_RE.search(lesson_md)
    if dm:
        lesson_md = dm.group(2)

    return ChallengeDoc(
        story_html=render_markdown(_strip_rules(story_md)),
        hints=hints,
        lesson_html=render_markdown(_strip_rules(lesson_md)),
    )
