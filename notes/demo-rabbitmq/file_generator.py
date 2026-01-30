"""Generate files in an inbox directory at a fixed interval.

This helper simulates an upstream system dropping files into an inbox.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from queue_config import INBOX_DIR


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the file generator."""
    parser = argparse.ArgumentParser(description="Generate demo files.")
    parser.add_argument("--inbox", default=INBOX_DIR, help="Inbox directory.")
    parser.add_argument("--count", type=int, default=5, help="Number of files to create.")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between files.")
    return parser.parse_args()


def main() -> None:
    """Create demo files in the inbox at the requested interval."""
    args = parse_args()
    inbox = Path(args.inbox)
    inbox.mkdir(parents=True, exist_ok=True)

    for idx in range(1, args.count + 1):
        path = inbox / f"demo_{idx}.txt"
        path.write_text(f"hello from file {idx}\n", encoding="utf-8")
        print(f"[x] Created {path}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
