# Vacation Snaps

The rival team's photographer posted a holiday photo on the public board. It looks like
a perfectly ordinary day at the beach... but this photographer is famously careless
about what they share.

- `vacation.jpg` - the photo

The flag is not in the picture you can see. It is hiding somewhere else in the file.

## Hints

<details>
<summary>Hint 1</summary>

Staring at the beach will not help. Every photo file also carries information *about*
the photo - when it was taken, with which program, sometimes even a note. You cannot
see any of that by looking at the picture.
</details>

<details>
<summary>Hint 2</summary>

You can read that hidden information with free tools. On Windows, right-click the file,
choose Properties and open the Details tab. Or search online for a "photo metadata
viewer" (also called an "EXIF viewer") and upload the photo. Look for fields that can
hold free text, like comments.
</details>

<details>
<summary>Hint 3 (walkthrough)</summary>

Open the file in any online metadata viewer, or run `exiftool vacation.jpg` if you have
it. Scroll through the list until you find a comment field - it may be called
"Comments", "XP Comment" or "User Comment". The text stored there is the flag.
</details>

## What you just learned

**Files remember more than you think.** Photos can carry GPS locations, camera and phone
models, editing programs and notes - and people forget to remove them. Before you publish
a picture, strip the metadata (phones have a "remove location" switch for this).
