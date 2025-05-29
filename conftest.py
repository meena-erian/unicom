import pytest
import threading
from django.db import transaction

class InlineThread:
    """
    A fake Thread that just invokes its target immediately.
    """
    def __init__(self, target, args=(), kwargs=None, **_ignored):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        # run in-band instead of spawning a new thread
        self._target(*self._args, **self._kwargs)

@pytest.fixture(autouse=True)
def run_validations_inline(monkeypatch):
    """
    Everywhere in tests, swap out:
      - Django’s transaction.on_commit => call immediately
      - threading.Thread       => InlineThread
    This makes your Channel.validate() fire synchronously
    on save(), so there are no background threads holding DB connections.
    """
    # 1) Make on_commit callbacks run immediately
    monkeypatch.setattr(
        transaction,
        "on_commit",
        lambda func, using=None: func()
    )

    # 2) Replace Thread with an inline runner
    monkeypatch.setattr(
        threading,
        "Thread",
        InlineThread
    )
