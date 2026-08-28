"""Down Under agent package.

Importing this package is side-effect-free: the data models are exported
eagerly (they only need pydantic), while ``DownunderAgent`` is resolved lazily
on first access so that importing the package does not require nooa, an API key,
or network access.
"""

from .models import BusynessEntry, NightAngle, VenuePulse

__all__ = ["DownunderAgent", "VenuePulse", "NightAngle", "BusynessEntry"]


def __getattr__(name: str):
    if name == "DownunderAgent":
        from .downunder import DownunderAgent

        return DownunderAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
