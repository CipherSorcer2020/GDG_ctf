# The Mole

The mole finally slipped up. They handed back their laptop, wiped - or so they thought.
One file survived in the recycle bin:

- `mole.exe` - a small program that asks for a password, and refuses *everyone*

You are the reverse-engineering team now. The password is the flag. Find what the program knows.

## Hints

<details>
<summary>Hint 1</summary>

You do not have to run the program to learn about it. Everything a program prints, and
everything it compares your input against, has to be stored inside the file somewhere.
Humans write words, and words are still words inside a file.
</details>

<details>
<summary>Hint 2</summary>

Try to read the plain text hiding inside `mole.exe`. The `strings` command does exactly
that (Linux, macOS, or Git Bash on Windows), and free websites can "extract strings from
a file". No tools? Open the file in a text editor (Notepad++ or VS Code work best) and
search for `flag{`.
</details>

<details>
<summary>Hint 3 (walkthrough)</summary>

A few lines will look like passwords - one of them is a decoy. Try each candidate with
`mole.exe <candidate>` in a terminal. The real one answers ACCESS GRANTED, and that exact
text is your flag.
</details>

## What you just learned

**Compiled does not mean secret.** Passwords and keys baked into a program can be read with
beginner tools - `strings` has "cracked" more protected software than any clever math.
Real apps keep secrets on a server, never inside the program you hand out.
