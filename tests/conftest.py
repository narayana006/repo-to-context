import pytest


def write(root, files):
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")


@pytest.fixture
def repo(tmp_path):
    """A small project with ignored, binary and nested files."""
    root = tmp_path / "demo"
    root.mkdir()
    write(
        root,
        {
            "README.md": "# Demo\n\nA demo project.\n",
            "pyproject.toml": '[project]\nname = "demo"\n',
            ".gitignore": "*.log\nbuild/\n!important.log\n",
            "src/demo/main.py": "def main():\n    print('hello')\n",
            "src/demo/helpers.py": "def add(a, b):\n    return a + b\n" * 20,
            "src/demo/.gitignore": "generated_*.py\n",
            "src/demo/generated_schema.py": "X = 1\n",
            "tests/test_helpers.py": "def test_add():\n    assert True\n",
            "debug.log": "noise\n",
            "important.log": "keep me\n",
            "build/out.txt": "artifact\n",
            "node_modules/pkg/index.js": "module.exports = {}\n",
            "package-lock.json": "{}\n",
            "logo.png": b"\x89PNG\r\n\x1a\n\x00\x00\x00\x00",
            ".git/config": "[core]\n",
        },
    )
    return root
