# Messages on the serial console, only while USB is connected.
#
# Without the USB cable (battery tests, real use) nobody reads the console,
# and writing to it can stall the firmware while the USB driver waits for a
# host that is not there. log() prints only when USB power is present; use
# it for every message that can be written while the firmware is running.


def usb_present():
    try:
        import tinys3
        return tinys3.get_vbus_present()
    except Exception:
        return True             # not on a TinyS3: always print


def log(*args):
    if usb_present():
        print(*args)
