"""Errors shown to people. Messages are plain English and say what to do next (spec §9)."""


class UserError(Exception):
    """Something the person can fix. Shown as-is, with status 400 (or `status`)."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status
