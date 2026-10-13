import asyncio
import weakref


class KeyedLocks:
    """One asyncio.Lock per key, so concurrent requests for the same key run once.

    Locks are held weakly: once no coroutine references a lock it is dropped.
    """

    def __init__(self) -> None:
        self._locks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()

    def get(self, key: str) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock
