import json
import os
import sys

from pynput.keyboard import Key, KeyCode


def _config_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


CONFIG_PATH = os.path.join(_config_dir(), "autoclicker_config.json")


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_config(cfg: dict) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except OSError as exc:
        print(f"[autoclicker] could not save config: {exc}")


def key_from_label(label: str, vk=None):
    if isinstance(label, str):
        name = label.strip().lower()
        if hasattr(Key, name):
            return getattr(Key, name)
    if vk is not None:
        char = None
        if isinstance(label, str) and len(label) == 1:
            char = label.lower()
        try:
            return KeyCode.from_vk(int(vk), char=char)
        except Exception:
            pass
    return Key.f6
