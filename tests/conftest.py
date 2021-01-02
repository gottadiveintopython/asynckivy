from functools import partial
import pytest

from kivy.tests.fixtures import kivy_clock


def _sleep(t, clock):
    from time import time, sleep
    tick = clock.tick
    deadline = time() + t
    while time() < deadline:
        sleep(.01)
        tick()


@pytest.fixture
def kivy_sleep(kivy_clock):
    return partial(_sleep, clock=kivy_clock)
