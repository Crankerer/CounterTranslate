import atexit
import logging
import logging.handlers
import os
import queue

_listener: logging.handlers.QueueListener | None = None


def setup(log_dir: str) -> logging.Logger:
    """Log to countertranslate.log via a background listener thread.

    Callers only enqueue records; the file write + flush happens on the
    listener thread, so logging never blocks the Tk thread, the tail thread
    or the pool workers on disk I/O.
    """
    global _listener
    path = os.path.join(log_dir, "countertranslate.log")
    logger = logging.getLogger("ct")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    _stop_listener()
    fh = logging.FileHandler(path, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter(
        "%(asctime)s.%(msecs)03d [%(levelname)-5s] %(message)s",
        datefmt="%H:%M:%S",
    ))
    q: queue.SimpleQueue = queue.SimpleQueue()
    logger.addHandler(logging.handlers.QueueHandler(q))
    _listener = logging.handlers.QueueListener(q, fh)
    _listener.start()
    logger.propagate = False
    return logger


@atexit.register
def _stop_listener() -> None:
    """Flush pending records and stop the listener (also runs at exit)."""
    global _listener
    if _listener is not None:
        _listener.stop()
        _listener = None


def get() -> logging.Logger:
    return logging.getLogger("ct")
