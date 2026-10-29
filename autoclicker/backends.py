import atexit
import sys


class _Backend:
    name = "none"

    def click(self):
        raise NotImplementedError

    def close(self):
        pass


class _PyDirectInputBackend(_Backend):
    name = "pydirectinput (Windows)"

    def __init__(self):
        import pydirectinput
        pydirectinput.PAUSE = 0
        self._pdi = pydirectinput

    def click(self):
        self._pdi.click(button=self._pdi.LEFT, _pause=False)


class _EvdevBackend(_Backend):
    name = "evdev uinput (Linux)"

    def __init__(self):
        from evdev import UInput, ecodes as e

        self._e = e
        caps = {
            e.EV_KEY: [e.BTN_LEFT],
            e.EV_REL: [e.REL_X, e.REL_Y],
        }
        self._ui = UInput(
            caps, name="autoclicker-virtual-mouse", version=0x1
        )

    def click(self):
        e = self._e
        self._ui.write(e.EV_KEY, e.BTN_LEFT, 1)
        self._ui.syn()
        self._ui.write(e.EV_KEY, e.BTN_LEFT, 0)
        self._ui.syn()

    def close(self):
        try:
            self._ui.close()
        except Exception:
            pass


def make_backend():
    if sys.platform.startswith("win"):
        try:
            return _PyDirectInputBackend()
        except Exception as exc:
            print(f"[autoclicker] pydirectinput unavailable: {exc}")
            return None
    if sys.platform.startswith("linux"):
        try:
            return _EvdevBackend()
        except Exception as exc:
            print(f"[autoclicker] evdev/uinput unavailable: {exc}\n"
                  "  Ensure the 'evdev' package is installed and you have "
                  "access to /dev/uinput (see README / run instructions).")
            return None
    print(f"[autoclicker] unsupported platform: {sys.platform}")
    return None


BACKEND = make_backend()
if BACKEND is not None:
    atexit.register(BACKEND.close)


def click():
    if BACKEND is not None:
        BACKEND.click()
