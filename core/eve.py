"""Модель атакующей стороны (Евы)."""
import random
from typing import List, Optional, Tuple

from .configs import EveConfig
from .prng import HashPRNG


class EveModel:
    """Модель Евы: принимает решения об атаке, выбирает базисы."""

    def __init__(self, config: EveConfig):
        self.config = config

    def should_attack_phase1(self) -> bool:
        return (self.config.eve_phase1 and
                random.random() < self.config.eve_intercept_p1)

    def should_attack_phase2(self) -> bool:
        return (self.config.eve_phase2 and
                random.random() < self.config.eve_intercept_p2)

    def choose_angles_phase1(self, angles_alice: List[float],
                              angles_bob: List[float]) -> Tuple[float, float]:
        return random.choice(angles_alice), random.choice(angles_bob)

    def choose_angle_phase2(self, angles_p2: List[float],
                             bases_eve: Optional[List[int]],
                             idx: int) -> Tuple[float, int]:
        if bases_eve is not None:
            basis = bases_eve[idx]
        else:
            basis = random.choice([0, 1])
        return angles_p2[basis], basis

    def corrupt_k1(self, k1: List[int]) -> List[int]:
        ber = self.config.eve_k1_ber
        return [1 - b if random.random() < ber else b for b in k1]

    def build_phase2_bases(self, k1: List[int],
                            num_pairs: int) -> Optional[List[int]]:
        """Если Ева знает K1 — вывести её базисы для фазы 2."""
        if not self.config.eve_uses_k1_phase2:
            return None
        eve_k1 = self.corrupt_k1(k1)
        eve_ik = ''.join(str(b) for b in eve_k1).encode('utf-8')
        rng = HashPRNG(eve_ik, b"basis")
        return [rng.next_bit() for _ in range(num_pairs)]