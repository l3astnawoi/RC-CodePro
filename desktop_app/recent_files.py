"""A small on-disk "recently opened" list for .rcmodel files.

Backed by QSettings (per-user, no server, no telemetry) so the Home page's
Recent Projects list reflects files the user actually opened or saved,
instead of hard-coded demo rows. Entries that no longer exist on disk are
dropped silently on load.
"""
import json
import os

from PySide6.QtCore import QSettings

_ORG, _APP, _KEY = "RCCodePro", "Desktop", "recent_projects"
MAX_ENTRIES = 8


def _settings():
    return QSettings(_ORG, _APP)


def load():
    """Existing file paths, most-recently-used first."""
    raw = _settings().value(_KEY, "")
    try:
        paths = json.loads(raw) if raw else []
    except (TypeError, ValueError):
        paths = []
    return [p for p in paths if isinstance(p, str) and os.path.isfile(p)]


def add(path):
    path = os.path.abspath(str(path))
    paths = [p for p in load() if os.path.abspath(p) != path]
    paths.insert(0, path)
    _settings().setValue(_KEY, json.dumps(paths[:MAX_ENTRIES]))


def remove(path):
    path = os.path.abspath(str(path))
    paths = [p for p in load() if os.path.abspath(p) != path]
    _settings().setValue(_KEY, json.dumps(paths))
