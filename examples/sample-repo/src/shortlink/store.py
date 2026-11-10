"""SQLite-backed storage for short links."""

import sqlite3

from .codes import encode


class LinkStore:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS links (id INTEGER PRIMARY KEY, url TEXT UNIQUE)"
        )

    def add(self, url):
        """Store ``url`` and return its short code. Adding twice is a no-op."""
        if not url.startswith(("http://", "https://")):
            raise ValueError("only http and https URLs can be shortened")
        self.db.execute("INSERT OR IGNORE INTO links (url) VALUES (?)", (url,))
        self.db.commit()
        (row_id,) = self.db.execute("SELECT id FROM links WHERE url = ?", (url,)).fetchone()
        return encode(row_id)

    def all(self):
        rows = self.db.execute("SELECT id, url FROM links ORDER BY id")
        return [(encode(row_id), url) for row_id, url in rows]
