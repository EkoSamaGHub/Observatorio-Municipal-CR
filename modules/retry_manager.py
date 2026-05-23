import random
import time


def retry(operation, retries=3, delay=2, max_delay=30):
    """Retry `operation` with capped exponential backoff + jitter.

    Jitter spreads retries so that many workers hitting the same flaky host do
    not retry in lockstep (avoids synchronized retry storms). Backoff is capped
    at `max_delay` so a slow host cannot inflate total wait without bound.
    """
    for attempt in range(retries):
        try:
            return operation()
        except Exception:
            if attempt == retries - 1:
                raise
            backoff = min(delay * (2 ** attempt), max_delay)
            time.sleep(backoff + random.uniform(0, backoff * 0.25))
