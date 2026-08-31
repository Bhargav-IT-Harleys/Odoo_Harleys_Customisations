import time


class RetryManager:
    """Simple retry helper for transient API failures."""

    def __init__(self, attempts=3, delay=2):
        self.attempts = attempts
        self.delay = delay

    def run(self, func, *args, **kwargs):
        last_error = None
        for attempt in range(1, self.attempts + 1):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                last_error = exc
                if attempt >= self.attempts:
                    raise
                time.sleep(self.delay)
        raise last_error
