# The Intern's Backup

An intern just walked out of Totally-Secure-Corp with a backup of the company's login
database. Nobody there ever thought about what happens when that file leaks...

- `hashes.txt` - the stolen database dump (5 accounts)
- `wordlist.txt` - a leaked list of passwords that people like to pick

The passwords in the dump are not stored as plain text. Work out the passwords of
`alice`, `bob`, `carol` and `dave`, then build the flag like this:

1. Put the four passwords in that order (alice, bob, carol, dave)
2. Join them with underscores
3. Wrap the result: `flag{word1_word2_word3_word4}`

The `root` line is your safety net: it holds the fingerprint of the finished flag.

## Hints

<details>
<summary>Hint 1</summary>

Those long strings of letters and digits are *fingerprints* of the passwords. The same
password always gives the same fingerprint, and you cannot turn a fingerprint back into
the password. But you can **guess**: compute the fingerprint of every word in
`wordlist.txt` and see which one matches.
</details>

<details>
<summary>Hint 2</summary>

Each fingerprint is 32 characters long - that length tells you which kind it is (search
for "hash identifier" if you want to confirm). Use an online generator for that kind of
hash and try the words one at a time, or let a small script do the boring part.
</details>

<details>
<summary>Hint 3 (walkthrough)</summary>

This script cracks every account that has a match in the wordlist:

```python
import hashlib

words = [w.strip() for w in open("wordlist.txt")]
lookup = {hashlib.md5(w.encode()).hexdigest(): w for w in words}

for line in open("hashes.txt"):
    parts = line.split()
    if len(parts) == 2 and parts[1] in lookup:
        print(parts[0], "->", lookup[parts[1]])
```

Then assemble the flag from the four passwords. To double-check, hash your finished flag
(the whole text, including `flag{` and `}`) and compare it with the `root` line.
</details>

## What you just learned

**Hashing is not encryption.** A hash is meant to be one-way, so a leaked database does
not hand over everyone's password - attackers can only *guess*, and guessing is fast when
people pick common words. That is why real sites use slow, salted hashes (like bcrypt)
and why you should never reuse a simple password.
