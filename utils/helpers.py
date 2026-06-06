import time
import logging
import os
from datetime import datetime

# just a simple logger setup - writes to console and to a file
# so we can see what happened after the run is done

def get_logger(name="pipeline"):
    os.makedirs("logs", exist_ok=True)
    log_file = f"logs/run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # dont add handlers if already set up (happens if called multiple times)
    if logger.handlers:
        return logger

    fmt = logging.Formatter("%(asctime)s  %(levelname)s  %(message)s", datefmt="%H:%M:%S")

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    logger.addHandler(ch)
    logger.addHandler(fh)

    return logger


def retry(fn, retries=3, delay=2):
    """
    tries fn up to `retries` times with a small sleep between attempts.
    if all attempts fail it just returns None instead of crashing everything.
    """
    logger = logging.getLogger("pipeline")
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            logger.debug(f"Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))  # back off a bit each time
            else:
                return None


def deduplicate(contacts):
    """
    removes duplicate contacts by email.
    keeps the first occurrence and drops the rest.
    simple but effective - no need to overthink this.
    """
    seen = set()
    clean = []
    for c in contacts:
        email = c.get("email", "").lower().strip()
        if email and email not in seen:
            seen.add(email)
            clean.append(c)
    return clean
