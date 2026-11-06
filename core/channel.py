"""Симулятор квантового канала: пары, измерения, шум."""
import random
from typing import Optional, Tuple

from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error, thermal_relaxation_error

from .configs import NoiseConfig


class ChannelSimulator:
    """Симулятор квантового канала: запутанные пары, измерения, шум."""

    def __init__(self, noise: NoiseConfig):
        self.noise = noise
        self.noise_model = self.build_noise_model()
        
    def update_noise(self, noise_p: float):
        """Динамически менять уровень шума (для разделения по фазам)."""
        self.noise.noise_p = noise_p
        self.noise.noise_model_name = "depolarizing" if noise_p > 0 else "none"
        self.noise_model = self.build_noise_model()

    def build_noise_model(self) -> Optional[NoiseModel]:
        if self.noise.noise_model_name == "none":
            return None
        nm = NoiseModel()
        if self.noise.noise_model_name in ("thermal", "combined"):
            err_2q_thermal = thermal_relaxation_error(
                self.noise.T1, self.noise.T2, self.noise.gate_time_2q).tensor(
                thermal_relaxation_error(
                    self.noise.T1, self.noise.T2, self.noise.gate_time_2q))
        else:
            err_2q_thermal = None
        if self.noise.noise_model_name in ("depolarizing", "combined"):
            p_dep_2q = self.noise.noise_p / 0.75 if self.noise.noise_p > 0 else 0.0
            err_2q_dep = depolarizing_error(p_dep_2q, 2) if p_dep_2q > 0 else None
        else:
            err_2q_dep = None
        if err_2q_thermal is not None and err_2q_dep is not None:
            err_2q = err_2q_thermal.compose(err_2q_dep)
        elif err_2q_thermal is not None:
            err_2q = err_2q_thermal
        elif err_2q_dep is not None:
            err_2q = err_2q_dep
        else:
            err_2q = None
        if err_2q is not None:
            nm.add_all_qubit_quantum_error(err_2q, ['cx'])
        return nm

    @staticmethod
    def create_entangled_pair() -> QuantumCircuit:
        qr = QuantumRegister(2, 'q')
        cr = ClassicalRegister(2, 'c')
        circuit = QuantumCircuit(qr, cr)
        circuit.h(0)
        circuit.cx(0, 1)
        return circuit

    @staticmethod
    def measure_at_angle(qubit_idx: int, angle: float) -> QuantumCircuit:
        qr = QuantumRegister(1, 'q')
        cr = ClassicalRegister(1, 'c')
        circuit = QuantumCircuit(qr, cr)
        circuit.ry(angle, 0)
        circuit.measure(0, 0)
        return circuit

    def simulate(self, alice_angle: float, bob_angle: float,
                 eve_alice_angle: Optional[float] = None,
                 eve_bob_angle: Optional[float] = None) -> Tuple[int, int]:
        circuit = self.create_entangled_pair()
        if eve_alice_angle is not None and eve_bob_angle is not None:
            qc_eve_a = self.measure_at_angle(0, eve_alice_angle)
            qc_eve_b = self.measure_at_angle(1, eve_bob_angle)
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

        qc_alice = self.measure_at_angle(0, alice_angle)
        qc_bob = self.measure_at_angle(1, bob_angle)
        combined = circuit.compose(qc_alice, qubits=[0], clbits=[0])
        combined = combined.compose(qc_bob, qubits=[1], clbits=[1])
        simulator = AerSimulator(method='statevector',
                                 noise_model=self.noise_model)
        counts = simulator.run(combined, shots=1).result().get_counts()
        bitstring = list(counts.keys())[0]
        return int(bitstring[-1]), int(bitstring[0])