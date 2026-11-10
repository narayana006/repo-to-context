import json
import xml.etree.ElementTree as ET

import pytest

from repo_to_context import pack_repo, render
from repo_to_context.cli import main
from repo_to_context.render import render_tree

from conftest import write


def test_tree_lists_every_file_with_counts(repo):
    pack = pack_repo(repo, recency={})
    tree = render_tree(pack)
    lines = tree.splitlines()
    assert lines[0] == "demo/"
    assert lines[1] == "├── src/"  # directories come first
    assert any(line.endswith("main.py  (15 tokens)") for line in lines)
    assert "└── pyproject.toml" in lines[-1]
    assert "logo.png  (binary, skipped)" in tree
    assert "debug.log" not in tree


def test_tree_marks_omitted_files(repo):
    pack = pack_repo(repo, 300, recency={})
    assert "helpers.py  (300 tokens, omitted)" in render_tree(pack)


def test_markdown_output(repo):
    out = render(pack_repo(repo, recency={}), "markdown")
    assert out.startswith("# Repository context: demo\n")
    assert "Token counts are approximate." in out
    assert "### `src/demo/main.py`\n\n```python\ndef main():\n    print('hello')\n```\n" in out
    # most important file comes first
    assert out.index("### `README.md`") < out.index("### `src/demo/main.py`")
    assert "noise" not in out and "artifact" not in out


def test_markdown_fence_grows_past_backticks_in_content(tmp_path):
    write(tmp_path, {"notes.md": "Use:\n\n```sh\nls\n```\n"})
    out = render(pack_repo(tmp_path, recency={}), "markdown")
    assert "````markdown\nUse:\n\n```sh\nls\n```\n````\n" in out


def test_xml_output_is_well_formed_and_escaped(tmp_path):
    write(tmp_path, {"a&b.py": "if a < b and c > d:\n    s = '&amp;' + \"\x07\"\n"})
    pack = pack_repo(tmp_path, 5000, "xml", recency={})
    root = ET.fromstring(render(pack, "xml"))
    assert root.tag == "repository"
    assert root.get("token_budget") == "5000"
    files = root.findall("./files/file")
    assert [f.get("path") for f in files] == ["a&b.py"]
    assert files[0].text.strip() == "if a < b and c > d:\n    s = '&amp;' + \"\""
    assert int(files[0].get("tokens")) > 0
    assert "a&b.py" in root.find("tree").text


def test_json_output(repo):
    pack = pack_repo(repo, 300, "json", recency={})
    doc = json.loads(render(pack, "json"))
    assert doc["repository"] == "demo"
    assert doc["token_counts"] == "approximate"
    assert doc["token_budget"] == 300
    assert doc["content_tokens"] == sum(f["tokens"] for f in doc["files"])
    assert {"path": "logo.png", "tokens": 0, "reason": "binary"} in doc["not_included"]
    for item in doc["files"]:
        assert set(item) == {"path", "tokens", "score", "content"}


def test_unknown_format(repo):
    with pytest.raises(ValueError):
        render(pack_repo(repo, recency={}), "yaml")


def test_cli_writes_file_and_reports(repo, tmp_path, capsys):
    out = tmp_path / "context.xml"
    code = main([str(repo), "--budget", "1k", "--format", "xml", "-o", str(out), "--no-git"])
    assert code == 0
    ET.fromstring(out.read_text(encoding="utf-8"))
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "of a 1,000 budget (approximate)" in captured.err
    assert "1 binary or oversized files skipped" in captured.err


def test_cli_stdout_ignore_flags_and_quiet(repo, tmp_path, capsys):
    extra = tmp_path / "extra.ignore"
    extra.write_text("*.toml\n")
    code = main([str(repo), "-i", "tests/", "--ignore-file", str(extra), "-q", "--no-git", "-f", "md"])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    assert "test_helpers.py" not in captured.out
    assert "pyproject.toml" not in captured.out
    assert "### `README.md`" in captured.out


def test_cli_list(repo, capsys):
    assert main([str(repo), "--list", "--no-git", "--budget", "300"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ["SCORE", "TOKENS", "STATUS", "WHY", "PATH"]
    assert lines[1].split() == ["100.0", "10", "included", "readme", "README.md"]
    assert any("omitted" in line and "helpers.py" in line for line in lines)


def test_cli_warns_when_nothing_fits(repo, capsys):
    assert main([str(repo), "--budget", "5", "--no-git"]) == 0
    assert "too small for any file" in capsys.readouterr().err


def test_cli_errors(tmp_path, capsys):
    assert main([str(tmp_path / "missing")]) == 2
    assert "repo-to-context:" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main([str(tmp_path), "--budget", "lots"])
