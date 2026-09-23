# tests/no_hardware/stubs/sitecustomize.py
#
# Auto-imported by CPython at interpreter startup whenever this directory is
# on PYTHONPATH (see run_tests.py). Installs just enough of MicroPython's
# machine/network/micropython modules, plus a couple of time/asyncio/socket
# shims, so the *unmodified* tests/v3 and tests/v5 test.py/target.py scripts
# (which normally only run on a MicroPython device) can run as plain CPython
# processes against a real broker instead.
#
# This must NOT import mqtt_local/primitives/mqtt_as itself - it only
# prepares sys.modules so that later, real imports of those succeed.

import sys
import time
import types
import uuid


def _install_micropython_stubs():
    machine_stub = types.ModuleType("machine")
    machine_stub.unique_id = lambda: uuid.uuid4().bytes[:6]
    sys.modules["machine"] = machine_stub

    micropython_stub = types.ModuleType("micropython")
    micropython_stub.const = lambda x: x
    sys.modules["micropython"] = micropython_stub

    class _FakeWLAN:
        def __init__(self, *_a, **_kw):
            pass

        def active(self, *_a, **_kw):
            pass

        def connect(self, *_a, **_kw):
            pass

        def disconnect(self):
            pass

        def isconnected(self):
            return True  # Assume the host machine is already online.

        def status(self, *_a, **_kw):
            return 0

        def config(self, *_a, **_kw):
            pass

    network_stub = types.ModuleType("network")
    network_stub.WLAN = _FakeWLAN
    network_stub.STA_IF = 0
    network_stub.STAT_CONNECTING = 1
    network_stub.STAT_IDLE = 1000
    sys.modules["network"] = network_stub

    if not hasattr(time, "ticks_ms"):
        _t0 = time.monotonic()
        time.ticks_ms = lambda: int((time.monotonic() - _t0) * 1000)
    if not hasattr(time, "ticks_diff"):
        time.ticks_diff = lambda a, b: a - b

    import gc

    if not hasattr(gc, "mem_free"):
        gc.mem_free = lambda: 0
    if not hasattr(gc, "mem_alloc"):
        gc.mem_alloc = lambda: 0

    import asyncio

    if not hasattr(asyncio, "sleep_ms"):

        async def _sleep_ms(ms):
            await asyncio.sleep(ms / 1000)

        asyncio.sleep_ms = _sleep_ms


def _patch_socket_for_micropython_api():
    """mqtt_as talks to raw sockets via MicroPython's read()/readinto()/
    write(), which return None on would-block rather than raising. Bridge
    that onto CPython's socket API (recv/recv_into/send raise
    BlockingIOError instead), and make connect() synchronous so we don't
    have to reproduce MicroPython's EINPROGRESS polling dance."""

    import socket

    if getattr(socket.socket, "_mqtt_as_harness_patched", False):
        return
    socket.socket._mqtt_as_harness_patched = True

    _orig_connect = socket.socket.connect

    def _connect(self, addr):
        was_blocking = self.getblocking()
        self.setblocking(True)
        try:
            _orig_connect(self, addr)
        finally:
            self.setblocking(was_blocking)

    def _readinto(self, buf, n):
        try:
            return self.recv_into(buf, n)
        except BlockingIOError:
            return None

    def _read(self, n):
        try:
            return self.recv(n)
        except BlockingIOError:
            return None

    def _write(self, data):
        try:
            return self.send(data)
        except BlockingIOError:
            return None

    socket.socket.connect = _connect
    socket.socket.readinto = _readinto
    socket.socket.read = _read
    socket.socket.write = _write


_install_micropython_stubs()
_patch_socket_for_micropython_api()

# mqtt_as grows its input buffer in place with bytearray.extend() while a
# memoryview onto it (self._mvbuf) is still live, in MQTT_base._as_read's
# buffer-growth path. MicroPython tolerates that; CPython's buffer-export
# protocol raises BufferError: "Existing exports of data: object cannot be
# re-sized". Pre-size the buffer past anything these test suites send
# (topics/messages up to 200 chars plus JSON/property wrapping) so the
# growth path is never exercised - purely a CPython-vs-MicroPython
# buffer-protocol difference, unrelated to whatever the tests are checking.
import mqtt_as  # noqa: E402

mqtt_as.IBUFSIZE = 2048
