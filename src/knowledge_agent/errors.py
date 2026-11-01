"""Safe, user-facing errors; never expose provider exception bodies."""


class RunStopped(Exception):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


class CorpusError(ValueError):
    pass
