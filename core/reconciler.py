"""Согласование ключа и усиление приватности."""
import math
import random
from typing import List, Optional, Tuple

from .configs import ReconciliationConfig


class Reconciler:
    """Согласование и усиление приватности (статeless)."""

    @staticmethod
    def _binary_entropy(p: float) -> float:
        if p <= 0 or p >= 1:
            return 0.0
        return -p * math.log2(p) - (1 - p) * math.log2(1 - p)

    @staticmethod
    def reconcile(raw_key: List[int], qber: float,
                  config: ReconciliationConfig,
                  is_phase2: bool,
                  shared_seed: int) -> Tuple[List[int], dict]:
        if is_phase2:
            enabled = config.enabled
            frame_size = config.frame_size
            success_prob = config.success_prob
            efficiency = config.efficiency
            fixed_leak = config.fixed_leak
            pa_loss = config.pa_entropy_loss
        else:
            enabled = config.enabled_p1
            frame_size = config.frame_size_p1
            success_prob = config.success_prob_p1
            efficiency = config.efficiency_p1
            fixed_leak = config.fixed_leak_p1
            pa_loss = 0.0

        before = len(raw_key)
        stats = {
            'before': before, 'after_recon': before, 'after_pa': before,
            'frames_total': 0, 'frames_success': 0, 'leaked': 0,
        }
        if not enabled:
            return list(raw_key), stats

        L = frame_size
        n_frames = before // L
        stats['frames_total'] = n_frames

        if qber >= 0.5 or n_frames == 0:
            stats['after_recon'] = 0
            stats['after_pa'] = 0
            return [], stats

        rng = random.Random(shared_seed) if shared_seed is not None else random
        if fixed_leak is not None:
            leak_per_frame = int(fixed_leak)
        else:
            h_qber = Reconciler._binary_entropy(qber)
            leak_per_frame = int(efficiency * L * h_qber)

        kept_flags = [rng.random() < success_prob for _ in range(n_frames)]
        n_ok = sum(kept_flags)
        stats['frames_success'] = n_ok

        kept_bits = n_ok * L
        leaked = n_ok * leak_per_frame
        after_recon = max(0, kept_bits - leaked)
        after_pa = max(0, int(after_recon * (1 - pa_loss)))

        stats['after_recon'] = after_recon
        stats['after_pa'] = after_pa
        stats['leaked'] = leaked

        result = []
        for idx, ok in enumerate(kept_flags):
            if ok:
                result.extend(raw_key[idx*L:(idx+1)*L])
        result = result[:after_pa]
        return result, stats