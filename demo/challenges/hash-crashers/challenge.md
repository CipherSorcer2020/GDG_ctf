# Hash Crashers

An intern just walked out of Totally-Secure-Corp with a backup of the
login database. Yes, the same company that still hashes passwords with
**MD5**. Their loss is your gain.

- `hashes.txt` - the stolen database dump (5 accounts)
- `wordlist.txt` - a leaked list of passwords their users like to pick

Crack the accounts. Assemble the flag from what you find.

---

## What's the setup?

MD5 turns any text into a 32-character **fingerprint**:

```
"summer" -> 1d028a104d4b5c1a3f0d0e1f0e12e0aa   (one-way, no key)
```

- The same input **always** produces the same hash
- There is no "decrypt" - you cannot reverse a hash
- But you **can guess**: hash every word in `wordlist.txt` and see which
  hash it matches. This is a *dictionary attack*.

**The flag rule (from the dump's README):**

1. Crack `alice`, `bob`, `carol`, `dave` - each password is one word
2. Join the four words **in that order** with underscores
3. Wrap it: `flag{word1_word2_word3_word4}`
4. Verify: your finished flag hashed with MD5 must equal `root`'s hash

---

## Hints

<details>
<summary>Hint 1 (click to reveal)</summary>

Hash every line of `wordlist.txt` with MD5 and compare it to `alice`'s
hash. Repeat for the other accounts. An online "MD5 generator" works,
one word at a time - tedious but effective.
</details>

<details>
<summary>Hint 2 (click to reveal)</summary>

```python
import hashlib
target = open("hashes.txt").read()
for word in open("wordlist.txt"):
    h = hashlib.md5(word.strip().encode()).hexdigest()
    if h in target:
        print(word.strip(), "->", h)
```
</details>

<details>
<summary>Hint 3 (spoiler - click to reveal)</summary>

The four words are `bluemoon`, `summer`, `keyboard`, `tiger`.
Assembled: `flag{bluemoon_summer_keyboard_tiger}` - confirm by hashing
it yourself before submitting. (Pasting `root`'s hash into an online
MD5 lookup will find nothing - that is exactly the lesson.)
</details>

---

## What you just learned

<details>
<summary>Lesson (click to reveal after solving)</summary>

**Hashing is not encryption.** Encryption is meant to be reversed with
a key; hashing is *designed* to be one-way. Passwords are stored as
hashes so that a leaked database doesn't hand over everyone's password
- attackers can only *guess* (dictionary attacks, rules, rainbow
tables). MD5 is broken for this job nowadays (fast GPUs guess billions
per second), which is why real sites use slow, salted hashes like bcrypt.
</details>
