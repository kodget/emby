"""Filesystem-only helpers for read-only persistence diagnostics."""

from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit


def sqlite_file_missing(config):
    """Avoid opening a nonexistent SQLite file, which would create a database."""
    raw_name = config.get("NAME") if config else ""
    name = str(raw_name or "")
    if name.startswith("file:"):
        target = urlsplit(name)
        if parse_qs(target.query).get("mode") == ["memory"]:
            return False
        name = unquote(target.path)
    return bool(name and name != ":memory:" and not Path(name).is_file())
