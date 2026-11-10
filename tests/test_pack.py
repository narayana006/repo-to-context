import os

import pytest

from repo_to_context import count_tokens, pack_repo, parse_budget, render, scan, select
from repo_to_context.pack import BINARY, INCLUDED, OMITTED, TOO_LARGE
from repo_to_context.ranking import base_score, git_recency, score_file

from conftest import write


def paths(pack, status=None):
    return [f.path for f in pack.files if status is None or f.status == status]


def test_count_tokens():
    assert count_tokens("") == 0
    assert count_tokens("id") == 1
    assert count_tokens("get_user_by_id") == 4  # 14 characters -> 4 tokens
    assert count_tokens("a = b + 1\n") == 6  # a, =, b, +, 1, newline
    assert count_tokens("日本語") == 3
    assert count_tokens("   \t  ") == 0


@pytest.mark.parametrize(
    "text, expected",
    [("8000", 8000), ("120k", 120_000), ("120K", 120_000), ("1.5m", 1_500_000), (" 2k ", 2000)],
)
def test_parse_budget(text, expected):
    assert parse_budget(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "12x", "-5", "0", "k"])
def test_parse_budget_rejects(text):
    with pytest.raises(ValueError):
        parse_budget(text)


def test_scan_honours_gitignore_and_defaults(repo):
    pack = scan(repo, recency={})
    assert paths(pack) == [
        ".gitignore",
        "README.md",
        "important.log",  # re-included by !important.log
        "logo.png",
        "pyproject.toml",
        "src/demo/.gitignore",
        "src/demo/helpers.py",
        "src/demo/main.py",
        "tests/test_helpers.py",
    ]
    assert paths(pack, BINARY) == ["logo.png"]


def test_no_gitignore_and_no_defaults(repo):
    pack = scan(repo, use_gitignore=False, recency={})
    assert "debug.log" in paths(pack)
    assert "build/out.txt" in paths(pack)
    assert "src/demo/generated_schema.py" in paths(pack)
    assert "package-lock.json" not in paths(pack)

    everything = scan(repo, use_gitignore=False, use_default_ignores=False, recency={})
    assert "package-lock.json" in paths(everything)
    assert "node_modules/pkg/index.js" in paths(everything)
    assert ".git/config" in paths(everything)


def test_custom_ignore_rules_override_gitignore(repo):
    pack = scan(repo, ignore=["tests/", "*.toml", "!debug.log"], recency={})
    assert "tests/test_helpers.py" not in paths(pack)
    assert "pyproject.toml" not in paths(pack)
    assert "debug.log" in paths(pack)


def test_max_file_size(repo):
    pack = scan(repo, max_file_bytes=100, recency={})
    assert paths(pack, TOO_LARGE) == ["src/demo/helpers.py"]


def test_non_utf8_file_is_treated_as_binary(tmp_path):
    write(tmp_path, {"latin1.txt": "caf\xe9".encode("latin-1"), "ok.txt": "fine\n"})
    pack = scan(tmp_path, recency={})
    assert paths(pack, BINARY) == ["latin1.txt"]


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="needs symlinks")
def test_symlinks_are_not_followed(repo, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("x")
    try:
        os.symlink(outside, repo / "linked")
    except OSError:
        pytest.skip("cannot create symlinks here")
    assert not any(p.startswith("linked") for p in paths(scan(repo, recency={})))


def test_missing_directory():
    with pytest.raises(NotADirectoryError):
        scan("/definitely/not/here")


def test_ranking_order(repo):
    ranked = [f.path for f in scan(repo, recency={}).ranked]
    assert ranked[:3] == ["README.md", "pyproject.toml", "src/demo/main.py"]
    assert ranked.index("src/demo/helpers.py") < ranked.index("tests/test_helpers.py")


def test_base_score_categories():
    assert base_score("README.md")[1] == "readme"
    assert base_score("docs/README.md")[1] == "doc"
    assert base_score("package.json")[1] == "config"
    assert base_score("Dockerfile")[1] == "config"
    assert base_score("cmd/server/main.go")[1] == "entrypoint"
    assert base_score("src/index.ts")[1] == "entrypoint"
    assert base_score("src/util.rs")[1] == "source"
    assert base_score("src/util_test.go")[1] == "test"
    assert base_score("web/button.spec.ts")[1] == "test"
    assert base_score("tests/data/main.py")[1] == "test"
    assert base_score("LICENSE")[1] == "other"


def test_recent_changes_and_size_adjust_the_score():
    plain, _ = score_file("src/a.py", 100, {})
    recent, why = score_file("src/a.py", 100, {"src/a.py": 0})
    older, _ = score_file("src/a.py", 100, {"src/a.py": 20})
    huge, _ = score_file("src/a.py", 50_000, {})
    deep, _ = score_file("src/x/y/z/a.py", 100, {})
    assert recent > older > plain > deep
    assert plain > huge
    assert "recent" in why


def test_recency_can_reorder_selection(repo):
    pack = scan(repo, recency={"tests/test_helpers.py": 0})
    plain = scan(repo, recency={})
    by_path = {f.path: f.score for f in pack.files}
    assert by_path["tests/test_helpers.py"] == pytest.approx(
        {f.path: f.score for f in plain.files}["tests/test_helpers.py"] + 15.0
    )


def test_git_recency_outside_a_repository(tmp_path):
    assert git_recency(tmp_path) == {}


def test_no_budget_includes_every_text_file(repo):
    pack = pack_repo(repo, recency={})
    assert paths(pack, OMITTED) == []
    assert len(paths(pack, INCLUDED)) == 8


@pytest.mark.parametrize("fmt", ["markdown", "xml", "json"])
@pytest.mark.parametrize("budget", [150, 300, 450, 600, 2000])
def test_output_stays_within_budget(repo, fmt, budget):
    pack = pack_repo(repo, budget, fmt, recency={})
    output = render(pack, fmt)
    included = paths(pack, INCLUDED)
    if included:
        assert count_tokens(output) <= budget
    # the most important file is taken first whenever anything is taken
    if included:
        assert "README.md" in included


def test_budget_prefers_important_files_and_skips_what_does_not_fit(repo):
    pack = scan(repo, recency={})
    select(pack, 60)  # content-only cost, no overhead
    included = paths(pack, INCLUDED)
    assert "README.md" in included and "pyproject.toml" in included
    assert "src/demo/helpers.py" in paths(pack, OMITTED)  # far too big
    assert pack.content_tokens <= 60
    # a smaller, lower-ranked file is still taken after a big one is skipped
    assert "src/demo/main.py" in included


def test_select_can_be_rerun_with_a_different_budget(repo):
    pack = scan(repo, recency={})
    select(pack, None)
    assert paths(pack, OMITTED) == []
    select(pack, 1)
    assert paths(pack, INCLUDED) == []


def test_empty_directory(tmp_path):
    pack = pack_repo(tmp_path, 100, recency={})
    assert pack.files == []
    assert "0 of 0 text files" in render(pack)
