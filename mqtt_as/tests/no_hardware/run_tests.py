# tests/no_hardware/run_tests.py
#
# Runs the EXISTING, unmodified tests/v3/test.py + tests/v3/target.py (and/or
# tests/v5 equivalents) as two ordinary CPython subprocesses talking to each
# other through the broker defined in stubs/mqtt_local.py (e.g.
# test.mosquitto.org), instead of one side running on a MicroPython device.
#
# How: test.py/target.py do `from mqtt_local import ...` and (v3 only)
# `from primitives import RingbufQueue` as plain top-level imports, and
# `from mqtt_as import ...`. We point PYTHONPATH at tests/no_hardware/stubs/,
# which provides real mqtt_local.py/primitives.py stand-ins plus a
# sitecustomize.py that stubs the MicroPython-only machine/network/
# micropython modules before mqtt_as is ever imported. Neither test.py nor
# target.py is modified in any way.
#
# Caveat: test.py/target.py use fixed, generic topic names ("control",
# "response", "foo topic", ...) with no namespacing. Shared public brokers,
# (e.g. test.mosquitto.org) unrelated traffic on those exact topic names could
# interfere. In practice this is rare, but if a run produces a confusing
# spurious failure, that's the first thing to suspect.
#
# Usage:
#   py -3 tests/no_hardware/run_tests.py v3
#   py -3 tests/no_hardware/run_tests.py v5
#   py -3 tests/no_hardware/run_tests.py both

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent  # .../mqtt_as/tests/no_hardware
MQTT_AS_DIR = HERE.parents[1]  # .../mqtt_as
REPO_ROOT = HERE.parents[2]  # .../micropython-mqtt (parent of the mqtt_as package)
STUBS_DIR = HERE / "stubs"

TARGET_STARTUP_GRACE = 3  # seconds to let target.py connect + subscribe before challenging it
TEST_TIMEOUT = 120  # seconds


def _subprocess_env():
    env = os.environ.copy()
    parts = [str(STUBS_DIR), str(REPO_ROOT)]
    if env.get("PYTHONPATH"):
        parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(parts)
    env["PYTHONIOENCODING"] = "utf-8"  # test.py/target.py print non-ASCII topics/messages
    return env


def _pump(proc, tag, sink=None):
    for line in proc.stdout:
        if sink is not None:
            sink.append(line)
        print(f"[{tag}] {line}", end="")


def _spawn(path, env):
    return subprocess.Popen(
        [sys.executable, "-u", str(path)],
        cwd=str(MQTT_AS_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def run_pair(version):
    target_path = MQTT_AS_DIR / "tests" / version / "target.py"
    test_path = MQTT_AS_DIR / "tests" / version / "test.py"
    env = _subprocess_env()

    print(f"\n=== {version}: starting target.py (loopback 'device') ===")
    target_proc = _spawn(target_path, env)
    target_thread = threading.Thread(
        target=_pump, args=(target_proc, f"{version}:target"), daemon=True
    )
    target_thread.start()

    time.sleep(TARGET_STARTUP_GRACE)

    print(f"=== {version}: starting test.py (challenger) ===\n")
    test_proc = _spawn(test_path, env)
    test_output = []
    test_thread = threading.Thread(
        target=_pump, args=(test_proc, f"{version}:test", test_output), daemon=True
    )
    test_thread.start()

    try:
        test_proc.wait(timeout=TEST_TIMEOUT)
    except subprocess.TimeoutExpired:
        print(f"\n[{version}] test.py timed out after {TEST_TIMEOUT}s")
        test_proc.kill()
    test_thread.join(timeout=5)

    target_proc.terminate()
    try:
        target_proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        target_proc.kill()
    target_thread.join(timeout=5)

    text = "".join(test_output)
    n_pass = text.count("PASS")
    n_fail = text.count("FAIL")
    ok = n_fail == 0 and n_pass > 0
    print(f"\n=== {version} summary: {n_pass} PASS marker(s), {n_fail} FAIL marker(s) ===")
    return ok


def main():
    args = sys.argv[1:] or ["v3"]
    versions = ["v3", "v5"] if args == ["both"] else args
    for v in versions:
        if v not in ("v3", "v5"):
            print(f"Unknown version {v!r}: expected v3, v5, or both")
            sys.exit(2)

    ok = True
    for v in versions:
        ok = run_pair(v) and ok

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
