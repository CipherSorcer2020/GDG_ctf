# Coffee Break

A local coffee shop built its own little website - and the developer was in a hurry.
Download the page, open it in your browser and take a look around.

- `index.html` - the coffee shop home page

Something in there should not have been left behind. Find the flag.

## Hints

<details>
<summary>Hint 1</summary>

What a web page shows is only half the story. Your browser has built-in tools to look
behind the scenes - try right-clicking the page and choosing **Inspect**, or press **F12**.
</details>

<details>
<summary>Hint 2</summary>

Developers leave notes and temporary values in the page while they work. Look at the
page's code (the **Elements** / **Sources** view, or press Ctrl+U) and read it like a
book - especially anything inside `<script>` tags.
</details>

<details>
<summary>Hint 3 (walkthrough)</summary>

Inside the script there is a value named `FLAG`. Open the **Console** tab in the developer
tools, type `FLAG` and press Enter. Or press Ctrl+U and search the code for `flag{`.
(Careful - the page also contains a couple of decoys that are not the flag.)
</details>

## What you just learned

**Anything sent to your browser can be read by you.** Never put secrets, keys or passwords
into a web page's code or hidden fields - everything the browser receives is visible to
everyone. Sensitive data belongs on the server.
