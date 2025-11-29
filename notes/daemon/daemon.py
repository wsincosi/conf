#!/usr/bin/env python3

import time
import logging
import signal
import sys

logging.basicConfig(
    filename="/tmp/mydaemon.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

running = True

def handle_exit(signum, frame):
    global running
    logging.info("Daemon stopping...")
    running = False

signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)

logging.info("Daemon started")

while running:
    logging.info("Daemon heartbeat...")
    time.sleep(5)

logging.info("Daemon exited cleanly")
sys.exit(0)

