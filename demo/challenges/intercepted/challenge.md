# Intercepted

Our spy caught a radio burst this morning. It is clearly a message - and there is a
flag hidden inside it - but it is scrambled. The sender is a big fan of ancient
history, and word is he never changes his habits.

- `message.txt` - the captured transmission

Read the message and find the flag inside it.

## Hints

<details>
<summary>Hint 1</summary>

Look closely at the text. Spaces, digits and punctuation look normal - only the
letters are scrambled. And every line ends with the same four-letter chunk. What
short word would a radio operator put at the end of every line?
</details>

<details>
<summary>Hint 2</summary>

Every letter was moved the same distance along the alphabet (for example A becomes D,
B becomes E...). There are only 25 possible distances, so you can simply try them all.
Search online for a "Caesar cipher decoder" that shows every shift at once.
</details>

<details>
<summary>Hint 3 (walkthrough)</summary>

Prefer a script? This prints all 25 shifts of the message:

```python
text = open("message.txt").read()

def shift(ch, k):
    if ch.isupper():
        return chr((ord(ch) - 65 - k) % 26 + 65)
    if ch.islower():
        return chr((ord(ch) - 97 - k) % 26 + 97)
    return ch

for k in range(1, 26):
    print(k, "->", "".join(shift(c, k) for c in text))
```

Run it and look for the one attempt that reads like English. The flag is in that
attempt, in the line that mentions the code word.
</details>

## What you just learned

**A cipher is only as strong as its number of possible keys.** This one has just 25, so
a computer (or a patient human) can try them all in a blink. Real encryption such as AES
has more keys than there are atoms on Earth. Shifting letters is fun - but it is not security.
