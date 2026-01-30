"""Consume file metadata messages and process the referenced files.

The worker pulls JSON messages from RabbitMQ, reads the file from disk,
optionally writes metadata to PostgreSQL, and then moves the file into a
processed or failed directory.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Optional

import pika

from queue_config import FAILED_DIR, IMPORT_QUEUE, INBOX_DIR, PROCESSED_DIR


def connect_db(dsn: str):
    """Connect to PostgreSQL if psycopg is installed; return None otherwise."""
    try:
        import psycopg
    except Exception:
        return None

    return psycopg.connect(dsn)


def ensure_table(connection) -> None:
    """Create the demo table if it does not already exist."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS imported_files (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            path TEXT NOT NULL,
            size BIGINT NOT NULL,
            mtime DOUBLE PRECISION NOT NULL,
            sha256 TEXT NOT NULL,
            imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    connection.commit()


def insert_metadata(connection, payload: dict) -> None:
    """Insert a metadata row into PostgreSQL."""
    connection.execute(
        """
        INSERT INTO imported_files (name, path, size, mtime, sha256)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            payload["name"],
            payload["path"],
            payload["size"],
            payload["mtime"],
            payload["sha256"],
        ),
    )
    connection.commit()


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the worker."""
    parser = argparse.ArgumentParser(description="Consume import queue messages.")
    parser.add_argument("--queue", default=IMPORT_QUEUE, help="Queue name to consume.")
    parser.add_argument("--inbox", default=INBOX_DIR, help="Inbox directory.")
    parser.add_argument(
        "--processed-dir", default=PROCESSED_DIR, help="Where to move processed files."
    )
    parser.add_argument(
        "--failed-dir", default=FAILED_DIR, help="Where to move failed files."
    )
    parser.add_argument(
        "--amqp-url",
        default=os.getenv("AMQP_URL", "amqp://guest:guest@localhost:5672/"),
        help="AMQP connection URL.",
    )
    parser.add_argument(
        "--db-dsn",
        default=os.getenv(
            "DB_DSN", "postgresql://postgres:postgres@localhost:5432/rabbit_demo"
        ),
        help="PostgreSQL DSN for metadata writes.",
    )
    return parser.parse_args()


def move_file(path: Path, destination_dir: Path) -> None:
    """Move a file into a destination directory, creating it if needed."""
    destination_dir.mkdir(parents=True, exist_ok=True)
    target = destination_dir / path.name
    shutil.move(str(path), str(target))


def process_payload(payload: dict, connection: Optional[object], processed_dir: Path) -> None:
    """Process the file referenced by a payload and store metadata if possible."""
    file_path = Path(payload["path"])
    if not file_path.exists():
        raise FileNotFoundError(f"File does not exist: {file_path}")

    if connection is not None:
        insert_metadata(connection, payload)

    move_file(file_path, processed_dir)


def main() -> None:
    """Run the queue worker loop."""
    args = parse_args()

    Path(args.inbox).mkdir(parents=True, exist_ok=True)
    processed_dir = Path(args.processed_dir)
    failed_dir = Path(args.failed_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)

    db_connection = connect_db(args.db_dsn)
    if db_connection is not None:
        ensure_table(db_connection)
        print("[*] PostgreSQL connected; metadata will be stored")
    else:
        print("[*] psycopg not installed; metadata will not be stored")

    connection = pika.BlockingConnection(pika.URLParameters(args.amqp_url))
    channel = connection.channel()
    channel.queue_declare(queue=args.queue, durable=True)
    channel.basic_qos(prefetch_count=1)

    def on_message(ch, method, properties, body) -> None:  # type: ignore[override]
        payload = None
        try:
            payload = json.loads(body.decode("utf-8"))
            process_payload(payload, db_connection, processed_dir)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print(f"[x] Processed {payload['name']!r}")
        except Exception as exc:  # pragma: no cover - demo logging
            print(f"[!] Failed to process message: {exc}")
            if isinstance(payload, dict) and "path" in payload:
                try:
                    move_file(Path(payload["path"]), failed_dir)
                except Exception:
                    pass
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    channel.basic_consume(queue=args.queue, on_message_callback=on_message)

    print(f"[*] Waiting for messages on {args.queue!r}. To exit press CTRL+C")
    try:
        channel.start_consuming()
    finally:
        connection.close()
        if db_connection is not None:
            db_connection.close()


if __name__ == "__main__":
    main()
