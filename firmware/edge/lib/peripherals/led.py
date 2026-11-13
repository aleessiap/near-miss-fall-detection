# On-board RGB LED of the TinyS3.
#
# The LED shows the device state: blue = searching for the IMU,
# green = connected and running, orange = data recording mode, red = error.
# Three purple blinks signal that the IMU has been found.
# The colour is written only when it changes. With enabled=False (battery
# tests) the LED power is switched off, so it does not affect consumption;
# the purple blinks are shown anyway, since they last about 1.5 s per test,
# and so is the short green blink once a minute that shows a running test.

import uasyncio as asyncio

_COLOURS = {'red': 0, 'purple': 42, 'blue': 100, 'green': 170, 'orange': 240}


def _rgb(colour, brightness):
    from tinys3 import rgb_color_wheel
    r, g, b = rgb_color_wheel(_COLOURS[colour])
    return (int(r * brightness), int(g * brightness), int(b * brightness))


class TinyS3Led:
    def __init__(self, enabled=True):
        from tinys3 import set_pixel_power
        self.enabled = enabled
        self._current = None
        self.led = None
        if enabled:
            self._open()
            set_pixel_power(True)
        else:
            set_pixel_power(False)

    def _open(self):
        if self.led is None:
            import neopixel
            from machine import Pin
            from tinys3 import RGB_DATA
            self.led = neopixel.NeoPixel(Pin(RGB_DATA), 1)

    def set(self, colour, brightness=0.5):
        if not self.enabled or colour == self._current:
            return
        self.led[0] = _rgb(colour, brightness)
        self.led.write()
        self._current = colour

    async def blink(self, colour, times=3, on_ms=250, off_ms=250, brightness=0.5):
        """Blink a colour, then restore the previous state of the LED
        (its colour, or LED power off when the LED is disabled)."""
        from tinys3 import set_pixel_power
        self._open()
        set_pixel_power(True)
        for _ in range(times):
            self.led[0] = _rgb(colour, brightness)
            self.led.write()
            await asyncio.sleep_ms(on_ms)
            self.led[0] = (0, 0, 0)
            self.led.write()
            await asyncio.sleep_ms(off_ms)
        if self.enabled:
            previous, self._current = self._current, None
            if previous is not None:
                self.set(previous)
        else:
            set_pixel_power(False)

    def red(self):
        self.set('red')

    def blue(self):
        self.set('blue')

    def green(self):
        self.set('green')

    def orange(self):
        self.set('orange')
