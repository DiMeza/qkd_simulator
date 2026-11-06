"""Гибридный двухфазовый протокол QKD."""
import random
import numpy as np

from core.context import SessionContext
from core.contracts import SessionResult
from core.prng import HashPRNG


class HybridProtocol:
    """Гибридный протокол: E91+CHSH (фаза 1) → K1 → BBM92+ловушки (фаза 2)."""

    name = "hybrid"

    def __init__(self, ctx: SessionContext, verbose: bool = True):
        ctx.protocol.validate()
        self.ctx = ctx
        self.verbose = verbose
        p = ctx.protocol

        self.num_phase1 = int(p.total_pairs * p.phase1_ratio)
        self.num_phase2_total = int(p.total_pairs * p.phase2_ratio)
        self.num_test = int(self.num_phase2_total * p.test_ratio)
        self.num_phase2_key = self.num_phase2_total - self.num_test

        self.angles_p1_alice = [0.0, np.pi/4, np.pi/2]
        self.angles_p1_bob = [0.0, np.pi/4, 3*np.pi/4]
        self.angles_p2 = [0.0, np.pi/4]

        self.p1_alice_basis = []
        self.p1_bob_basis = []
        self.p1_alice_result = []
        self.p1_bob_result = []
        self.S = 0.0
        self.qber_phase1 = 0.0

        self.K1 = []
        self.K1_bob = []
        self.shared_key = []
        self.qber_phase2 = 0.0
        self.S_phase2 = 0.0

        self.trap_indices = []
        self.trap_alice_basis = []
        self.trap_bob_basis = []
        self.trap_alice_res = []
        self.trap_bob_res = []

    @staticmethod
    def _ik_to_bytes(ik):
        return ''.join(str(b) for b in ik).encode('utf-8')

    def phase1_evaluation(self) -> bool:
        p = self.ctx.protocol
        self.ctx.channel.update_noise(self.ctx.protocol.noise_p1)
        if self.verbose:
            print("\n" + "="*70)
            print("ФАЗА 1: ОЦЕНКА КАНАЛА (E91 + CHSH, 3 БАЗИСА)")
            print(f"Количество пар: {self.num_phase1}")
            print("="*70)

        self.p1_alice_basis = []
        self.p1_bob_basis = []
        self.p1_alice_result = []
        self.p1_bob_result = []

        for _ in range(self.num_phase1):
            a_basis = random.choice([0, 1, 2])
            b_basis = random.choice([0, 1, 2])
            a_angle = self.angles_p1_alice[a_basis]
            b_angle = self.angles_p1_bob[b_basis]

            if self.ctx.eve.should_attack_phase1():
                self.ctx.stats.eve_intercepted_p1 += 1
                e_a_angle, e_b_angle = self.ctx.eve.choose_angles_phase1(
                    self.angles_p1_alice, self.angles_p1_bob)
                a_res, b_res = self.ctx.channel.simulate(
                    a_angle, b_angle, e_a_angle, e_b_angle)
                if abs(a_angle - b_angle) < 1e-9:
                    self.ctx.stats.k1_bits_total += 1
                    if abs(a_angle - e_a_angle) < 1e-9:
                        self.ctx.stats.eve_knows_k1_bits += 1
            else:
                a_res, b_res = self.ctx.channel.simulate(a_angle, b_angle)
                if abs(a_angle - b_angle) < 1e-9:
                    self.ctx.stats.k1_bits_total += 1

            self.p1_alice_basis.append(a_basis)
            self.p1_bob_basis.append(b_basis)
            self.p1_alice_result.append(a_res)
            self.p1_bob_result.append(b_res)

        self.S = self.ctx.analyzer.compute_S(
            self.p1_alice_basis, self.p1_bob_basis,
            self.p1_alice_result, self.p1_bob_result)
        self.qber_phase1 = self.ctx.analyzer.compute_qber(
            self.angles_p1_alice, self.angles_p1_bob,
            self.p1_alice_result, self.p1_bob_result,
            self.p1_alice_basis, self.p1_bob_basis)

        if self.verbose:
            print(f"S = {self.S:.3f}  (порог: {p.threshold_s})")
            print(f"QBER1 = {self.qber_phase1*100:.2f}%")

        if abs(self.S) < p.threshold_s:
            if self.verbose:
                print("⚠ Канал скомпрометирован!")
            return p.force_continue
        return True

    def _extract_secret_bits(self):
        p = self.ctx.protocol
        alice_bits, bob_bits = [], []
        for i in range(self.num_phase1):
            a_angle = self.angles_p1_alice[self.p1_alice_basis[i]]
            b_angle = self.angles_p1_bob[self.p1_bob_basis[i]]
            if abs(a_angle - b_angle) < 1e-9:
                alice_bits.append(self.p1_alice_result[i])
                bob_bits.append(self.p1_bob_result[i])
        while len(alice_bits) < p.min_secret_bits:
            b = random.choice([0, 1])
            alice_bits.append(b)
            bob_bits.append(b)
        bob_bits = [1 - b if random.random() < p.bob_mismatch_prob else b
                    for b in bob_bits]
        return alice_bits, bob_bits

    def phase2_key_generation(self):
        self.ctx.channel.update_noise(self.ctx.protocol.noise_p2)
        p = self.ctx.protocol
        if self.verbose:
            print("\n" + "="*70)
            print("ФАЗА 2: ГЕНЕРАЦИЯ КЛЮЧА (BBM92 + E91-ловушки)")
            print("="*70)

        alice_ik = self._ik_to_bytes(self.K1)
        bob_ik = self._ik_to_bytes(self.K1_bob)
        if not alice_ik or not bob_ik:
            raise ValueError("Секрет K1 пуст!")

        rng_a = HashPRNG(alice_ik, b"basis")
        rng_b = HashPRNG(bob_ik, b"basis")
        bases_alice = [rng_a.next_bit() for _ in range(self.num_phase2_total)]
        bases_bob = [rng_b.next_bit() for _ in range(self.num_phase2_total)]

        bases_eve = self.ctx.eve.build_phase2_bases(
            self.K1, self.num_phase2_total)

        trap_domain = b"trap_pos|" + str(p.iteration).encode()
        trap_rng = HashPRNG(alice_ik, trap_domain)
        trap_indices, trap_set, u = [], set(), 0
        while len(trap_indices) < self.num_test:
            u += 1
            tmp = trap_rng.next_int(self.num_phase2_total)
            if tmp not in trap_set:
                trap_set.add(tmp)
                trap_indices.append(tmp)

        self.shared_key = []
        self.trap_indices = []
        self.trap_alice_basis = []
        self.trap_bob_basis = []
        self.trap_alice_res = []
        self.trap_bob_res = []
        total_errors = 0

        for i in range(self.num_phase2_total):
            if i in trap_set:
                a_basis = random.choice([0, 1, 2])
                b_basis = random.choice([0, 1, 2])
                a_angle = self.angles_p1_alice[a_basis]
                b_angle = self.angles_p1_bob[b_basis]
                if self.ctx.eve.should_attack_phase2():
                    self.ctx.stats.eve_intercepted_p2 += 1
                    e_a, e_b = self.ctx.eve.choose_angles_phase1(
                        self.angles_p1_alice, self.angles_p1_bob)
                    a_res, b_res = self.ctx.channel.simulate(
                        a_angle, b_angle, e_a, e_b)
                else:
                    a_res, b_res = self.ctx.channel.simulate(a_angle, b_angle)
                self.trap_indices.append(i)
                self.trap_alice_basis.append(a_basis)
                self.trap_bob_basis.append(b_basis)
                self.trap_alice_res.append(a_res)
                self.trap_bob_res.append(b_res)
            else:
                alice_basis = bases_alice[i]
                bob_basis = bases_bob[i]
                a_angle = self.angles_p2[alice_basis]
                b_angle = self.angles_p2[bob_basis]
                if self.ctx.eve.should_attack_phase2():
                    self.ctx.stats.eve_intercepted_p2 += 1
                    e_angle, eve_basis = self.ctx.eve.choose_angle_phase2(
                        self.angles_p2, bases_eve, i)
                    a_res, b_res = self.ctx.channel.simulate(
                        a_angle, b_angle, e_angle, e_angle)
                    eve_knows_bit = (eve_basis == alice_basis)
                else:
                    a_res, b_res = self.ctx.channel.simulate(a_angle, b_angle)
                    eve_knows_bit = False

                if a_res != b_res:
                    total_errors += 1
                else:
                    self.shared_key.append(a_res)
                    self.ctx.stats.raw_key_bits_total += 1
                    if eve_knows_bit:
                        self.ctx.stats.eve_knows_raw_key_bits += 1

        self.qber_phase2 = (total_errors / self.num_phase2_key
                            if self.num_phase2_key > 0 else 0.0)
        self.S_phase2 = self.ctx.analyzer.compute_S(
            self.trap_alice_basis, self.trap_bob_basis,
            self.trap_alice_res, self.trap_bob_res)

        shared_seed_p2 = hash((p.iteration, 'recon_p2')) & 0xFFFFFFFF
        final_key, stats2 = self.ctx.reconciler.reconcile(
            self.shared_key, self.qber_phase2,
            config=self.ctx.recon, is_phase2=True, shared_seed=shared_seed_p2)

        self.ctx.stats.key_length_before_recon = stats2['before']
        self.ctx.stats.key_length_after_recon = stats2['after_recon']
        self.ctx.stats.key_length_after_pa = stats2['after_pa']
        self.shared_key = final_key

        return len(final_key), self.qber_phase2, self.S_phase2

    def run(self) -> SessionResult:
        p = self.ctx.protocol
        res = SessionResult()

        safe = self.phase1_evaluation()
        res.phase1_success = safe
        res.S_phase1 = self.S
        res.qber_phase1 = self.qber_phase1
        res.eve_knows_k1_bits = self.ctx.stats.eve_knows_k1_bits
        res.k1_bits_total = self.ctx.stats.k1_bits_total
        res.eve_intercepted_p1 = self.ctx.stats.eve_intercepted_p1
        res.S1_ok = abs(self.S) >= p.threshold_s

        if not safe:
            return res

        self.K1, self.K1_bob = self._extract_secret_bits()
        res.secret_bits_used = len(self.K1)

        qber_k1 = (sum(1 for a, b in zip(self.K1, self.K1_bob) if a != b)
                   / len(self.K1)) if self.K1 else 0.0
        res.qber_k1 = qber_k1

        shared_seed_p1 = hash((p.iteration, 'recon_p1')) & 0xFFFFFFFF
        K1_final, stats1 = self.ctx.reconciler.reconcile(
            self.K1, qber_k1, config=self.ctx.recon,
            is_phase2=False, shared_seed=shared_seed_p1)

        self.ctx.stats.key_length_before_recon_p1 = stats1['before']
        self.ctx.stats.key_length_after_recon_p1 = stats1['after_recon']
        res.key_before_recon_p1 = stats1['before']
        res.key_after_recon_p1 = stats1['after_recon']

        if self.ctx.eve.config.eve_uses_k1_phase2:
            assumed = int(len(self.K1) * self.ctx.eve.config.eve_intercept_p1
                          * (1 - self.ctx.eve.config.eve_k1_ber))
            res.eve_knows_k1_bits = max(res.eve_knows_k1_bits, assumed)

        self.K1 = K1_final
        self.K1_bob = K1_final
        res.secret_bits_used = len(self.K1)

        if not self.K1:
            return res

        res.phase2_ran = True
        key_len, qber2, S2 = self.phase2_key_generation()
        res.key_length = key_len
        res.qber_phase2 = qber2
        res.S_phase2 = S2
        res.key_length_before_recon = self.ctx.stats.key_length_before_recon
        res.key_length_after_recon = self.ctx.stats.key_length_after_recon
        res.key_length_after_pa = self.ctx.stats.key_length_after_pa
        res.eve_knows_raw_key_bits = self.ctx.stats.eve_knows_raw_key_bits
        res.raw_key_bits_total = self.ctx.stats.raw_key_bits_total
        res.eve_intercepted_p2 = self.ctx.stats.eve_intercepted_p2

        res.S2_ok = abs(self.S_phase2) >= p.threshold_s
        res.key_ok = self.ctx.stats.key_length_after_pa > 0
        res.success = res.S1_ok and res.S2_ok and res.key_ok
        return res