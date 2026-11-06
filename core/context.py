"""Контекст сеанса: всё, что нужно протоколу."""
from dataclasses import dataclass

from .configs import ProtocolConfig, ReconciliationConfig
from .channel import ChannelSimulator
from .eve import EveModel
from .analyzer import SecurityAnalyzer
from .reconciler import Reconciler
from .stats import SessionStats


@dataclass
class SessionContext:
    """Всё, что протокол получает извне: конфиги и готовые сервисы."""
    protocol: ProtocolConfig
    recon: ReconciliationConfig
    channel: ChannelSimulator
    eve: EveModel
    analyzer: SecurityAnalyzer
    reconciler: Reconciler
    stats: SessionStats