import gc
gc.threshold((gc.mem_free() + gc.mem_alloc()) // 4)
import uos
from flashbdev import bdev

try:
    if bdev:
        uos.mount(bdev, '/')
except OSError:
    import inisetup
    inisetup.setup()

try:
    uos.stat('/main.py')
except OSError:
    with open("/main.py", "w") as f:
        f.write("""\
import mqtt
""")

gc.collect()
