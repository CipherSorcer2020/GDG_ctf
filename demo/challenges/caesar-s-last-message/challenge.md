# Caesar's Last Message

Our spy inside the rival team caught a radio burst this morning.
Their team lead is a huge Roman-history nerd and encrypts every order
with a Caesar cipher - and word is he never changes the shift.

- `message.txt` - the captured transmission

Recover the message (and, ahem, the flag inside it).

---

## What's the setup?

A Caesar cipher shifts every letter of the alphabet by a fixed amount:

```
plain:  A B C D E ... X Y Z
shift+3 D E F G H ... A B C     ("ABC" becomes "DEF")
```

- Every letter moves by the **same amount** - that amount *is* the key
- Only letters move; spaces, digits and punctuation stay put
- Decoding means shifting each letter **back** by the key

You don't know the key. Good news: there are only **25** possible values.

---

## Hints

<details>
<summary>Hint 1 (click to reveal)</summary>

Only 25 possible keys exist. Shift the first word back by 1, then 2,
then 3... one of them produces readable English. An online
"Caesar cipher decoder" will try them all for you.
</details>

<details>
<summary>Hint 2 (click to reveal)</summary>

In Python, one letter shifted back by `k` is:

```python
chr((ord(c) - 65 - k) % 26 + 65)   # for uppercase letters
```

Wrap it in `for k in range(25):` and print every attempt.
</details>

<details>
<summary>Hint 3 (spoiler - click to reveal)</summary>

```python
text = open("message.txt").read()
for k in range(25):
    out = "".join(
        chr((ord(c) - 65 - k) % 26 + 65) if "A" <= c <= "Z" else c
        for c in text
    )
    print(k, "->", out)
```

Run it and look for the attempt containing `flag{`.
</details>

---

## What you just learned

<details>
<summary>Lesson (click to reveal after solving)</summary>

**A cipher is only as strong as its key space.** The Caesar cipher has
just 25 possible keys, so a computer (or a curious human) can try every
one in milliseconds - brute force wins instantly. Real ciphers like AES
have key spaces around 2^256, which makes guessing hopeless. Shifting
letters is fun; it is not security.
</details>
