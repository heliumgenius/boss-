"""Re-export BossClient, Throttle, AntiDetect, and city resolution helpers."""
from ..constants import CITY_CODES
from .transport import BossClient
from .throttle import Throttle
from .antidetect import AntiDetect


def resolve_city(name: str) -> str:
    """Resolve city name to code, passthrough if already a code."""
    if name.isdigit() and len(name) >= 6:
        return name
    return CITY_CODES.get(name, CITY_CODES["全国"])


def list_cities() -> dict[str, str]:
    """Return all supported city name -> code mappings."""
    return dict(CITY_CODES)


__all__ = ["BossClient", "Throttle", "AntiDetect", "resolve_city", "list_cities"]
