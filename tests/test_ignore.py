import pytest

from repo_to_context.ignore import IgnoreRules, parse_rule


def rules(*patterns, base=""):
    r = IgnoreRules()
    r.add_patterns(patterns, base=base)
    return r


@pytest.mark.parametrize(
    "pattern, path, is_dir, expected",
    [
        ("*.log", "debug.log", False, True),
        ("*.log", "logs/app/debug.log", False, True),
        ("*.log", "debug.log.txt", False, False),
        ("build/", "build", True, True),
        ("build/", "src/build", True, True),
        ("build/", "build", False, False),  # dir-only pattern, path is a file
        ("/dist", "dist", True, True),
        ("/dist", "pkg/dist", True, False),  # anchored to the root
        ("docs/*.md", "docs/a.md", False, True),
        ("docs/*.md", "docs/sub/a.md", False, False),  # * does not cross /
        ("docs/*.md", "other/docs/a.md", False, False),  # inner slash anchors
        ("**/temp", "a/b/temp", True, True),
        ("**/temp", "temp", True, True),
        ("logs/**", "logs/a/b.txt", False, True),
        ("a/**/z", "a/z", False, True),
        ("a/**/z", "a/b/c/z", False, True),
        ("file?.txt", "file1.txt", False, True),
        ("file?.txt", "file10.txt", False, False),
        ("[abc].py", "b.py", False, True),
        ("[!abc].py", "b.py", False, False),
        ("[!abc].py", "d.py", False, True),
        (r"\#notes", "#notes", False, True),
        (".env", ".env", False, True),
        (".env", ".envrc", False, False),
    ],
)
def test_single_pattern(pattern, path, is_dir, expected):
    assert rules(pattern).is_ignored(path, is_dir) is expected


def test_comments_and_blank_lines_are_skipped():
    assert parse_rule("# comment") is None
    assert parse_rule("   ") is None
    assert parse_rule("") is None
    assert parse_rule("/") is None


def test_negation_and_last_match_wins():
    r = rules("*.log", "!keep.log")
    assert r.is_ignored("a.log")
    assert not r.is_ignored("keep.log")
    assert rules("!keep.log", "*.log").is_ignored("keep.log")


def test_match_distinguishes_no_match_from_reinclude():
    r = rules("*.log", "!keep.log")
    assert r.match("a.log") is True
    assert r.match("keep.log") is False
    assert r.match("a.txt") is None


def test_rules_from_a_nested_directory_only_apply_there():
    r = rules("*.txt", "/local.cfg", base="pkg/sub")
    assert r.is_ignored("pkg/sub/a.txt")
    assert r.is_ignored("pkg/sub/deep/a.txt")
    assert not r.is_ignored("pkg/a.txt")
    assert r.is_ignored("pkg/sub/local.cfg")
    assert not r.is_ignored("pkg/sub/deep/local.cfg")


def test_trailing_spaces_are_trimmed():
    assert rules("*.tmp   ").is_ignored("a.tmp")
