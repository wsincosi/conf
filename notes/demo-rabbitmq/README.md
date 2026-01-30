# RabbitMQ + Python demo

This is a tiny playground for learning RabbitMQ from Python using `pika`.
It focuses on `basic_publish` and the simplest publish/consume flow.

## What RabbitMQ is (short)
RabbitMQ is a message broker. Producers publish messages to **exchanges**.
Exchanges route messages to **queues** based on rules (bindings). Consumers
read from queues and ack messages when done. This decouples services and
smooths spikes, retries, and backpressure.

## Quick start

1) Start RabbitMQ (Docker):

```bash
cd demo-rabbitmq
docker-compose up -d
```

If you have the newer Docker Compose plugin, you can also use `docker compose`.

2) Create a Python virtual env + install deps:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

3) Run a consumer (in one terminal):

```bash
python consumer.py
```

4) Publish messages (in another terminal):

```bash
python publisher.py "hello"
python publisher.py "another message"
```

You should see the consumer print received messages.

## RabbitMQ management UI
Open `http://localhost:15672` and log in with:
- user: `guest`
- pass: `guest`

## Files
- `publisher.py` uses `basic_publish` to send a message
- `consumer.py` declares the queue and consumes messages
- `docker-compose.yml` runs RabbitMQ with the management UI
- `file_watcher.py` watches a directory and publishes file metadata
- `worker.py` consumes file metadata and processes files
- `file_generator.py` simulates an upstream system creating files

## Notes on basic_publish
`basic_publish` sends a message to an exchange and routing key. In this demo:
- exchange: "" (the default direct exchange)
- routing key: "hello" (the queue name)

When using the default exchange, the routing key must match the queue name.

Try changing:
- The routing key to see unroutable messages
- The queue name to a new value
- The message properties (e.g., delivery_mode=2 for persistence)

## Useful next steps
- Add acknowledgements and retry logic
- Use a fanout or topic exchange
- Add dead-letter queues

## File ingest demo (watcher → queue → worker → Postgres)

This flow models: files appear in an inbox → metadata is published to a queue →
a worker consumes the message, processes the file, and writes metadata to Postgres.

1) Start RabbitMQ + Postgres:

```bash
docker-compose up -d
```

2) Install deps:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

3) In terminal A, run the worker:

```bash
python worker.py
```

4) In terminal B, run the watcher:

```bash
python file_watcher.py
```

5) In terminal C, generate demo files:

```bash
python file_generator.py --count 5 --interval 1
```

Files will be moved to `processed/` after the worker handles them, and metadata
will be stored in Postgres (if `psycopg` is installed).

### Useful env vars
- `AMQP_URL` (default: `amqp://guest:guest@localhost:5672/`)
- `DB_DSN` (default: `postgresql://postgres:postgres@localhost:5432/rabbit_demo`)
