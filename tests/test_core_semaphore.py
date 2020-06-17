import pytest


def test_zero_capacity():
    import asynckivy as ak
    s = ak.Semaphore(0)
    assert not s.can_acquire_nowait
    with pytest.raises(ak.WouldBlock):
        s.acquire_nowait()
    with pytest.raises(ValueError):
        s.release()

    state = None
    async def task(s):
        nonlocal state
        state = 'A'
        await s.acquire()
        state = 'B'
    coro = ak.start(task(s))
    assert state == 'A'
    with pytest.raises(StopIteration):
        coro.send(None)
    assert state == 'B'


def test_one_capacity():
    import asynckivy as ak
    s = ak.Semaphore(1)
    assert s.can_acquire_nowait
    s.acquire_nowait()
    assert s._value == 0
    assert not s.can_acquire_nowait
    with pytest.raises(ak.WouldBlock):
        s.acquire_nowait()
    s.release()
    assert s._value == 1
    with pytest.raises(ValueError):
        s.release()

    state = None
    async def task(s):
        nonlocal state
        state = 'A'
        async with s:
            state = 'B'
    ak.start(task(s))
    assert state == 'B'

    state = None
    s.acquire_nowait()
    ak.start(task(s))
    assert state == 'A'
    s.release()
    assert state == 'B'


def test_multiple_tasks():
    import asynckivy as ak
    s = ak.Semaphore(2)
    s.acquire_nowait()
    s.acquire_nowait()
    outcome = []
    async def task(s, outcome, prefix):
        outcome.append(prefix + '1')
        async with s:
            outcome.append(prefix + '2')
        outcome.append(prefix + '3')

    for prefix in 'ABC':
        ak.start(task(s, outcome, prefix))

    assert outcome == [
        'A1', 'B1', 'C1', 
    ]
    s.release()
    assert outcome == [
        'A1', 'B1', 'C1', 
        'A2', 'B2', 'C2', 
        'C3', 'B3', 'A3', 
    ]
    s.release()


def test_exception():
    import asynckivy as ak
    s = ak.Semaphore(1)
    s.acquire_nowait()

    async def task(s):
        async with s:
            assert not s.can_acquire_nowait
            raise IndexError

    ak.start(task(s))
    with pytest.raises(IndexError):
        s.release()
    assert s.can_acquire_nowait
