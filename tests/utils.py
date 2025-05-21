import time
import pytest
from django.db import transaction
from django.conf import settings
import psycopg2
import psycopg2.extensions


def wait_for_condition(condition_fn, timeout=2.0, interval=0.1):
    """
    Wait until condition_fn() returns True or timeout is reached.
    Raises TimeoutError if condition not met in time.
    """
    start = time.time()
    while True:
        if condition_fn():
            return
        if time.time() - start > timeout:
            raise TimeoutError("Condition not met in time")
        time.sleep(interval)



