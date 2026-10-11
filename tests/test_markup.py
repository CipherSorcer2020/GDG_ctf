from ctf_runner.markup import parse_challenge, render_markdown

SAMPLE = """
# Title

Story with `code` and **bold**.

- `file.txt` - a file

## Hints

<details>
<summary>Hint 1 (click)</summary>

First nudge.
</details>

<details>
<summary>Hint 2</summary>

```python
print("<b>")
```
</details>

## What you just learned

<details>
<summary>Lesson (click to reveal)</summary>

**Big idea.**
</details>
"""


def test_sections_are_split():
    doc = parse_challenge(SAMPLE)
    assert "Title" not in doc.story_html and "<code>code</code>" in doc.story_html
    assert [h.title for h in doc.hints] == ["Hint 1", "Hint 2"]
    assert "First nudge" in doc.hints[0].html and "<pre>" in doc.hints[1].html
    assert "Big idea" in doc.lesson_html and "summary" not in doc.lesson_html.lower()
    assert "Hints" not in doc.story_html and "nudge" not in doc.story_html


def test_story_does_not_contain_hint_or_lesson_text():
    doc = parse_challenge(SAMPLE)
    for secret in ("First nudge", "Big idea"):
        assert secret not in doc.story_html


def test_html_is_escaped():
    out = render_markdown("<script>alert(1)</script> and `<b>`\n\n```\n<img onerror=x>\n```")
    assert "<script>" not in out and "<img" not in out
    assert "&lt;script&gt;" in out and "&lt;img" in out


def test_plain_description_without_sections_is_all_story():
    doc = parse_challenge("Just a story.\n\nSecond paragraph.")
    assert doc.hints == [] and doc.lesson_html == "" and doc.story_html.count("<p>") == 2


def test_lists_and_wrapped_lines():
    out = render_markdown("- one\n- two\n  continued\n\n1. a\n2. b\n\nwrapped\nline")
    assert "<li>two continued</li>" in out and "<ol>" in out and "<p>wrapped line</p>" in out


def test_comments_are_removed():
    assert "secret" not in render_markdown("hi <!-- secret --> there")
