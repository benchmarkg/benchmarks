"""What every gate module shares: the hard-fail exception and the repository root."""
from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class GateError(Exception):
    """A hard fail: the run commits nothing for this record (07 S8, "a red gate means no commit")."""

    def __init__(self, gate: str, message: str):
        super().__init__('%s: %s' % (gate, message))
        self.gate = gate
