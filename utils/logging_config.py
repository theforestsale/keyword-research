import logging
import queue
import os
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler


def setup_logging(app):
    log_queue = queue.Queue(-1)

    queue_handler = QueueHandler(log_queue)

    log_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "app.log"),
        maxBytes=1_000_000,
        backupCount=3,
    )
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        "[%(levelname)s] %(name)s: %(message)s"
    ))

    queue_handler.setLevel(logging.INFO)
    file_handler.setLevel(logging.INFO)
    console_handler.setLevel(logging.WARNING)

    listener = QueueListener(log_queue, file_handler, console_handler)
    listener.start()

    app.logger.addHandler(queue_handler)
    app.logger.setLevel(logging.INFO)

    return listener
