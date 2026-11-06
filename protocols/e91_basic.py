"""E91 (Экерт, 1991) — оригинальная версия.

Особенности:
- Синглетное состояние |ψ-⟩ = (|01⟩ - |10⟩)/√2 (антикорреляции).
- Углы Алисы [0, π/4, π/2], Боба [π/4, π/2, 3π/4] (сдвиг на π/4).
- Измерение через RZ(angle) → RY(-π/2) → measure (проекция в XZ-плоскости).
- QBER считается по совпадениям (для синглета ошибка = равные биты).
- Eve — упрощённая intercept-resend со схлопыванием состояния.
- Одна фаза, S по парам (0,0), (0,2), (2,0), (2,2).
"""
import random
import numpy as np
from typing import List, Optional, Tuple

from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error

from core.configs import E91Config, NoiseConfig, ReconciliationConfig
from core.reconciler import Reconciler


class E91BasicProtocol:
    """E91 (Экерт, 1991) с шумом, частичным перехватом Евы, recon+PA."""

    def __init__(self,
                 config: E91Config,
                 noise: NoiseConfig,
                 recon: ReconciliationConfig,
                 verbose: bool = True):
        self.cfg = config
        self.noise = noise
        self.recon = recon
        self.verbose = verbose

        self.noise_model = self._build_noise_model()

        self.alice_angles = [0.0, np.pi / 4, np.pi / 2]
        self.bob_angles = [np.pi / 4, np.pi / 2, 3 * np.pi / 4]

        # состояние сеанса
        self.alice_basis: List[int] = []
        self.bob_basis: List[int] = []
        self.alice_result: List[int] = []
        self.bob_result: List[int] = []
        self._eve_knowledge_for_pair: List[bool] = []
        self.eve_intercepted_count = 0
        self.eve_knows_sifted = 0

        self.S = 0.0
        self.qber = 0.0
        self.key_length = 0
        self.sifted_key: List[int] = []

        self.key_length_before_recon = 0
        self.key_length_after_recon = 0
        self.key_length_after_pa = 0

    # ---------- Шум ----------
    def _build_noise_model(self) -> Optional[NoiseModel]:
        if self.noise.noise_p <= 0:
            return None
        nm = NoiseModel()
        p_dep = self.noise.noise_p / 0.75
        err_2q = depolarizing_error(p_dep, 2)
        nm.add_all_qubit_quantum_error(err_2q, ['cx'])
        return nm

    # ---------- Квантовые схемы ----------
    @staticmethod
    def _create_singlet_state() -> QuantumCircuit:
        qr = QuantumRegister(2, 'q')
        cr = ClassicalRegister(2, 'c')
        circuit = QuantumCircuit(qr, cr)
        circuit.h(0)
        circuit.cx(0, 1)
        circuit.z(0)
        circuit.x(1)
        return circuit

    @staticmethod
    def _measure_at_angle(qubit_idx: int, angle: float) -> QuantumCircuit:
        qr = QuantumRegister(1, 'q')
        cr = ClassicalRegister(1, 'c')
        circuit = QuantumCircuit(qr, cr)
        circuit.rz(angle, 0)
        circuit.ry(-np.pi / 2, 0)
        circuit.measure(0, 0)
        return circuit

    def _simulate_measurement(self, alice_angle: float,
                              bob_angle: float) -> Tuple[int, int]:
        circuit = self._create_singlet_state()
        qc_alice = self._measure_at_angle(0, alice_angle)
        qc_bob = self._measure_at_angle(1, bob_angle)
        combined = circuit.compose(qc_alice, qubits=[0], clbits=[0])
        combined = combined.compose(qc_bob, qubits=[1], clbits=[1])
        simulator = AerSimulator(method='statevector',
                                 noise_model=self.noise_model)
        counts = simulator.run(combined, shots=1).result().get_counts()
        bitstring = list(counts.keys())[0]
        return int(bitstring[-1]), int(bitstring[0])

    def _simulate_with_eve(self, alice_angle: float, bob_angle: float,
                           eve_alice_angle: float,
                           eve_bob_angle: float) -> Tuple[int, int]:
        circuit = self._create_singlet_state()
        qc_eve_a = self._measure_at_angle(0, eve_alice_angle)
        qc_eve_b = self._measure_at_angle(1, eve_bob_angle)
        combined = circuit.compose(qc_eve_a, qubits=[0], clbits=[0])
        combined = combined.compose(qc_eve_b, qubits=[1], clbits=[1])
        simulator = AerSimulator(method='statevector',
                                 noise_model=self.noise_model)
        counts = simulator.run(combined, shots=1).result().get_counts()
        bitstring = list(counts.keys())[0]
        eve_res_a = int(bitstring[-1])
        eve_res_b = int(bitstring[0])

        if abs(alice_angle - eve_alice_angle) < 1e-9:
            alice_res = eve_res_a
        else:
            alice_res = random.choice([0, 1])
        if abs(bob_angle - eve_bob_angle) < 1e-9:
            bob_res = eve_res_b
        else:
            bob_res = random.choice([0, 1])
        return alice_res, bob_res

    # ---------- Анализ ----------
    def _compute_S(self) -> None:
        combos = [(0, 0), (0, 2), (2, 0), (2, 2)]
        correlations = {c: 0 for c in combos}
        counts = {c: 0 for c in combos}
        for i in range(self.cfg.num_pairs):
            ab = (self.alice_basis[i], self.bob_basis[i])
            if ab in correlations:
                counts[ab] += 1
                e = 1 if self.alice_result[i] == self.bob_result[i] else -1
                correlations[ab] += e
        E = {ab: correlations[ab] / counts[ab] if counts[ab] > 0 else 0.0
             for ab in correlations}
        self.S = E[(0, 0)] - E[(0, 2)] + E[(2, 0)] + E[(2, 2)]

    def _sift_key(self) -> None:
        matching = 0
        errors = 0
        self.sifted_key = []
        self.eve_knows_sifted = 0

        for i in range(self.cfg.num_pairs):
            a_angle = self.alice_angles[self.alice_basis[i]]
            b_angle = self.bob_angles[self.bob_basis[i]]
            if abs(a_angle - b_angle) < 1e-9:
                matching += 1
                self.sifted_key.append(self.alice_result[i])
                # singlet → антикорреляция: ошибка = равные биты
                if self.alice_result[i] == self.bob_result[i]:
                    errors += 1
                if self._eve_knowledge_for_pair[i]:
                    self.eve_knows_sifted += 1

        self.key_length = matching
        self.qber = errors / matching if matching > 0 else 0.0

    # ---------- Запуск ----------
    def run(self) -> dict:
        self.alice_basis = []
        self.bob_basis = []
        self.alice_result = []
        self.bob_result = []
        self._eve_knowledge_for_pair = []
        self.eve_intercepted_count = 0

        if self.verbose:
            print("=" * 70)
            print("ПРОТОКОЛ E91 (ЭКЕРТ, 1991)")
            print("=" * 70)

        for _ in range(self.cfg.num_pairs):
            a_basis = random.choice([0, 1, 2])
            b_basis = random.choice([0, 1, 2])
            a_angle = self.alice_angles[a_basis]
            b_angle = self.bob_angles[b_basis]

            eve_attacks = (self.cfg.eve_enabled and
                           random.random() < self.cfg.eve_intercept)

            if eve_attacks:
                self.eve_intercepted_count += 1
                e_a_angle = random.choice(self.alice_angles)
                e_b_angle = random.choice(self.bob_angles)
                a_res, b_res = self._simulate_with_eve(
                    a_angle, b_angle, e_a_angle, e_b_angle)
                eve_knows_a = (abs(a_angle - e_a_angle) < 1e-9)
            else:
                a_res, b_res = self._simulate_measurement(a_angle, b_angle)
                eve_knows_a = False

            self.alice_basis.append(a_basis)
            self.bob_basis.append(b_basis)
            self.alice_result.append(a_res)
            self.bob_result.append(b_res)
            self._eve_knowledge_for_pair.append(eve_knows_a)

        self._compute_S()
        self._sift_key()

        # Согласование + PA (переиспользуем Reconciler из core)
        shared_seed = hash((self.cfg.iteration, 'recon')) & 0xFFFFFFFF
        final_key, stats = Reconciler.reconcile(
            self.sifted_key, self.qber,
            config=self.recon, is_phase2=True, shared_seed=shared_seed)

        self.key_length_before_recon = stats['before']
        self.key_length_after_recon = stats['after_recon']
        self.key_length_after_pa = stats['after_pa']

        S_ok = abs(self.S) > self.cfg.s_threshold
        key_ok = self.key_length_after_pa > 0

        if self.verbose:
            print(f"S = {self.S:.3f}  (порог: ±{self.cfg.s_threshold})")
            print(f"QBER = {self.qber * 100:.2f}%")
            print(f"Ключ после PA: {self.key_length_after_pa} бит")

        return {
            'S': self.S,
            'qber': self.qber,
            'key_before_recon': self.key_length_before_recon,
            'key_after_recon': self.key_length_after_recon,
            'key_after_pa': self.key_length_after_pa,
            'eve_intercepted': self.eve_intercepted_count,
            'eve_knows_key_bits': self.eve_knows_sifted,
            'sifted_bits_total': self.key_length,
            'S_ok': S_ok,
            'key_ok': key_ok,
        }

    def run_trials(self, trials: int = 10) -> dict:
        """Серия прогонов + усреднение."""
        raw = [self.run() for _ in range(trials)]

        scalar_keys = ['S', 'qber', 'key_before_recon', 'key_after_recon',
                       'key_after_pa', 'eve_intercepted',
                       'eve_knows_key_bits', 'sifted_bits_total']
        mean, std = {}, {}
        for key in scalar_keys:
            vals = np.array([r[key] for r in raw], dtype=float)
            mean[key] = float(np.mean(vals))
            std[key] = float(np.std(vals)) if len(vals) > 1 else 0.0

        S_ok_count = sum(int(r['S_ok']) for r in raw)
        key_ok_count = sum(int(r['key_ok']) for r in raw)
        success_count = sum(1 for r in raw if r['S_ok'] and r['key_ok'])

        return {
            'trials': trials,
            'mean': mean,
            'std': std,
            'S_ok_count': S_ok_count,
            'key_ok_count': key_ok_count,
            'success_count': success_count,
            'raw': raw,
        }