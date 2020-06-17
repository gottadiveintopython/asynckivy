'''Everything in this module doesn't depend on Kivy.'''

__all__ = ('start', 'or_', 'and_', 'Event', 'Semaphore', )

import types
import typing
from inspect import getcoroutinestate, CORO_CLOSED
from collections import deque

from ._exceptions import WouldBlock

def start(coro):
    '''Starts a asynckivy-flavored coroutine.
    Returns the argument itself.
    '''
    def step_coro(*args, **kwargs):
        try:
            if getcoroutinestate(coro) != CORO_CLOSED:
                coro.send((args, kwargs, ))(step_coro)
        except StopIteration:
            pass

    try:
        coro.send(None)(step_coro)
    except StopIteration:
        pass

    return coro


class Task:
    '''(internal)'''
    __slots__ = ('coro', 'done', 'result', 'done_callback')
    def __init__(self, coro, *, done_callback=None):
        self.coro = coro
        self.done = False
        self.result = None
        self.done_callback = done_callback
    async def _run(self):
        self.result = await self.coro
        self.done = True
        if self.done_callback is not None:
            self.done_callback()


@types.coroutine
def gather(coros:typing.Iterable[typing.Coroutine], *, n:int=None) -> typing.Sequence[Task]:
    '''(internal)'''
    coros = tuple(coros)
    n_coros_left = n if n is not None else len(coros)

    def step_coro(*args, **kwargs):
        nonlocal n_coros_left; n_coros_left -= 1
    def done_callback():
        nonlocal n_coros_left
        n_coros_left -= 1
        if n_coros_left == 0:
            step_coro()
    tasks = tuple(Task(coro, done_callback=done_callback) for coro in coros)
    for task in tasks:
        start(task._run())

    if n_coros_left <= 0:
        return tasks

    def callback(step_coro_):
        nonlocal step_coro
        step_coro = step_coro_
    yield callback

    return tasks


async def or_(*coros):
    return await gather(coros, n=1)


async def and_(*coros):
    return await gather(coros)


class Event:
    '''Equivalent of 'trio.Event'
    '''
    __slots__ = ('_flag', '_step_coro_list')

    def __init__(self):
        self._flag = False
        self._step_coro_list = []

    def is_set(self):
        return self._flag

    def set(self):
        if self._flag:
            return
        self._flag = True
        step_coro_list = self._step_coro_list
        self._step_coro_list = []
        for step_coro in step_coro_list:
            step_coro()

    def clear(self):
        self._flag = False

    @types.coroutine
    def wait(self):
        yield (lambda step_coro: step_coro()) if self._flag \
            else self._step_coro_list.append


@types.coroutine
def _get_step_coro():
    '''(internal)'''
    return (yield lambda step_coro: step_coro(step_coro))[0][0]


class Semaphore:
    '''Equivalent of `trio.Semaphore` '''

    __slots__ = ('_value', '_max_value', '_coros', )

    def __init__(self, max:int):
        if not isinstance(max, int):
            raise TypeError("max must be an int")
        self._value = max
        self._max_value = max
        self._coros = deque()

    def __repr__(self):
        return "<asynckivy.Semaphore({}, max_value={}) at {:#x}>".format(
            self._value, self._max_value, id(self)
        )

    @property
    def value(self):
        return self._value

    @property
    def max_value(self):
        return self._max_value

    @property
    def can_acquire_nowait(self) -> bool:
        return self._value > 0

    def acquire_nowait(self):
        if self._value > 0:
            self._value -= 1
        else:
            raise WouldBlock

    @types.coroutine
    def acquire(self):
        if self._value > 0:
            self._value -= 1
            yield (lambda step_coro: step_coro())
        else:
            yield self._coros.append

    def release(self):
        if self._value == self._max_value:
            raise ValueError("semaphore released too many times")
        coros = self._coros
        if coros:
            coros.popleft()()
        else:
            self._value += 1

    async def __aenter__(self):
        await self.acquire()

    async def __aexit__(self, exc_type, exc, tb):
        self.release()
