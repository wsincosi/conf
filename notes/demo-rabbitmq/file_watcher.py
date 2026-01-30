"""Watch an inbox directory and publish file metadata to RabbitMQ.

This demo uses watchdog to detect new files, then publishes a JSON message
containing metadata (path, size, mtime, checksum) to a queue. The file
contents stay on disk; the queue only carries a lightweight reference.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import time
from pathlib import Path

import pika
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from queue_config import FAILED_DIR, IMPORT_QUEUE, INBOX_DIR


class FileEventHandler(FileSystemEventHandler):
    """Push filesystem events into a thread-safe queue for processing."""

    def __init__(self, event_queue: queue.Queue[Path]) -> None:
        self._event_queue = event_queue

    def on_created(self, event) -> None:  # type: ignore[override]
        if not event.is_directory:
            self._event_queue.put(Path(event.src_path))

    def on_moved(self, event) -> None:  # type: ignore[override]
        if not event.is_directory:
            self._event_queue.put(Path(event.dest_path))


class RabbitPublisher:
    """Publish file metadata messages to a RabbitMQ queue."""

    def __init__(self, amqp_url: str, routing_key: str) -> None:
        self._amqp_url = amqp_url
        self._routing_key = routing_key
        self._connection = pika.BlockingConnection(pika.URLParameters(amqp_url))
        self._channel = self._connection.channel()
        self._channel.queue_declare(queue=routing_key, durable=True)

    def publish(self, payload: dict) -> None:
        """Publish a JSON payload to the configured queue."""
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self._channel.basic_publish(
            exchange="",
            routing_key=self._routing_key,
            body=body,
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
            ),
        )

    def close(self) -> None:
        """Close the underlying RabbitMQ connection."""
        self._connection.close()


def wait_for_stable_file(path: Path, checks: int = 3, delay: float = 0.2) -> None:
    """Wait until a file's size stops changing for a few checks."""
    last_size = -1
    for _ in range(checks):
        size = path.stat().st_size
        if size == last_size:
            return
        last_size = size
        time.sleep(delay)


def sha256sum(path: Path) -> str:
    """Compute a SHA-256 checksum for the given file path."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_payload(path: Path) -> dict:
    """Build a JSON-serializable metadata payload for a file."""
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "name": path.name,
        "size": stat.st_size,
        "mtime": stat.st_mtime,
        "sha256": sha256sum(path),
    }


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the watcher."""
    parser = argparse.ArgumentParser(description="Watch an inbox and publish metadata.")
    parser.add_argument("--inbox", default=INBOX_DIR, help="Inbox directory to watch.")
    parser.add_argument(
        "--routing-key",
        default=IMPORT_QUEUE,
        help="Queue name (routing key for default exchange).",
    )
    parser.add_argument(
        "--amqp-url",
        default=os.getenv("AMQP_URL", "amqp://guest:guest@localhost:5672/"),
        help="AMQP connection URL.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the filesystem watcher and publish events to RabbitMQ."""
    args = parse_args()
    inbox = Path(args.inbox)
    inbox.mkdir(parents=True, exist_ok=True)
    Path(FAILED_DIR).mkdir(parents=True, exist_ok=True)

    event_queue: queue.Queue[Path] = queue.Queue()
    handler = FileEventHandler(event_queue)
    observer = Observer()
    observer.schedule(handler, str(inbox), recursive=False)

    publisher = RabbitPublisher(args.amqp_url, args.routing_key)

    observer.start()
    print(f"[*] Watching {inbox.resolve()} -> queue {args.routing_key!r}")

    try:
        while True:
            path = event_queue.get()
            try:
                wait_for_stable_file(path)
                payload = build_payload(path)
                publisher.publish(payload)
                print(f"[x] Published {path.name!r}")
            except Exception as exc:  # pragma: no cover - demo logging
                print(f"[!] Failed to publish {path}: {exc}")
    except KeyboardInterrupt:
        print("\n[*] Stopping watcher")
    finally:
        observer.stop()
        observer.join()
        publisher.close()


if __name__ == "__main__":
    main()
