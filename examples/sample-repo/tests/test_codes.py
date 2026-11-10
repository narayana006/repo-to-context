from shortlink.codes import decode, encode


def test_roundtrip():
    for number in (0, 1, 61, 62, 3843, 10**9):
        assert decode(encode(number)) == number


def test_known_values():
    assert encode(0) == "0"
    assert encode(61) == "Z"
    assert encode(62) == "10"
