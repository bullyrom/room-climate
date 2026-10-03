"""Outcome of a Wi-Fi credential provisioning attempt."""

from __future__ import annotations

from enum import Enum


class ProvisionOutcome(Enum):
    """Result of trying to store Wi-Fi credentials on the device."""

    SAVED = "saved"
    NOT_SAVED = "not_saved"
    NO_CONFIRMATION = "no_confirmation"
