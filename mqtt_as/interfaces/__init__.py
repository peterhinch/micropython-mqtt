from uerrno import EINPROGRESS, ETIMEDOUT
import usocket
import uasyncio as asyncio


async def _g():
    pass


type_coro = type(_g())


# If a callback is passed, run it and return.
# If a coro is passed initiate it and return.
# coros are passed by name i.e. not using function call syntax.
def launch(func, tup_args):
    res = func(*tup_args)
    if isinstance(res, type_coro):
        res = asyncio.create_task(res)
    return res


class BaseInterface:
    def __init__(self, socket=None):
        # Legitimate errors while waiting on a socket. See uasyncio __init__.py open_connection().
        self.BUSY_ERRORS = [EINPROGRESS, ETIMEDOUT]
        self.socket = socket or usocket  # support for custom socket implementations
        self._subs = []
        self._state = None

    async def connect(self):
        """Serve connect request"""
        return await self._connect()

    async def _connect(self):
        """Hardware specific connect method"""
        # return True  # if connection is successful, otherwise False
        raise NotImplementedError()

    async def disconnect(self):
        """Serve disconnect request"""
        return await self._disconnect()

    async def _disconnect(self):
        """Hardware specific disconnect method"""
        # return True  # if connection is successful, otherwise False
        raise NotImplementedError()

    async def reconnect(self):
        """Serve reconnect request"""
        return await self._reconnect()

    async def _reconnect(self):
        """Hardware specific disconnect method"""
        if await self._disconnect():
            return await self._connect()
        return False

    def isconnected(self):
        if self._isconnected():
            if not self._state:
                # triggers if state is False or None
                self._state = True
                self._launch_subs(True)
        else:
            if self._state:
                # triggers if state is True
                self._state = False
                self._launch_subs(False)

    def _isconnected(self):
        raise NotImplementedError()

    def _launch_subs(self, state):
        for cb in self._subs:
            launch(cb, (state,))

    def subscribe(self, cb):
        self._subs.append(cb)
