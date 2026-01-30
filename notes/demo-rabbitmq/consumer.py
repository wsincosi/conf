"""Consume messages from a RabbitMQ queue and acknowledge each one."""

import pika
from queue_config import QUEUE_NAME


def main() -> None:
    """Connect to RabbitMQ and start a simple consuming loop."""
    connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
    channel = connection.channel()

    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    channel.basic_qos(prefetch_count=1)

    def on_message(ch, method, properties, body) -> None:
        text = body.decode("utf-8", errors="replace")
        print(f"[x] Received {text!r}")
        # Acknowledge after processing
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=on_message)

    print("[*] Waiting for messages. To exit press CTRL+C")
    try:
        channel.start_consuming()
    finally:
        connection.close()


if __name__ == "__main__":
    main()
