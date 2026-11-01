"""Safe, user-facing errors; never expose provider exception bodies."""


import asyncio


class RunStopped(Exception):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


class CorpusError(ValueError):
    pass


class TurnCancelled(asyncio.CancelledError):
    """Cancellation with a saved final result available for CLI presentation."""

    def __init__(self, result):
        super().__init__("user_cancelled")
        self.result = result
