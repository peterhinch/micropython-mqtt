from . import BaseInterface


class Linux(BaseInterface):
    async def _disconnect(self):
        return True  # just to prevent errors we'll pretend to be disconnected.

    def _isconnected(self):
        return True  # always connected.

    async def _connect(self):
        return True  # always connected or can't do anything about it
