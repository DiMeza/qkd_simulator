"""Проверка единого интерфейса для всех пяти протоколов."""
from core.runner import run_unified, print_unified_report


if __name__ == "__main__":
    scenarios = [
        ("hybrid",      {"eve_q": 0.0,  "noise_p": 0.0, "num_runs": 5}),
        ("hybrid",      {"eve_q": 1.0,  "noise_p": 0.0, "num_runs": 5,
                         "force_continue": True}),
        ("e91_basic",   {"eve_q": 0.0,  "noise_p": 0.0, "num_runs": 5}),
        ("e91_basic",   {"eve_q": 0.5,  "noise_p": 0.0, "num_runs": 5}),
        ("e91_alt",     {"eve_q": 0.0,  "noise_p": 0.15, "num_runs": 5}),
        ("bbm92_chsh",  {"eve_q": 0.0,  "noise_p": 0.0, "num_runs": 5}),
        ("bbm92_chsh",  {"eve_q": 0.5,  "noise_p": 0.0, "num_runs": 5}),
        ("bbm92_plain", {"eve_q": 0.0,  "noise_p": 0.0, "num_runs": 5}),
    ]

    for proto, params in scenarios:
        # E91 требует больше пар для нормальной статистики
        pairs = 5000 if proto.startswith("e91") else 2000
        r = run_unified(proto, num_pairs=pairs, **params)
        label = f"{proto} (noise={params['noise_p']}, eve={params['eve_q']})"
        print_unified_report(label, r)