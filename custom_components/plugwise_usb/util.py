"""Plugwise USB helper functions."""

from __future__ import annotations

import re

def validate_mac(mac: str) -> bool:
    """Validate the supplied string is in a ZigBee MAC address format."""
    try:
        if not re.match("^[A-F0-9]+$", mac):
            return False
    except TypeError:
        return False

    try:
        _ = int(mac, 16)
    except ValueError:
        return False
    return True