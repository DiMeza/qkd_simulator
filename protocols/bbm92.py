"""BBM92: plain (оригинальный) и CHSH+DBA (модифицированный).

Протокол самодостаточен: использует только общие конфиги NoiseConfig и
ReconciliationConfig, а физику, Eve и CHSH-валидацию реализует локально
(из-за batched sampling и специфичной модели перехвата).
"""
import numpy as np

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error

from core.configs import BBM92Config, NoiseConfig, ReconciliationConfig


class BBM92Protocol:
    """BBM92 с режимами plain (без CHSH/DBA) и CHSH+DBA."""

    TRUST_ANGLES = (0.0, 45.0)
    VERIFY_ANGLES = (22.5, 67.5)

    def __init__(self,
                 config: BBM92Config,
                 noise: NoiseConfig,
                 recon: ReconciliationConfig,
                 verbose: bool = True):
        self.cfg = config
        self.noise = noise
        self.recon = recon
        self.verbose = verbose

        self.rng = np.random.default_rng(config.seed)
        self.rng_recon = np.random.default_rng(
            None if config.seed is None else config.seed + 1000)

        if noise.noise_p > 0:
            nm = NoiseModel()
            p_dep = noise.noise_p / 0.75
            err = depolarizing_error(p_dep, 2)
            nm.add_all_qubit_quantum_error(err, ['cx'])
            self.simulator = AerSimulator(noise_model=nm)
        else:
            self.simulator = AerSimulator()

    # ------------------------------------------------------------------
    # Квантовая схема
    # ------------------------------------------------------------------
    def _bell_circuit(self, theta_A_deg, theta_B_deg):
        qr = QuantumRegister(2, 'q')
        cr = ClassicalRegister(2, 'c')
        qc = QuantumCircuit(qr, cr)
        qc.h(0)
        qc.cx(0, 1)
        qc.ry(-2 * np.radians(theta_A_deg), 0)
        qc.ry(-2 * np.radians(theta_B_deg), 1)
        qc.measure(0, 0)
        qc.measure(1, 1)
        return qc

    def _sample_clean(self, theta_A, theta_B, n):
        if n == 0:
            return np.array([], dtype=int), np.array([], dtype=int)
        qc = self._bell_circuit(theta_A, theta_B)
        counts = self.simulator.run(qc, shots=n).result().get_counts()
        a_list, b_list = [], []
        for bs, c in counts.items():
            a_list.extend([int(bs[-1])] * c)
            b_list.extend([int(bs[0])] * c)
        return np.array(a_list), np.array(b_list)

    def _sample_eve(self, theta_A, theta_B, n):
        """Intercept-resend + шум при пересылке."""
        if n == 0:
            return (np.array([], dtype=int), np.array([], dtype=int),
                    np.array([], dtype=int))
        lam = self.noise.noise_p

        if isinstance(self.cfg.eve_basis, (list, tuple, np.ndarray)):
            theta_e = self.rng.choice(np.asarray(self.cfg.eve_basis), size=n)
        else:
            theta_e = np.full(n, float(self.cfg.eve_basis))

        e_bits = self.rng.integers(0, 2, size=n)

        p_A = (np.cos(np.radians(theta_A - theta_e))**2
               - (2 * lam / 3) * np.cos(np.radians(2 * (theta_A - theta_e))))
        p_B = (np.cos(np.radians(theta_B - theta_e))**2
               - (2 * lam / 3) * np.cos(np.radians(2 * (theta_B - theta_e))))

        a = np.where(self.rng.random(n) < p_A, e_bits, 1 - e_bits)
        b = np.where(self.rng.random(n) < p_B, e_bits, 1 - e_bits)
        return a, b, e_bits

    def _sample_pairs(self, theta_A, theta_B, n):
        if n == 0:
            return (np.array([], dtype=int), np.array([], dtype=int),
                    np.array([], dtype=bool), np.array([], dtype=int))

        if self.cfg.eve_q <= 0:
            a, b = self._sample_clean(theta_A, theta_B, n)
            return a, b, np.zeros(n, dtype=bool), -np.ones(n, dtype=int)

        n_int = self.rng.binomial(n, self.cfg.eve_q)
        n_clean = n - n_int

        a_clean, b_clean = self._sample_clean(theta_A, theta_B, n_clean)
        a_int, b_int, e_int = self._sample_eve(theta_A, theta_B, n_int)

        a = np.concatenate([a_clean, a_int])
        b = np.concatenate([b_clean, b_int])
        int_mask = np.concatenate([
            np.zeros(n_clean, dtype=bool), np.ones(n_int, dtype=bool)])
        e_bits = np.concatenate([-np.ones(n_clean, dtype=int), e_int])
        return a, b, int_mask, e_bits

    # ------------------------------------------------------------------
    @staticmethod
    def _correlation(a, b):
        n = len(a)
        if n == 0:
            return 0.0
        same = int(np.sum(a == b))
        return (2 * same - n) / n

    def _chsh_value(self, a, b, bases_A, bases_B, angles_A, angles_B, signs):
        E = {}
        for a_ang in angles_A:
            for b_ang in angles_B:
                m = (bases_A == a_ang) & (bases_B == b_ang)
                E[(a_ang, b_ang)] = (self._correlation(a[m], b[m])
                                     if m.sum() > 0 else 0.0)
        combos = [(angles_A[0], angles_B[0]),
                  (angles_A[0], angles_B[1]),
                  (angles_A[1], angles_B[0]),
                  (angles_A[1], angles_B[1])]
        return sum(s * E[c] for c, s in zip(combos, signs))

    # ------------------------------------------------------------------
    # Согласование + PA
    # ------------------------------------------------------------------
    @staticmethod
    def _binary_entropy(p):
        if p <= 0 or p >= 1:
            return 0.0
        return float(-p * np.log2(p) - (1 - p) * np.log2(1 - p))

    def _reconcile_and_amplify(self, raw_key_len, qber):
        before = int(raw_key_len)
        stats = {'before': before, 'after_recon': before, 'after_pa': before,
                 'frames_total': 0, 'frames_success': 0, 'leaked': 0}

        if not self.recon.enabled or before == 0:
            after_pa = int(before * (1 - self.recon.pa_entropy_loss))
            stats['after_pa'] = after_pa
            return before, after_pa, stats

        if qber >= 0.5:
            stats['after_recon'] = 0
            stats['after_pa'] = 0
            return 0, 0, stats

        L = min(self.recon.frame_size, before)
        n_frames = before // L
        stats['frames_total'] = n_frames

        h_qber = self._binary_entropy(qber)
        leak_per_frame = int(self.recon.efficiency * L * h_qber)

        kept_flags = self.rng_recon.random(n_frames) < self.recon.success_prob
        n_ok = int(kept_flags.sum())
        stats['frames_success'] = n_ok

        kept_bits = n_ok * L
        leaked = n_ok * leak_per_frame
        after_recon = max(0, kept_bits - leaked)
        after_pa = max(0, int(after_recon * (1 - self.recon.pa_entropy_loss)))

        stats['after_recon'] = after_recon
        stats['after_pa'] = after_pa
        stats['leaked'] = leaked
        return after_recon, after_pa, stats

    # ------------------------------------------------------------------
    # Plain BBM92 (без CHSH/DBA)
    # ------------------------------------------------------------------
    def _run_plain(self, N):
        bases_A = self.rng.choice([0.0, 45.0], N)
        bases_B = self.rng.choice([0.0, 45.0], N)

        out_A = np.zeros(N, dtype=int)
        out_B = np.zeros(N, dtype=int)
        int_mask = np.zeros(N, dtype=bool)
        e_bits = -np.ones(N, dtype=int)

        for bA, bB in set(zip(bases_A, bases_B)):
            mask = (bases_A == bA) & (bases_B == bB)
            n = int(mask.sum())
            if n > 0:
                a, b, im, eb = self._sample_pairs(float(bA), float(bB), n)
                out_A[mask] = a
                out_B[mask] = b
                int_mask[mask] = im
                e_bits[mask] = eb

        key_mask = (bases_A == bases_B)
        N_key = int(key_mask.sum())

        if N_key > 0:
            errs = int(np.sum(out_A[key_mask] != out_B[key_mask]))
            e = errs / N_key
            de = self.cfg.k * np.sqrt(e * (1 - e) / N_key)
        else:
            e, de = 0.0, 0.0

        eve_intercepted = int(int_mask.sum())
        key_int = int_mask & key_mask
        if key_int.sum() > 0:
            eve_knows = int(np.sum((e_bits == out_A) & key_int))
        else:
            eve_knows = 0

        e_corr = max(e + de, 0.0)

        abort, reasons = False, []
        if e - de > self.cfg.qber_threshold:
            abort = True
            reasons.append(f"e-de>{self.cfg.qber_threshold:.2f}")

        key_recon, key_pa, recon_stats = self._reconcile_and_amplify(N_key, e_corr)

        return {
            'N': N, 'mode': 'plain',
            'counts': {'qber': N_key, 'SA': 0, 'SB': 0, 'det': 0, 'key': N_key},
            'e': e, 'de': de,
            'S_A': None, 'S_B': None,
            'e_A': e, 'e_B': e, 'de_A': de, 'de_B': de,
            'E_corr': 0.0, 'u': 0.0, 'gamma': 0.0,
            'N1_A': 0, 'N1_B': 0,
            'e_corr': e_corr, 'e_priv': e,
            'abort': abort, 'reasons': reasons,
            'key_rate': N_key / N if N > 0 else 0.0,
            'key_bits_raw': N_key,
            'key_bits_after_recon': key_recon,
            'key_bits_after_pa': key_pa,
            'recon_stats': recon_stats,
            'key_rate_final': key_pa / N if N > 0 else 0.0,
            'eve_intercepted': eve_intercepted,
            'eve_knows_key_bits': eve_knows,
            'sifted_bits_total': N_key,
        }

    # ------------------------------------------------------------------
    # CHSH + DBA
    # ------------------------------------------------------------------
    def _run_chsh(self, N):
        p = self.cfg.p
        mode_A = self.rng.random(N) < p
        mode_B = self.rng.random(N) < p
        bases_A = np.where(mode_A,
                           self.rng.choice(self.VERIFY_ANGLES, N),
                           self.rng.choice(self.TRUST_ANGLES, N))
        bases_B = np.where(mode_B,
                           self.rng.choice(self.VERIFY_ANGLES, N),
                           self.rng.choice(self.TRUST_ANGLES, N))

        out_A = np.zeros(N, dtype=int)
        out_B = np.zeros(N, dtype=int)
        int_mask = np.zeros(N, dtype=bool)
        e_bits = -np.ones(N, dtype=int)

        for mA, mB, bA, bB in set(zip(mode_A, mode_B, bases_A, bases_B)):
            mask = (mode_A == mA) & (mode_B == mB) & \
                   (bases_A == bA) & (bases_B == bB)
            n = int(mask.sum())
            if n > 0:
                a, b, im, eb = self._sample_pairs(float(bA), float(bB), n)
                out_A[mask] = a
                out_B[mask] = b
                int_mask[mask] = im
                e_bits[mask] = eb

        qber_mask = (mode_A & mode_B) & (bases_A == bases_B)
        SA_mask   = (~mode_A) & mode_B
        SB_mask   = mode_A & (~mode_B)
        det_mask  = ((mode_A & mode_B) | (~mode_A & ~mode_B)) & (bases_A != bases_B)
        key_mask  = (~mode_A) & (~mode_B) & (bases_A == bases_B)

        N_qber = int(qber_mask.sum())
        if N_qber > 0:
            errs = int(np.sum(out_A[qber_mask] != out_B[qber_mask]))
            e = errs / N_qber
            de = self.cfg.k * np.sqrt(e * (1 - e) / N_qber)
        else:
            e, de = 0.0, 0.0

        N_SA = int(SA_mask.sum())
        if N_SA > 0:
            S_A = self._chsh_value(out_A, out_B, bases_A, bases_B,
                                   (0.0, 45.0), (22.5, 67.5),
                                   (+1, -1, +1, +1))
            e_A = 0.5 * (1 - S_A / (2 * np.sqrt(2)))
            de_A = 1.0 / np.sqrt(2 * N_SA)
        else:
            S_A, e_A, de_A = None, 0.0, 0.0

        N_SB = int(SB_mask.sum())
        if N_SB > 0:
            S_B = self._chsh_value(out_A, out_B, bases_A, bases_B,
                                   (22.5, 67.5), (0.0, 45.0),
                                   (+1, +1, -1, +1))
            e_B = 0.5 * (1 - S_B / (2 * np.sqrt(2)))
            de_B = 1.0 / np.sqrt(2 * N_SB)
        else:
            S_B, e_B, de_B = None, 0.0, 0.0

        N_det = int(det_mask.sum())
        if N_det > 0:
            E_corr = self._correlation(out_A[det_mask], out_B[det_mask])
            N1_A = int(out_A[det_mask].sum())
            N1_B = int(out_B[det_mask].sum())
            sigma_E = 1.0 / np.sqrt(N_det)
        else:
            E_corr, N1_A, N1_B, sigma_E = 0.0, 0, 0, 0.0

        u = self.cfg.z_u * sigma_E
        gamma = max(self.cfg.z_gamma * np.sqrt(de**2 + de_A**2 + de_B**2), 0.01)

        abort, reasons = False, []
        if S_A is not None and S_A <= 2.0:
            abort = True; reasons.append("S_A<=2")
        if S_B is not None and S_B <= 2.0:
            abort = True; reasons.append("S_B<=2")
        if N_det > 0:
            thr = 0.5 * N_det + 5.0 * 0.5 * np.sqrt(N_det)
            if N1_A > thr: abort = True; reasons.append("N1_A")
            if N1_B > thr: abort = True; reasons.append("N1_B")
        if abs(E_corr) > u:
            abort = True; reasons.append("|E|>u")
        if e - de > 0.11:
            abort = True; reasons.append("e-de>0.11")
        if e_A > 0.11:
            abort = True; reasons.append("e_A>0.11")
        if e_B > 0.11:
            abort = True; reasons.append("e_B>0.11")
        if abs(e - e_A) > gamma:
            abort = True; reasons.append("|e-e_A|>gamma")
        if abs(e - e_B) > gamma:
            abort = True; reasons.append("|e-e_B|>gamma")

        N_key = int(key_mask.sum())
        e_corr = max(e + de, e_A, e_B, 0.0)
        e_priv = max(e_A, e_B, 0.0)

        eve_intercepted = int(int_mask.sum())
        key_int = int_mask & key_mask
        if key_int.sum() > 0:
            eve_knows = int(np.sum((e_bits == out_A) & key_int))
        else:
            eve_knows = 0

        key_recon, key_pa, recon_stats = self._reconcile_and_amplify(N_key, e_corr)

        return {
            'N': N, 'mode': 'chsh',
            'counts': {'qber': N_qber, 'SA': N_SA, 'SB': N_SB,
                       'det': N_det, 'key': N_key},
            'e': e, 'de': de,
            'S_A': S_A, 'S_B': S_B,
            'e_A': e_A, 'e_B': e_B, 'de_A': de_A, 'de_B': de_B,
            'E_corr': E_corr, 'u': u, 'gamma': gamma,
            'N1_A': N1_A, 'N1_B': N1_B,
            'e_corr': e_corr, 'e_priv': e_priv,
            'abort': abort, 'reasons': reasons,
            'key_rate': N_key / N if N > 0 else 0.0,
            'key_bits_raw': N_key,
            'key_bits_after_recon': key_recon,
            'key_bits_after_pa': key_pa,
            'recon_stats': recon_stats,
            'key_rate_final': key_pa / N if N > 0 else 0.0,
            'eve_intercepted': eve_intercepted,
            'eve_knows_key_bits': eve_knows,
            'sifted_bits_total': N_key,
        }

    # ------------------------------------------------------------------
    def run(self, N, plain_mode=None):
        if plain_mode is None:
            plain_mode = self.cfg.plain_mode
        return self._run_plain(N) if plain_mode else self._run_chsh(N)

    def run_trials(self, N, trials=10, plain_mode=None):
        raw = [self.run(N, plain_mode=plain_mode) for _ in range(trials)]

        scalar_keys = ['e', 'de', 'e_A', 'e_B', 'de_A', 'de_B',
                       'e_corr', 'e_priv', 'E_corr', 'u', 'gamma',
                       'key_rate', 'key_rate_final']
        mean, std = {}, {}
        for key in scalar_keys:
            vals = np.array([r[key] for r in raw], dtype=float)
            mean[key] = float(np.mean(vals))
            std[key] = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0

        for key in ('S_A', 'S_B'):
            vals = np.array([r[key] for r in raw if r[key] is not None],
                            dtype=float)
            if len(vals):
                mean[key] = float(np.mean(vals))
                std[key] = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
            else:
                mean[key] = std[key] = float('nan')

        for key in ('qber', 'SA', 'SB', 'det', 'key'):
            vals = np.array([r['counts'][key] for r in raw], dtype=float)
            mean['N_' + key] = float(np.mean(vals))
            std['N_' + key] = (float(np.std(vals, ddof=1))
                               if len(vals) > 1 else 0.0)

        for field in ('key_bits_raw', 'key_bits_after_recon',
                      'key_bits_after_pa', 'eve_intercepted',
                      'eve_knows_key_bits', 'sifted_bits_total'):
            vals = np.array([r[field] for r in raw], dtype=float)
            mean[field] = float(np.mean(vals))
            std[field] = (float(np.std(vals, ddof=1))
                          if len(vals) > 1 else 0.0)

        n_aborts = sum(r['abort'] for r in raw)
        abort_rate = n_aborts / trials

        successful = [r for r in raw if not r['abort']]
        if successful:
            kr_cond = float(np.mean([r['key_rate'] for r in successful]))
            kr_cond_std = (float(np.std([r['key_rate'] for r in successful],
                                        ddof=1))
                           if len(successful) > 1 else 0.0)
            kr_final_cond = float(np.mean([r['key_rate_final'] for r in successful]))
            kr_final_cond_std = (float(np.std([r['key_rate_final'] for r in successful],
                                              ddof=1))
                                 if len(successful) > 1 else 0.0)
        else:
            kr_cond = kr_cond_std = 0.0
            kr_final_cond = kr_final_cond_std = 0.0

        reasons_count = {}
        for r in raw:
            for reason in r['reasons']:
                reasons_count[reason] = reasons_count.get(reason, 0) + 1
        key_ok_count = sum(1 for r in raw
                           if (not r['abort']) and r['key_bits_after_pa'] > 0)
        success_count = sum(1 for r in raw
                            if (not r['abort']) and r['key_bits_after_pa'] > 0)

        return {
            'trials': trials, 'N': N,
            'mean': mean, 'std': std,
            'abort_rate': abort_rate,
            'abort_reasons': reasons_count,
            'key_rate_conditional': kr_cond,
            'key_rate_conditional_std': kr_cond_std,
            'key_rate_expected': (1 - abort_rate) * kr_cond,
            'key_rate_expected_std': (1 - abort_rate) * kr_cond_std,
            'key_rate_final_conditional': kr_final_cond,
            'key_rate_final_conditional_std': kr_final_cond_std,
            'key_rate_final_expected': (1 - abort_rate) * kr_final_cond,
            'key_rate_final_expected_std': (1 - abort_rate) * kr_final_cond_std,
            'S_ok_count': trials - n_aborts,
            'key_ok_count': key_ok_count,
            'success_count': success_count,
            'raw': raw,
        }


# ----------------------------------------------------------------------
# Фабрики для реестра протоколов
# ----------------------------------------------------------------------

def make_bbm92_plain(config, noise, recon, verbose=False):
    """Оригинальный BBM92 без CHSH/DBA."""
    config.plain_mode = True
    return BBM92Protocol(config, noise, recon, verbose=verbose)


def make_bbm92_chsh(config, noise, recon, verbose=False):
    """BBM92 с CHSH+DBA модификацией."""
    config.plain_mode = False
    return BBM92Protocol(config, noise, recon, verbose=verbose)