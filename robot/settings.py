"""Live recognition settings, validated and saved in the shared directory."""
import json
import math
import os
import tempfile
import threading
from pathlib import Path

from robot.config import SHARED

DEFAULTS = dict(match=.822, guess_band=.05, window_s=6.0, window_gap_s=1.0,
                window_floor=.70, duplicate=.95, views_cap=24,
                ask_delay_s=3., ask_blank_s=4., ask_max=3)
RANGES = dict(match=(.6, .99), guess_band=(0., .2), window_s=(0., 30.),
              window_gap_s=(.2, 5.), window_floor=(0., .99), duplicate=(.8, 1.),
              views_cap=(3, 64), ask_delay_s=(1., 20.), ask_blank_s=(1., 30.),
              ask_max=(0, 10))


class Settings:
    def __init__(self, path: Path):
        self.path, self.writing = path, threading.Lock()
        self.values = dict(DEFAULTS)
        if path.exists():
            try:  # a bad file must not stop the robot at the booth: defaults, and say so
                data = json.loads(path.read_text())
                if not isinstance(data, dict):
                    raise ValueError("Settings must be an object")
                for name, value in data.items():
                    self.validate(name, value)
                self.values.update(data)
            except (OSError, ValueError) as error:
                print(f"settings: ignoring {path}: {error}", flush=True)

    @staticmethod
    def validate(name, value):
        if not isinstance(name, str) or name not in RANGES:
            raise ValueError("Unknown setting")
        low, high = RANGES[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or \
                not math.isfinite(value) or not low <= value <= high or \
                (name in {"views_cap", "ask_max"} and int(value) != value):
            raise ValueError(f"{name} must be between {low} and {high}")

    def __getattr__(self, name):
        try:
            return self.__dict__["values"][name]
        except KeyError:
            raise AttributeError(name) from None

    def snapshot(self):
        return dict(self.values)

    def change(self, data):
        if not isinstance(data, dict):
            raise ValueError("Settings must be an object")
        with self.writing:  # the page server is threaded; readers see one dict swap
            if set(data) == {"reset"} and data["reset"] is True:
                updated = dict(DEFAULTS)
            elif set(data) == {"name", "value"}:
                self.validate(data["name"], data["value"])
                updated = {**self.values, data["name"]: data["value"]}
                updated["views_cap"] = int(updated["views_cap"])
            else:
                raise ValueError("Supply name and value, or reset: true")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(
                dir=self.path.parent, prefix="settings-", suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as stream:
                    json.dump(updated, stream)
                os.replace(temporary, self.path)
            finally:
                Path(temporary).unlink(missing_ok=True)
            self.values = updated


settings = Settings(SHARED / "settings.json")


def _selftest():
    for name, value in DEFAULTS.items():
        Settings.validate(name, value)
        try:
            Settings.validate(name, RANGES[name][1] + 1)
        except ValueError:
            pass
        else:
            raise AssertionError(name)
    with tempfile.TemporaryDirectory() as root:
        path = Path(root) / "settings.json"
        saved = Settings(path)
        saved.change({"name": "match", "value": .9})
        assert Settings(path).snapshot() == saved.snapshot()
        saved.change({"reset": True})
        assert Settings(path).snapshot() == DEFAULTS
        path.write_text('{"match": 5}')
        assert Settings(path).snapshot() == DEFAULTS, "a bad file falls back to defaults"


if __name__ == "__main__":
    _selftest()
