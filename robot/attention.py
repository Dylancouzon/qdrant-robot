"""Select one visitor from source-specific face matches for conversation and following."""
import re
from dataclasses import dataclass

import numpy as np

from robot.people import THRESHOLD, name_in

TALK_TO = re.compile(r"^(?:please\s+)?talk to\s+([a-z]+(?:[ '-][a-z]+)*?)[.!?]*$", re.I)


@dataclass
class Candidate:
    vector: np.ndarray
    width: int
    box: tuple
    scores: list

    @property
    def names(self):
        return [name for name, _, score in self.scores if score >= THRESHOLD]

    @property
    def name(self):
        names = self.names
        return names[0] if len(names) == 1 else None


def handover(text):
    matched = TALK_TO.fullmatch(text.strip())
    return matched[1].title() if matched else None


def choose(candidates, active=None, text=""):
    """Return one face and an explanation when selection must wait. Names never verify faces."""
    target = handover(text)
    if target:
        matches = [c for c in candidates if c.name and c.name.casefold() == target.casefold()]
        return _unique(matches, f"I cannot uniquely recognize {target} in this view.")
    if introduced := name_in(text):
        unknown = [c for c in candidates if not c.names]
        if unknown:
            return _unique(unknown, "Please introduce yourselves one at a time.")
        matches = [c for c in candidates if c.name and c.name.casefold() == introduced.casefold()]
        if matches:
            return _unique(matches, "Please introduce yourselves one at a time.")
    if active is not None:
        matches = [c for c in candidates if float(c.vector @ active) >= THRESHOLD]
        if matches:
            return _unique(matches, "I cannot tell which person I am talking to. Please separate.")
        if candidates:
            return None, "Please introduce yourself, or say who I should talk to."
    if len(candidates) == 1:
        return _unique(candidates, "I cannot identify this face confidently.")
    known = [c for c in candidates if c.name]
    if len(known) == 1:
        return known[0], ""
    return None, "Please introduce yourself, or say who I should talk to." if candidates else ""


def _unique(candidates, error):
    if len(candidates) == 1 and len(candidates[0].names) <= 1:
        return candidates[0], ""
    return None, error
