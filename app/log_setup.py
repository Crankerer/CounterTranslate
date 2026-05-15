import logging
import os


def setup(log_dir: str) -> logging.Logger:
    path = os.path.join(log_dir, "countertranslate.log")
    logger = logging.getLogger("ct")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    fh = logging.FileHandler(path, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter(
        "%(asctime)s.%(msecs)03d [%(levelname)-5s] %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(fh)
    logger.propagate = False
    return logger


def get() -> logging.Logger:
    return logging.getLogger("ct")
