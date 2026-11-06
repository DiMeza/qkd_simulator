"""Конфигурации сеанса и среды."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProtocolConfig:
    """Параметры сеанса протокола (фазы, пороги, размеры)."""
    total_pairs: int = 10000
    phase1_ratio: float = 0.4
    phase2_ratio: float = 0.6
    test_ratio: float = 0.1
    threshold_s: float = 2.0
    iteration: int = 0
    min_secret_bits: int = 20
    bob_mismatch_prob: float = 0.0
    force_continue: bool = False
    noise_p1: float = 0.0
    noise_p2: float = 0.0

    def validate(self) -> None:
        if not (0 < self.phase1_ratio < 1):
            raise ValueError(f"phase1_ratio должен быть в (0, 1), получено {self.phase1_ratio}")
        if not (0 < self.phase2_ratio < 1):
            raise ValueError(f"phase2_ratio должен быть в (0, 1), получено {self.phase2_ratio}")
        if abs(self.phase1_ratio + self.phase2_ratio - 1.0) > 1e-6:
            raise ValueError("phase1_ratio + phase2_ratio ≈ 1")
        if not (0 <= self.test_ratio <= 1):
            raise ValueError("test_ratio должен быть в [0, 1]")
        if not (0 <= self.bob_mismatch_prob <= 1):
            raise ValueError("bob_mismatch_prob должен быть в [0, 1]")
        if self.min_secret_bits < 0:
            raise ValueError("min_secret_bits должен быть >= 0")


@dataclass
class EveConfig:
    """Параметры атакующей стороны (Евы)."""
    eve_phase1: bool = False
    eve_phase2: bool = False
    eve_intercept_p1: float = 1.0
    eve_intercept_p2: float = 1.0
    eve_uses_k1_phase2: bool = False
    eve_k1_ber: float = 0.0


@dataclass
class NoiseConfig:
    """Параметры шумовой модели квантового канала (только на гейте cx)."""
    noise_model_name: str = "none"
    noise_p: float = 0.0
    T1: float = 50_000.0
    T2: float = 70_000.0
    gate_time_1q: float = 100.0
    gate_time_2q: float = 200.0


@dataclass
class ReconciliationConfig:
    """Параметры согласования и усиления приватности."""
    enabled: bool = True
    frame_size: int = 1024
    success_prob: float = 0.9
    efficiency: float = 1.1
    fixed_leak: Optional[int] = None
    pa_entropy_loss: float = 0.1
    enabled_p1: bool = True
    frame_size_p1: int = 16
    success_prob_p1: float = 0.9
    efficiency_p1: float = 1.1
    fixed_leak_p1: Optional[int] = None

@dataclass
class BBM92Config:
    """Специфичные параметры протокола BBM92 (plain или CHSH+DBA)."""
    p: float = 0.15                  # вероятность верификационного базиса
    k: float = 1.5                   # коэффициент для статистической погрешности de
    z_u: float = 5.0                 # порог на |E| в сигмах
    z_gamma: float = 5.0             # порог на |e - e_A|
    qber_threshold: float = 0.11     # порог QBER в plain-режиме
    eve_q: float = 0.0               # вероятность перехвата (intercept-resend)
    eve_basis: object = (0.0, 45.0)  # угол или кортеж углов Евы
    plain_mode: bool = False         # True → оригинальный BBM92 без CHSH/DBA
    seed: Optional[int] = None       # seed для numpy RNG

@dataclass
class E91Config:
    """Специфичные параметры протокола E91 (Экерт, 1991)."""
    num_pairs: int = 10000
    iteration: int = 0
    eve_enabled: bool = False
    eve_intercept: float = 1.0
    s_threshold: float = 2.0

@dataclass
class E91AltConfig:
    """Специфичные параметры альтернативного E91 (Φ⁺ + CHSH)."""
    num_pairs: int = 10000
    iteration: int = 0
    eve_enabled: bool = False
    eve_intercept: float = 1.0
    s_threshold: float = 2.0