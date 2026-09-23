# tests/no_hardware/stubs/primitives.py
#
# Minimal stand-in for peterhinch/micropython-async's `primitives` package,
# providing just the RingbufQueue API that tests/v3/test.py and
# tests/v5/test.py import unmodified: put_nowait/get_nowait/qsize/get.
# Not a general-purpose reimplementation - only what those two files use.

import asyncio


class RingbufQueue:
    def __init__(self, size):
        self._buf = [None] * size
        self._size = size
        self._wi = 0
        self._ri = 0
        self._full = False
        self._evt = asyncio.Event()

    def qsize(self):
        if self._full:
            return self._size
        return (self._wi - self._ri) % self._size

    def put_nowait(self, *v):
        item = v[0] if len(v) == 1 else v
        self._buf[self._wi] = item
        if self._full:
            self._ri = (self._ri + 1) % self._size
        self._wi = (self._wi + 1) % self._size
        self._full = self._wi == self._ri
        self._evt.set()

    def get_nowait(self):
        if self.qsize() == 0:
            raise IndexError("Queue is empty")
        item = self._buf[self._ri]
        self._ri = (self._ri + 1) % self._size
        self._full = False
        if self.qsize() == 0:
            self._evt.clear()
        return item

    async def get(self):
        while self.qsize() == 0:
            self._evt.clear()
            await self._evt.wait()
        return self.get_nowait()

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self.get()
