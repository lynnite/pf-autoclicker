import signal
import time
import tkinter as tk
from tkinter import ttk, messagebox

from pynput.keyboard import Listener as KeyboardListener, Key, KeyCode

from .backends import BACKEND
from .config import load_config, save_config, key_from_label
from .engine import AutoClicker


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("AutoClicker")
        self.root.resizable(False, False)

        self.clicker = AutoClicker()

        cfg = load_config()

        self.mode = tk.StringVar(value=cfg.get("mode", "toggle"))
        self.rpm_text = tk.StringVar(value=str(cfg.get("rpm", 600)))
        self.on_off = tk.BooleanVar(value=False)
        self.keybind_str = tk.StringVar(value=cfg.get("keybind_label", "F6"))
        self.jitter_pct = tk.DoubleVar(value=float(cfg.get("jitter_pct", 15.0)))
        self._bound_key = key_from_label(
            cfg.get("keybind_label", "F6"), cfg.get("keybind_vk")
        )
        self._key_held = False
        self._last_key_press = 0.0
        self._repeat_guard = 0.04
        self._listener = None
        self._capturing = False
        self._save_after_id = None
        self._config_ready = False

        self._build_ui()
        self._start_keyboard_listener()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.clicker.set_jitter(self.jitter_pct.get() / 100.0)
        self._on_rpm_change()
        self._config_ready = True

    def _build_ui(self):
        pad = {"padx": 8, "pady": 6}
        frm = ttk.Frame(self.root, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")

        self.toggle_btn = ttk.Button(
            frm, text="OFF", width=14, command=self._toggle_on_off
        )
        self.toggle_btn.grid(row=0, column=0, columnspan=2, sticky="ew", **pad)

        ttk.Label(frm, text="RPM (clicks/min):").grid(
            row=1, column=0, sticky="w", **pad
        )
        self.rpm_entry = ttk.Entry(frm, textvariable=self.rpm_text, width=12)
        self.rpm_entry.grid(row=1, column=1, sticky="ew", **pad)
        self.rpm_text.trace_add("write", self._on_rpm_change)

        self.speed_lbl = ttk.Label(frm, text="", foreground="#555")
        self.speed_lbl.grid(row=2, column=0, columnspan=2, sticky="w",
                            padx=8, pady=(0, 6))
        self._update_speed_label()

        ttk.Label(frm, text="Variation:").grid(
            row=3, column=0, sticky="w", **pad
        )
        jit_frm = ttk.Frame(frm)
        jit_frm.grid(row=3, column=1, sticky="ew", **pad)
        self.jitter_scale = ttk.Scale(
            jit_frm, from_=0, to=100, variable=self.jitter_pct,
            orient="horizontal", command=self._on_jitter_change
        )
        self.jitter_scale.pack(side="left", fill="x", expand=True)
        self.jitter_lbl = ttk.Label(jit_frm, text="15%", width=5)
        self.jitter_lbl.pack(side="left")
        self.clicker.set_jitter(0.15)

        ttk.Label(frm, text="Keybind:").grid(row=4, column=0, sticky="w", **pad)
        self.bind_btn = ttk.Button(
            frm, textvariable=self.keybind_str, width=12,
            command=self._start_capture
        )
        self.bind_btn.grid(row=4, column=1, sticky="ew", **pad)

        ttk.Label(frm, text="Mode:").grid(row=5, column=0, sticky="w", **pad)
        mode_frm = ttk.Frame(frm)
        mode_frm.grid(row=5, column=1, sticky="ew", **pad)
        ttk.Radiobutton(
            mode_frm, text="Toggle", value="toggle", variable=self.mode,
            command=self._on_mode_change
        ).pack(anchor="w")
        ttk.Radiobutton(
            mode_frm, text="Hold", value="hold", variable=self.mode,
            command=self._on_mode_change
        ).pack(anchor="w")

        self.status_lbl = ttk.Label(frm, text="Status: idle", foreground="#333")
        self.status_lbl.grid(row=6, column=0, columnspan=2, sticky="w", **pad)

        if BACKEND is not None:
            back_txt = f"Backend: {BACKEND.name}"
            back_fg = "#2a7d2a"
        else:
            back_txt = "Backend: UNAVAILABLE (see README)"
            back_fg = "#b00020"
        ttk.Label(frm, text=back_txt, foreground=back_fg).grid(
            row=7, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 6)
        )

    def _on_rpm_change(self, *_):
        text = self.rpm_text.get().strip()
        try:
            val = float(text)
            if val <= 0:
                raise ValueError
        except ValueError:
            self.speed_lbl.config(text="Enter a positive number.")
            return
        self.clicker.set_rpm(val)
        interval = self.clicker.interval()
        jit = self.clicker.get_jitter()
        if jit > 0:
            spread = f"  ±{jit * 100:.0f}%"
        else:
            spread = ""
        self.speed_lbl.config(
            text=(f"~{val / 60.0:.2f} clicks/sec  "
                  f"(every {interval * 1000:.1f} ms{spread})")
        )
        self._schedule_save()

    def _update_speed_label(self):
        self._on_rpm_change()

    def _on_jitter_change(self, *_):
        pct = self.jitter_pct.get()
        self.jitter_lbl.config(text=f"{pct:.0f}%")
        self.clicker.set_jitter(pct / 100.0)
        self._update_speed_label()
        self._schedule_save()

    def _toggle_on_off(self):
        self.on_off.set(not self.on_off.get())
        if self.on_off.get():
            if BACKEND is None:
                messagebox.showerror(
                    "No click backend",
                    "No click backend is available on this system.\n\n"
                    "On Linux install 'evdev' and grant access to /dev/uinput;\n"
                    "on Windows install 'pydirectinput'."
                )
                self.on_off.set(False)
                return
            try:
                val = float(self.rpm_text.get().strip())
                if val <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid RPM",
                                     "Please enter a positive RPM value.")
                self.on_off.set(False)
                return
            self.clicker.set_rpm(val)
            self.clicker.start()
            self.toggle_btn.config(text="ON")
            self._set_status("armed - waiting for key")
        else:
            self.clicker.stop()
            self.toggle_btn.config(text="OFF")
            self._set_status("idle")

    def _set_status(self, text):
        self.status_lbl.config(text=f"Status: {text}")

    def _on_mode_change(self):
        self.clicker.set_clicking(False)
        self._set_status("armed - waiting for key" if self.on_off.get()
                         else "idle")
        self._schedule_save()

    def _start_capture(self):
        self._capturing = True
        self.bind_btn.config(text="Press a key...")
        self._set_status("press any key to bind")

    def _key_vk(self):
        k = self._bound_key
        if isinstance(k, KeyCode):
            return k.vk
        if isinstance(k, Key):
            val = getattr(k, "value", None)
            if isinstance(val, KeyCode):
                return val.vk
        return None

    def _gather_config(self) -> dict:
        try:
            rpm = float(self.rpm_text.get().strip())
        except ValueError:
            rpm = 600
        return {
            "rpm": rpm,
            "jitter_pct": float(self.jitter_pct.get()),
            "mode": self.mode.get(),
            "keybind_label": self.keybind_str.get(),
            "keybind_vk": self._key_vk(),
        }

    def _save_current_config(self):
        if not getattr(self, "_config_ready", False):
            return
        save_config(self._gather_config())

    def _schedule_save(self):
        if not getattr(self, "_config_ready", False):
            return
        if self._save_after_id is not None:
            try:
                self.root.after_cancel(self._save_after_id)
            except Exception:
                pass
        self._save_after_id = self.root.after(600, self._save_current_config)

    def _display_key(self, key):
        if isinstance(key, Key):
            return key.name.upper()
        if isinstance(key, KeyCode):
            if key.char:
                return key.char.upper()
            return f"VK{key.vk}"
        return str(key).upper()

    def _start_keyboard_listener(self):
        self._listener = KeyboardListener(
            on_press=self._on_key_press, on_release=self._on_key_release
        )
        self._listener.daemon = True
        self._listener.start()

    def _keys_equal(self, a, b):
        if a == b:
            return True
        if isinstance(a, Key) and isinstance(b, Key):
            return a == b
        if isinstance(a, KeyCode) and isinstance(b, KeyCode):
            return a.vk == b.vk and a.char == b.char
        return False

    def _on_key_press(self, key):
        if self._capturing:
            self._capturing = False
            self._bound_key = key
            self.keybind_str.set(self._display_key(key))
            self._set_status("armed - waiting for key"
                             if self.on_off.get() else "idle")
            self._save_current_config()
            return

        if not self._keys_equal(key, self._bound_key):
            return

        if not self.on_off.get():
            return

        now = time.monotonic()
        if now - self._last_key_press < self._repeat_guard:
            self._key_held = True
            return
        self._last_key_press = now
        self._key_held = True

        if self.mode.get() == "toggle":
            new_state = self.clicker.toggle_clicking()
            self._set_status("clicking" if new_state else "armed - paused")
        else:
            self.clicker.set_clicking(True)
            self._set_status("clicking (held)")

    def _on_key_release(self, key):
        if not self._keys_equal(key, self._bound_key):
            return
        self._key_held = False
        if self.mode.get() == "hold" and self.on_off.get():
            self.clicker.set_clicking(False)
            self._set_status("armed - waiting for key")

    def _on_close(self):
        try:
            self._save_current_config()
        except Exception:
            pass
        try:
            if self._listener:
                self._listener.stop()
        except Exception:
            pass
        self.clicker.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass
    app = App(root)

    def _handle_signal(signum, frame):
        try:
            app._save_current_config()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass

    for _sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(_sig, _handle_signal)
        except (ValueError, OSError):
            pass

    root.mainloop()
