#!/usr/bin/env python3
import hashlib
import os
import sqlite3
import subprocess
import time
from pathlib import Path

WATCH_DIR = Path("/path/to/the/directory").resolve()
STATE_DIR = Path.home() / ".local/state/new-file-watcher"
DB = STATE_DIR / "seen.sqlite3"

POLL_SECONDS = 10
STABLE_SECONDS = 3

STATE_DIR.mkdir(parents=True, exist_ok=True)

db = sqlite3.connect(DB)
db.execute("""
CREATE TABLE IF NOT EXISTS processed (
    path TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    processed_at INTEGER NOT NULL,
    PRIMARY KEY (path, fingerprint)
)
""")
db.commit()


def file_fingerprint(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_stable(path: Path) -> bool:
    try:
        first = path.stat()
        time.sleep(STABLE_SECONDS)
        second = path.stat()
        return (
            first.st_size == second.st_size
            and first.st_mtime_ns == second.st_mtime_ns
        )
    except FileNotFoundError:
        return False


def already_processed(path: Path, fingerprint: str) -> bool:
    row = db.execute(
        "SELECT 1 FROM processed WHERE path = ? AND fingerprint = ?",
        (str(path), fingerprint),
    ).fetchone()
    return row is not None


def mark_processed(path: Path, fingerprint: str) -> None:
    db.execute(
        "INSERT OR IGNORE INTO processed VALUES (?, ?, ?)",
        (str(path), fingerprint, int(time.time())),
    )
    db.commit()


def process_file(path: Path) -> None:
    # Replace this with your real curl command.
    # Example:
    subprocess.run(
        [
            "curl",
            "--fail",
            "--retry", "5",
            "--retry-delay", "10",
            "--data-binary", f"@{path}",
            "https://example.com/endpoint",
        ],
        check=True,
    )


def scan_once() -> None:
    for path in sorted(WATCH_DIR.iterdir()):
        if not path.is_file():
            continue

        if not is_stable(path):
            continue

        fingerprint = file_fingerprint(path)

        if already_processed(path, fingerprint):
            continue

        process_file(path)
        mark_processed(path, fingerprint)


while True:
    try:
        scan_once()
    except Exception as e:
        print(f"watcher error: {e}", flush=True)

    time.sleep(POLL_SECONDS)
