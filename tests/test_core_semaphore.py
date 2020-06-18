import pytest


def test_invalid_argument():
    import asynckivy as ak

    with pytest.raises(TypeError):
        ak.Semaphore('hello')
    with pytest.raises(TypeError):
        ak.Semaphore(0.)
    with pytest.raises(ValueError):
        ak.Semaphore(-1)


def test_can_acquire_nowait():
    import asynckivy as ak

    s = ak.Semaphore(0)
    s._value = 0
    assert not s.can_acquire_nowait
    s._value = 1
    assert s.can_acquire_nowait
    s._value = 2
    assert s.can_acquire_nowait


def test_count():
    import asynckivy as ak

    s = ak.Semaphore(0)
    assert s.value == 0

    s = ak.Semaphore(2)
    assert s.value == 2
    s.acquire_nowait()
    assert s.value == 1
    s.acquire_nowait()
    assert s.value == 0
    s.release()
    assert s.value == 1
    s.release()
    assert s.value == 2


def test_count_async():
    import asynckivy as ak

    done = False
    async def task():
        s = ak.Semaphore(2)
        assert s.value == 2
        await s.acquire()
        assert s.value == 1
        await s.acquire()
        assert s.value == 0
        s.release()
        assert s.value == 1
        s.release()
        assert s.value == 2
        nonlocal done; done = True
    ak.start(task())
    assert done


@pytest.mark.parametrize('capacity', range(3))
def test__acquiring_too_much__releasing_too_much(capacity):
    import asynckivy as ak
    s = ak.Semaphore(capacity)

    with pytest.raises(ValueError):
        s.release()
    for __ in range(capacity):
        s.acquire_nowait()
    assert s.value == 0
    with pytest.raises(ak.WouldBlock):
        s.acquire_nowait()
    with pytest.raises(ak.WouldBlock):
        s.acquire_nowait()
    for __ in range(capacity):
        s.release()
    assert s.value == capacity
    with pytest.raises(ValueError):
        s.release()
    with pytest.raises(ValueError):
        s.release()


def test_nested_with():
    import asynckivy as ak
    s = ak.Semaphore(1)
    assert s.value == 1
    with s:
        assert s.value == 0
        with pytest.raises(ak.WouldBlock):
            with s:
                assert False
            assert False
        assert s.value == 0
    assert s.value == 1


def test_async_with():
    import asynckivy as ak
    s = ak.Semaphore(1)

    done = False
    async def task(s):
        assert s.value == 1
        async with s:
            assert s.value == 0
        assert s.value == 1
        nonlocal done; done = True
    ak.start(task(s))
    assert done


def test_nested_async_with():
    import asynckivy as ak
    s = ak.Semaphore(2)
    s.acquire_nowait()

    done = False
    async def task(s):
        assert s.value == 1
        async with s:
            assert s.value == 0
            async with s:
                assert s.value == 0
            assert s.value == 1
        assert s.value == 2
        nonlocal done; done = True
    ak.start(task(s))
    assert s.value == 0
    assert not done
    s.release()
    assert s.value == 2
    assert done


def test_recover_from_exception():
    import asynckivy as ak
    s = ak.Semaphore(1)

    with pytest.raises(IndexError):
        with s:
            assert s.value == 0
            raise IndexError
    assert s.value == 1


def test_recover_from_exception_async():
    import asynckivy as ak
    s = ak.Semaphore(1)

    async def task(s):
        async with s:
            assert s.value == 0
            raise IndexError

    with pytest.raises(IndexError):
        ak.start(task(s))
    assert s.value == 1


def test_order():
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
    assert s.value == 1
    s.release()
