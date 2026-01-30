"""Publish a single message to a RabbitMQ queue using basic_publish."""

import sys

import pika
from queue_config import QUEUE_NAME


def main() -> None:
    """Connect to RabbitMQ and publish one message to the configured queue."""
    message = " ".join(sys.argv[1:]) or "Hello from RabbitMQ"

    connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
    channel = connection.channel()

    # Declaring ensures the queue exists before publishing.
    channel.queue_declare(queue=QUEUE_NAME, durable=True)

    channel.basic_publish(
        exchange="",
        routing_key=QUEUE_NAME,
        body=message.encode("utf-8"),
        properties=pika.BasicProperties(
            delivery_mode=2,  # Make message persistent
        ),
    )

    print(f"[x] Sent {message!r} to queue {QUEUE_NAME!r}")
    connection.close()


if __name__ == "__main__":
    main()
