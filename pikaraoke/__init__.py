"""Top-level package exports for PiKaraoke."""

from pikaraoke.version import __version__

PACKAGE = __package__
VERSION = __version__

__all__ = [
    "VERSION",
    "PACKAGE",
    "Karaoke",
    "get_platform",
]


def __getattr__(name: str):
    """Load heavy runtime exports lazily to keep package import lightweight."""
    if name == "Karaoke":
        from pikaraoke.karaoke import Karaoke

        return Karaoke
    if name == "get_platform":
        from pikaraoke.lib.get_platform import get_platform

        return get_platform
    raise AttributeError(f"module 'pikaraoke' has no attribute {name!r}")
