"""Реестр протоколов."""
from .hybrid import HybridProtocol
from .bbm92 import BBM92Protocol, make_bbm92_plain, make_bbm92_chsh
from .e91_basic import E91BasicProtocol
from .e91_alt import E91AltProtocol

PROTOCOLS = {
    "hybrid": HybridProtocol,
    "bbm92_plain": make_bbm92_plain,
    "bbm92_chsh": make_bbm92_chsh,
    "e91_basic": E91BasicProtocol,
    "e91_alt": E91AltProtocol,
}

__all__ = [
    "PROTOCOLS", "HybridProtocol", "BBM92Protocol",
    "E91BasicProtocol", "E91AltProtocol",
    "make_bbm92_plain", "make_bbm92_chsh",
]