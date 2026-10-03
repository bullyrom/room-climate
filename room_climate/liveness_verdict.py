"""Liveness verdict for a CO2 sensor."""

from __future__ import annotations

from enum import Enum


class LivenessVerdict(Enum):
    """Possible health states of the attached sensor."""

    ALIVE = "alive"
    DEGRADED = "degraded"
    DEAD = "dead"
    UNREACHABLE = "unreachable"
