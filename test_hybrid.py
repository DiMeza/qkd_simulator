"""Проверка: гибридный протокол через новую структуру работает как раньше."""
import random
from core.runner import run_experiment, print_report


if __name__ == "__main__":
    random.seed(42)  # для воспроизводимости

    print_report("1. БЕЗ ЕВЫ",
                 run_experiment("hybrid",
                                eve_phase1=False, eve_phase2=False,
                                num_runs=10))

    print_report("4. ЕВА НА ОБЕИХ ФАЗАХ (100% и 100%)",
                 run_experiment("hybrid",
                                eve_phase1=True, eve_phase2=True,
                                force_continue=True,
                                eve_intercept_p1=1.00,
                                eve_intercept_p2=1.00,
                                num_runs=10))

    print_report("10. БЕЗ ЕВЫ, ШУМ depolarizing p=0.05",
                 run_experiment("hybrid",
                                eve_phase1=False, eve_phase2=False,
                                force_continue=True,
                                noise_model="depolarizing", noise_p=0.05,
                                num_runs=10))