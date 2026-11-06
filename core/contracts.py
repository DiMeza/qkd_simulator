"""Контракт протокола и результат сеанса."""
from dataclasses import dataclass, asdict
from typing import Protocol


@dataclass
class SessionResult:
    """Результат одного сеанса протокола (все поля — как в старом run())."""
    phase1_success: bool = False
    phase2_ran: bool = False
    S_phase1: float = 0.0
    qber_phase1: float = 0.0
    qber_k1: float = 0.0
    key_length: int = 0
    qber_phase2: float = 0.0
    S_phase2: float = 0.0
    secret_bits_used: int = 0
    key_before_recon_p1: int = 0
    key_after_recon_p1: int = 0
    key_length_before_recon: int = 0
    key_length_after_recon: int = 0
    key_length_after_pa: int = 0
    eve_knows_k1_bits: int = 0
    k1_bits_total: int = 0
    eve_knows_raw_key_bits: int = 0
    raw_key_bits_total: int = 0
    eve_intercepted_p1: int = 0
    eve_intercepted_p2: int = 0
    S1_ok: bool = False
    S2_ok: bool = False
    key_ok: bool = False
    success: bool = False

    def to_dict(self) -> dict:
        """Вернуть результат в виде словаря (совместимо со старым API)."""
        return asdict(self)


class QKDProtocol(Protocol):
    """Контракт протокола: имя + метод run()."""
    name: str

    def run(self) -> SessionResult:
        """Выполнить один сеанс и вернуть результат."""
        ...