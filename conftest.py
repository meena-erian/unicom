import pytest
import threading
from django.db import transaction

class InlineThread:
    """
    A fake Thread that just invokes its target immediately.
    """
    def __init__(self, target, *args, **kwargs):
        self._target = target

    def start(self):
        # run in-band instead of spawning a new thread
        self._target()

@pytest.fixture(autouse=True)
def run_validations_inline(monkeypatch):
    """
    Everywhere in tests, swap out:
      - Django’s transaction.on_commit => call immediately
      - threading.Thread       => InlineThread
    This makes your Bot.validate() fire synchronously
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
