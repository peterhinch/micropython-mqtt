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
        """Serve connect request. Triggers callbacks if state changes"""
        if await self._connect():
            self._change_state(True)
            return True
        return False

    async def _connect(self):
        """Hardware specific connect method"""
        # return True  # if connection is successful, otherwise False
        raise NotImplementedError()

    async def disconnect(self):
        """Serve disconnect request. Triggers callbacks if state changes"""
        if await self._disconnect():
            self._change_state(False)
            return True
        return False

    async def _disconnect(self):
        """Hardware specific disconnect method"""
        # return True  # if disconnect is successful, otherwise False
        raise NotImplementedError()

    async def reconnect(self):
        """Serve reconnect request"""
        return await self._reconnect()

    async def _reconnect(self):
        """Hardware specific reconnect method"""
        if await self._disconnect():
            return await self._connect()
        return False

    def isconnected(self):
        """"Checks if the interface is connected. Triggers callbacks if state changes"""
        st = self._isconnected()
        self._change_state(st)
        return st

    def _isconnected(self):
        """Hardware specific isconnected method"""
        raise NotImplementedError()

    def _change_state(self, state):
        """Private method executing all callbacks or creating asyncio tasks"""
        trig = False
        if state:
            if not self._state:
                # triggers if state is False or None
                self._state = True
                trig = True
        else:
            if self._state:
                # triggers if state is True
                self._state = False
                trig = True
        if trig:
            for cb in self._subs:
                launch(cb, (state,))

    def subscribe(self, cb):
        """Subscribe to interface connection state changes"""
        self._subs.append(cb)
