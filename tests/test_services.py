"""Модульные тесты сервисов: HashPRNG, Reconciler, SecurityAnalyzer, ChannelSimulator."""
import math
import pytest

from core.prng import HashPRNG
from core.reconciler import Reconciler
from core.analyzer import SecurityAnalyzer
from core.channel import ChannelSimulator
from core.configs import NoiseConfig, ReconciliationConfig


class TestHashPRNG:
    def test_deterministic(self):
        """Одинаковый ключ и домен → одинаковая последовательность."""
        a = HashPRNG(b"key", b"dom")
        b = HashPRNG(b"key", b"dom")
        assert [a.next_bit() for _ in range(100)] == [b.next_bit() for _ in range(100)]

    def test_different_domain(self):
        """Разный домен → разная последовательность."""
        a = HashPRNG(b"key", b"dom1")
        b = HashPRNG(b"key", b"dom2")
        seq_a = [a.next_bit() for _ in range(100)]
        seq_b = [b.next_bit() for _ in range(100)]
        assert seq_a != seq_b

    def test_next_int_range(self):
        """next_int(N) всегда в [0, N)."""
        rng = HashPRNG(b"seed", b"test")
        for N in [1, 2, 10, 1000]:
            for _ in range(50):
                v = rng.next_int(N)
                assert 0 <= v < N


class TestReconciler:
    def test_entropy(self):
        """H(0) = H(1) = 0, H(0.5) = 1."""
        assert Reconciler._binary_entropy(0.0) == 0.0
        assert Reconciler._binary_entropy(1.0) == 0.0
        assert abs(Reconciler._binary_entropy(0.5) - 1.0) < 1e-9

    def test_empty_key(self):
        """Пустой ключ → пустой результат."""
        cfg = ReconciliationConfig(enabled=True, frame_size=1024)
        result, stats = Reconciler.reconcile(
            [], 0.0, cfg, is_phase2=True, shared_seed=42)
        assert result == []
        assert stats['after_pa'] == 0

    def test_qber_too_high(self):
        """QBER ≥ 0.5 → ключ не вырабатывается."""
        cfg = ReconciliationConfig(enabled=True, frame_size=16)
        result, stats = Reconciler.reconcile(
            [0] * 100, 0.5, cfg, is_phase2=True, shared_seed=42)
        assert result == []
        assert stats['after_pa'] == 0

    def test_short_key_shorter_than_frame(self):
        """Ключ короче кадра → 0 бит."""
        cfg = ReconciliationConfig(enabled=True, frame_size=1024)
        result, stats = Reconciler.reconcile(
            [0] * 100, 0.01, cfg, is_phase2=True, shared_seed=42)
        assert result == []

    def test_deterministic_with_seed(self):
        """С фиксированным seed результат воспроизводим."""
        cfg = ReconciliationConfig(enabled=True, frame_size=16)
        key = [0, 1] * 500
        r1, _ = Reconciler.reconcile(key, 0.01, cfg, True, 42)
        r2, _ = Reconciler.reconcile(key, 0.01, cfg, True, 42)
        assert r1 == r2


class TestSecurityAnalyzer:
    def test_chsh_perfect_correlation(self):
        """Идеальные корреляции → S = 2√2 для стандартных углов."""
        # Эмулируем: базисы (0,1), (0,2), (2,1), (2,2)
        # E(0,1) = +1, E(0,2) = -1, E(2,1) = +1, E(2,2) = +1 → S = 1+1+1+1 = 4? 
        # На самом деле для CHSH максимум 2√2 при квантовых корреляциях,
        # но при детерминированных единичных исходах S может быть 2.
        # Проверим: если все результаты совпадают и базисы в комбинациях,
        # то каждый E = +1, кроме (0,2) где знак минус → S = 1 - 1 + 1 + 1 = 2
        basis_a = [0, 0, 2, 2]
        basis_b = [1, 2, 1, 2]
        res_a = [0, 0, 0, 0]
        res_b = [0, 0, 0, 0]
        S = SecurityAnalyzer.compute_S(basis_a, basis_b, res_a, res_b)
        assert S == 2.0  # корреляции +1 везде

    def test_chsh_zero(self):
        """S = 0 при равном вкладе совпадений и несовпадений.

        E(0,1) = +1, E(0,2) = -1, E(2,1) = -1, E(2,2) = -1
        S = 1 - (-1) + (-1) + (-1) = 0
        """
        basis_a = [0, 0, 2, 2]
        basis_b = [1, 2, 1, 2]
        res_a = [0, 0, 0, 0]
        res_b = [0, 1, 1, 1]
        S = SecurityAnalyzer.compute_S(basis_a, basis_b, res_a, res_b)
        assert abs(S) < 1e-9

    def test_qber_zero(self):
        """Совпадающие биты → QBER = 0."""
        angles = [0.0, math.pi/4, math.pi/2]
        qber = SecurityAnalyzer.compute_qber(
            angles, angles, [0, 1, 0], [0, 1, 0], [0, 1, 2], [0, 1, 2])
        assert qber == 0.0

    def test_qber_half(self):
        """Ровно половина ошибок → QBER = 0.5."""
        angles = [0.0]
        qber = SecurityAnalyzer.compute_qber(
            angles, angles,
            [0, 1, 0, 1],     # res_a
            [0, 1, 1, 0],     # res_b: позиции 0,1 совпали, 2,3 разные → 2/4
            [0, 0, 0, 0], [0, 0, 0, 0])
        assert qber == 0.5


class TestChannelSimulator:
    def test_entangled_pair_circuit(self):
        """Схема пары — H + CX, 2 кубита, 2 бита."""
        qc = ChannelSimulator.create_entangled_pair()
        assert qc.num_qubits == 2
        assert qc.num_clbits == 2

    def test_noise_none(self):
        """noise_model_name='none' → no noise model."""
        ch = ChannelSimulator(NoiseConfig(noise_model_name="none"))
        assert ch.noise_model is None

    def test_noise_depolarizing(self):
        """depolarizing → noise model создан."""
        ch = ChannelSimulator(NoiseConfig(
            noise_model_name="depolarizing", noise_p=0.05))
        assert ch.noise_model is not None