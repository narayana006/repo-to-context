"""Base-62 short codes."""

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def encode(number):
    if number < 0:
        raise ValueError("number must not be negative")
    if number == 0:
        return ALPHABET[0]
    digits = []
    while number:
        number, remainder = divmod(number, 62)
        digits.append(ALPHABET[remainder])
    return "".join(reversed(digits))


def decode(code):
    number = 0
    for char in code:
        number = number * 62 + ALPHABET.index(char)
    return number
