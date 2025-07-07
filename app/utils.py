import logging
import time
from functools import wraps

log = logging.getLogger("utils")


def with_interval_check(func):
    """
    A decorator for check classes' `is_healthy` method to add periodic execution.

    The decorated class instance must have the following attributes:
    - interval_seconds: int
    - last_run_timestamp: float
    - last_run_result: bool
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        log.info("here!")
        log.info(f"interval_seconds: {self.interval_seconds}")
        log.info(f"last_run_timestampe: {self.last_run_timestamp}")

        if not hasattr(self, "interval_seconds") or self.interval_seconds <= 0:
            log.info("25")
            return func(self, *args, **kwargs)

        if not hasattr(self, "last_run_timestamp") or not hasattr(self, "last_run_result"):
            log.info("29")
            raise AttributeError(f"{self.__class__.__name__} is missing 'last_run_timestamp' or 'last_run_result' attributes required by with_interval_check.")

        current_time = time.time()
        if (current_time - self.last_run_timestamp) < self.interval_seconds:
            log.info(f"Skipping {self.__class__.__name__} as it ran less than {self.interval_seconds}s ago. Returning previous result: {self.last_run_result}")
            return self.last_run_result

        result = func(self, *args, **kwargs)
        self.last_run_timestamp = current_time
        self.last_run_result = result

        log.info(f"last_run_timestamp: {self.last_run_timestamp}")

        return result
    return wrapper