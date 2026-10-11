# EXIFpose

The rival team accidentally leaked a zip of "vacation photos" on the
public board. Their photographer is famously lazy about one thing...

- `vacation.png` - a lovely sunset. Or is it?

The flag is not in the picture. It is in the **file**.

---

## What's the setup?

Every photo carries **metadata** - data about the data:

- JPEGs store EXIF: camera model, date, sometimes GPS coordinates
- PNGs store text chunks: `Comment`, `Software`, `Author`, ...

The picture you *see* is a tiny part of the file. The rest is notes
about the file - and people forget to clean those up.

---

## Hints

<details>
<summary>Hint 1 (click to reveal)</summary>

You are not here to admire the sunset. Inspect the **file itself**:
free online tools like "PNG metadata viewer", or the classic
`exiftool vacation.png`.
</details>

<details>
<summary>Hint 2 (click to reveal)</summary>

Look for a chunk whose keyword is `Comment`. Metadata tools list every
keyword and its value - one of those values looks suspiciously like a
flag.
</details>

<details>
<summary>Hint 3 (spoiler - click to reveal)</summary>

`exiftool vacation.png` prints:

`
Comment      : flag{p1x3ls_r3m3mb3r_4ll}
`

No exiftool? Any online PNG-metadata viewer shows the same thing.
</details>

---

## What you just learned

<details>
<summary>Lesson (click to reveal after solving)</summary>

**Files remember everything.** Metadata can leak GPS locations, device
names, software versions, authors - intelligence agencies and stalkers
build entire profiles from it. Before publishing anything, strip the
metadata (phones have a "remove location" toggle, tools like exiftool
do the rest). And if you ever handle classified material: a screenshot
is not the same as a fresh export.
</details>
