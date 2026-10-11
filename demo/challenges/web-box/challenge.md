# Web Box

A local coffee shop website is running at `http://localhost:8000/game/files/rsawarmup/index.html` — wait, no, this is a static challenge.

Download the attachment and look for something that shouldn't be there.

---

## What's the setup?

A simple static HTML page for a fictional coffee shop. Something feels off...
or does it? The flag is hidden somewhere a curious user might notice.

---

## Hints

<details>
<summary>Hint 1 (click to reveal)</summary>

Right-click on the page and select "Inspect" or press `Ctrl+Shift+C`.

</details>

<details>
<summary>Hint 2 (click to reveal)</summary>

Look inside the Console tab.

</details>

<details>
<summary>Hint 3 (spoiler - click to reveal)</summary>

The flag appears in the Console when you type "FLAG". Cause the Flag was stored as a JavaScript variable Developers sometimes forget to remove these before shipping.

</details>

---

## What you just learned

<details>
<summary>Lesson (click to reveal after solving)</summary>

**Client-side code is visible to the user.** Never put secrets, API keys, or flags in JavaScript variables, or hidden form fields — they're all accessible to anyone who views the page source. Sensitive data belongs on the server side only.

</details>
