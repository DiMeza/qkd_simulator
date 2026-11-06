"""Анализ безопасности: CHSH и QBER."""
from typing import List


class SecurityAnalyzer:
    """Анализ безопасности: CHSH-корреляции и QBER (статeless)."""

    @staticmethod
    def compute_S(basis_a: List[int], basis_b: List[int],
                  res_a: List[int], res_b: List[int]) -> float:
        correlations = {(0, 1): 0, (0, 2): 0, (2, 1): 0, (2, 2): 0}
        counts = {(0, 1): 0, (0, 2): 0, (2, 1): 0, (2, 2): 0}
        for i in range(len(basis_a)):
            ab = (basis_a[i], basis_b[i])
            if ab in correlations:
                counts[ab] += 1
                e = 1 if res_a[i] == res_b[i] else -1
                correlations[ab] += e
        E = {ab: (correlations[ab] / counts[ab] if counts[ab] > 0 else 0.0)
             for ab in correlations}
        return E[(0, 1)] - E[(0, 2)] + E[(2, 1)] + E[(2, 2)]

    @staticmethod
    def compute_qber(angles_a: List[float], angles_b: List[float],
                     res_a: List[int], res_b: List[int],
                     basis_a: List[int], basis_b: List[int]) -> float:
        matching = 0
        errors = 0
        for i in range(len(basis_a)):
            a_angle = angles_a[basis_a[i]]
            b_angle = angles_b[basis_b[i]]
            if abs(a_angle - b_angle) < 1e-9:
                matching += 1
                if res_a[i] != res_b[i]:
                    errors += 1
        return errors / matching if matching > 0 else 0.0