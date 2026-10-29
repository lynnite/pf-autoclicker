import random
import threading
import time

from .backends import click


class AutoClicker:
    def __init__(self):
        self._running = False
        self._clicking = False
        self._thread = None
        self._lock = threading.Lock()
        self.rpm = 600
        self.jitter = 0.15
        self._rng = random.Random()

    def set_rpm(self, rpm: float):
        with self._lock:
            self.rpm = max(1.0, float(rpm))

    def get_rpm(self) -> float:
        with self._lock:
            return self.rpm

    def set_jitter(self, fraction: float):
        with self._lock:
            self.jitter = min(1.0, max(0.0, float(fraction)))

    def get_jitter(self) -> float:
        with self._lock:
            return self.jitter

    def interval(self) -> float:
        rpm = self.get_rpm()
        return 60.0 / rpm if rpm > 0 else 60.0

    def jittered_interval(self) -> float:
        base = self.interval()
        frac = self.get_jitter()
        if frac <= 0.0 or base <= 0.0:
            return base
        factor = 1.0 + self._rng.uniform(-frac, frac)
        return max(base * 0.05, base * factor)

    def start(self):
        if self._running:
            return
        self._running = True
        self._clicking = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self.set_clicking(False)
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        self._thread = None

    def set_clicking(self, clicking: bool):
        with self._lock:
            self._clicking = clicking

    def is_clicking(self) -> bool:
        with self._lock:
            return self._clicking

    def toggle_clicking(self) -> bool:
        with self._lock:
            self._clicking = not self._clicking
            return self._clicking

    def is_running(self) -> bool:
        return self._running

    def _run(self):
        while self._running:
            if self.is_clicking():
                try:
                    click()
                except Exception as exc:
                    if type(exc).__name__ == "FailSafeException":
                        self.set_clicking(False)
                        break

                delay = self.jittered_interval()
                if delay > 0:
                    time.sleep(delay)
                else:
                    time.sleep(0.0001)
            else:
                time.sleep(0.005)
