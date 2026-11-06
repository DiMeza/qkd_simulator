"""CLI для запуска экспериментов со всеми протоколами.

Примеры:
    python cli.py --protocol e91_basic
    python cli.py --protocol bbm92_chsh --noise 0.30
    python cli.py --protocol bbm92_chsh --eve-q 0.50
    python cli.py --protocol hybrid --eve-q 0.50 --noise 0.05
    python cli.py --protocol bbm92_plain --runs 20 --pairs 5000
"""
import argparse

from core.runner import run_unified, print_unified_report


def main():
    parser = argparse.ArgumentParser(
        description="Симулятор КРК: запуск экспериментов для всех протоколов")

    parser.add_argument("--protocol", type=str, required=True,
                        choices=["hybrid", "e91_basic", "e91_alt",
                                 "bbm92_plain", "bbm92_chsh"],
                        help="имя протокола")
    parser.add_argument("--runs", type=int, default=10,
                        help="число прогонов (по умолчанию 10)")
    parser.add_argument("--pairs", type=int, default=10000,
                        help="число пар на прогон (по умолчанию 10000)")
    parser.add_argument("--noise", type=float, default=0.0,
                        help="вероятность ошибки на CX (0 = без шума)")
    parser.add_argument("--eve-q", type=float, default=0.0,
                        help="доля перехвата Евы (0 = без атаки)")
    parser.add_argument("--s-threshold", type=float, default=2.0,
                        help="порог S (по умолчанию 2.0)")
    parser.add_argument("--force-continue", action="store_true",
                        help="продолжать при провале S-проверки (только hybrid)")
    parser.add_argument("--plain-mode", action="store_true",
                        help="для bbm92: режим plain без CHSH/DBA")
    parser.add_argument("--seed", type=int, default=None,
                        help="seed для numpy RNG (только bbm92)")

    args = parser.parse_args()

    result = run_unified(
        protocol_name=args.protocol,
        num_runs=args.runs,
        num_pairs=args.pairs,
        noise_p=args.noise,
        eve_q=args.eve_q,
        s_threshold=args.s_threshold,
        force_continue=args.force_continue,
        plain_mode=args.plain_mode if args.protocol.startswith("bbm92") else None,
        seed=args.seed,
    )
    print_unified_report(args.protocol, result)


if __name__ == "__main__":
    main()