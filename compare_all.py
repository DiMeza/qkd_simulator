"""Сравнение всех 5 протоколов КРК в одинаковых условиях.

Сценарии (7):
  baseline, noise_0.05, noise_0.15, noise_0.30,
  eve_10%, eve_50%, eve_100%

По умолчанию: 10 прогонов × 10000 пар, force_continue=True для всех.
"""
import argparse
import csv

from core.runner import run_unified


PROTOCOLS = ["hybrid", "e91_basic", "e91_alt", "bbm92_plain", "bbm92_chsh"]

SCENARIOS = [
    ("baseline",   {"noise_p": 0.00, "eve_q": 0.00}),
    ("noise_0.05", {"noise_p": 0.05, "eve_q": 0.00}),
    ("noise_0.15", {"noise_p": 0.15, "eve_q": 0.00}),
    ("noise_0.30", {"noise_p": 0.30, "eve_q": 0.00}),
    ("eve_10%",    {"noise_p": 0.00, "eve_q": 0.10}),
    ("eve_50%",    {"noise_p": 0.00, "eve_q": 0.50}),
    ("eve_100%",   {"noise_p": 0.00, "eve_q": 1.00}),
]


def extract(r):
    """Нормализовать поля результата run_unified."""
    return {
        # S
        "S_mean": r['S_mean'], "S_std": r['S_std'],
        "S2_mean": r.get('S2_mean', 0.0), "S2_std": r.get('S2_std', 0.0),
        # QBER
        "qber_p1_mean": r['qber_mean'], "qber_p1_std": r['qber_std'],
        "qber_p2_mean": r.get('qber_phase2_mean', 0.0),
        "qber_p2_std": r.get('qber_phase2_std', 0.0),
        "qber_k1_mean": r.get('qber_k1_mean', 0.0),
        "qber_k1_std": r.get('qber_k1_std', 0.0),
        "has_k1_mismatch": r.get('has_k1_mismatch', False),
        # K1 (только гибрид)
        "K1_raw_mean": r.get('K1_before_recon_mean', 0.0),
        "K1_raw_std": r.get('K1_before_recon_std', 0.0),
        "K1_recon_mean": r.get('K1_after_recon_mean', 0.0),
        "K1_recon_std": r.get('K1_after_recon_std', 0.0),
        # Финальный ключ
        "key_raw_mean": r['key_before_recon_mean'],
        "key_raw_std": r['key_before_recon_std'],
        "key_recon_mean": r['key_after_recon_mean'],
        "key_recon_std": r['key_after_recon_std'],
        "key_pa_mean": r['key_after_pa_mean'],
        "key_pa_std": r['key_after_pa_std'],
        # Знание Евы
        "eve_intercepted_mean": r['eve_intercepted_mean'],
        "eve_pct_mean": r['eve_knows_pct_mean'],
        # Статусы
        "success_count": r['success_count'],
        "success_pct": r['success_count'] / r['num_runs'] * 100,
        "S_ok_count": r['S_ok_count'],
        "key_ok_count": r['key_ok_count'],
        "phase2_ran_count": r.get('phase2_ran_count', 0),
        "num_runs": r['num_runs'],
    }


def run_all(num_runs, num_pairs):
    data = {}
    total = len(PROTOCOLS) * len(SCENARIOS)
    n = 0
    for proto in PROTOCOLS:
        data[proto] = {}
        for scen_name, params in SCENARIOS:
            n += 1
            print(f"[{n:2d}/{total}] {proto:14s} / {scen_name:10s} ... ",
                  end="", flush=True)
            r = run_unified(
                proto,
                num_runs=num_runs,
                num_pairs=num_pairs,
                force_continue=True,     # игнорируется для E91/BBM92
                **params)
            data[proto][scen_name] = extract(r)
            m = data[proto][scen_name]
            print(f"S={m['S_mean']:+6.2f}±{m['S_std']:.2f}  "
                  f"QBER={m['qber_p2_mean' if proto == 'hybrid' else 'qber_p1_mean']*100:5.2f}%  "
                  f"key_PA={m['key_pa_mean']:5.0f}  "
                  f"success={m['success_pct']:3.0f}%")
    return data


def print_matrix(title, data, field_mean, field_std=None,
                 fmt="{:.2f}", note="", skip_proto_field=None):
    """Матрица mean ± std по всем протоколам и сценариям."""
    print(f"\n{title}")
    if note:
        print(f"  ({note})")
    width = 15
    header = f"{'Протокол':<14}"
    for scen_name, _ in SCENARIOS:
        header += f" {scen_name:>{width}}"
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)
    for proto in PROTOCOLS:
        row = f"{proto:<14}"
        for scen_name, _ in SCENARIOS:
            rec = data[proto][scen_name]
            if skip_proto_field and rec.get(skip_proto_field, 0) == 0 and proto != 'hybrid':
                # для plain bbm92 нет S — показываем N/A
                if field_mean == 'S_mean' and proto == 'bbm92_plain':
                    row += f" {'N/A':>{width}}"
                    continue
            val = rec[field_mean]
            if field_std:
                std = rec[field_std]
                cell = f"{fmt.format(val)}±{fmt.format(std)}"
            else:
                cell = fmt.format(val)
            row += f" {cell:>{width}}"
        print(row)
    print(sep)


def print_hybrid_detail(data):
    """Детализация гибрида: два QBER и длины K1."""
    print("\n" + "=" * 120)
    print("ДЕТАЛИЗАЦИЯ ГИБРИДА: QBER по фазам и длины K1")
    print("=" * 120)

    print("\nQBER по фазам (mean ± std, %):")
    header = f"{'Сценарий':<12}{'QBER ф1 (канал E91)':>26}{'QBER ф2 (финальный ключ)':>26}"
    print(header)
    print("-" * len(header))
    for scen_name, _ in SCENARIOS:
        rec = data['hybrid'][scen_name]
        print(f"{scen_name:<12}"
              f"{rec['qber_p1_mean']*100:>12.2f} ± {rec['qber_p1_std']*100:<8.2f}"
              f"{rec['qber_p2_mean']*100:>12.2f} ± {rec['qber_p2_std']*100:<8.2f}")

    # Если есть сценарии с bob_mismatch — показать отдельно
    any_mismatch = any(data['hybrid'][s]['has_k1_mismatch']
                       for s, _ in SCENARIOS)
    if any_mismatch:
        print("\nQBER K1 (рассогласование K1, только при bob_mismatch_prob > 0):")
        for scen_name, _ in SCENARIOS:
            rec = data['hybrid'][scen_name]
            if rec['has_k1_mismatch']:
                print(f"  {scen_name:<12} "
                      f"{rec['qber_k1_mean']*100:.2f}% ± "
                      f"{rec['qber_k1_std']*100:.2f}%")

    print("\nДлины K1 и финального ключа (mean ± std, бит):")
    header = (f"{'Сценарий':<12}{'K1 raw':>16}{'K1 recon':>16}"
              f"{'Key raw':>16}{'Key recon':>16}{'Key PA':>16}")
    print(header)
    print("-" * len(header))
    for scen_name, _ in SCENARIOS:
        rec = data['hybrid'][scen_name]
        print(f"{scen_name:<12}"
              f"{rec['K1_raw_mean']:>8.0f}±{rec['K1_raw_std']:<6.0f}"
              f"{rec['K1_recon_mean']:>8.0f}±{rec['K1_recon_std']:<6.0f}"
              f"{rec['key_raw_mean']:>8.0f}±{rec['key_raw_std']:<6.0f}"
              f"{rec['key_recon_mean']:>8.0f}±{rec['key_recon_std']:<6.0f}"
              f"{rec['key_pa_mean']:>8.0f}±{rec['key_pa_std']:<6.0f}")


def save_csv(data, path):
    rows = []
    for proto in PROTOCOLS:
        for scen_name, _ in SCENARIOS:
            r = data[proto][scen_name]
            rows.append({"protocol": proto, "scenario": scen_name, **r})
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print(f"CSV: {path}")


def save_markdown(data, path, num_runs, num_pairs):
    lines = ["# Сравнение протоколов КРК\n"]
    lines.append(f"- Прогонов на точку: **{num_runs}**")
    lines.append(f"- Пар на прогон: **{num_pairs}**")
    lines.append(f"- force_continue: **True**\n")

    def table(field_mean, field_std, fmt, title, note=""):
        lines.append(f"## {title}\n")
        if note:
            lines.append(f"*{note}*\n")
        header = "| Протокол | " + " | ".join(s for s, _ in SCENARIOS) + " |"
        sep = "|" + "---|" * (len(SCENARIOS) + 1)
        lines.append(header)
        lines.append(sep)
        for proto in PROTOCOLS:
            row = f"| {proto} |"
            for scen_name, _ in SCENARIOS:
                rec = data[proto][scen_name]
                if field_mean == "S_mean" and proto == "bbm92_plain":
                    row += " N/A |"
                    continue
                if field_std:
                    row += (f" {fmt.format(rec[field_mean])} ± "
                            f"{fmt.format(rec[field_std])} |")
                else:
                    row += f" {fmt.format(rec[field_mean])} |"
            lines.append(row)
        lines.append("")

    table("S_mean", "S_std", "{:.2f}", "S (CHSH-параметр)",
          "|S| > 2 — канал безопасен; plain-режим без CHSH")
    table("qber_p1_mean", "qber_p1_std", "{:.2f}", "QBER, % (фаза 1 для гибрида, единственный для остальных)")
    table("key_raw_mean", "key_raw_std", "{:.0f}", "Сырой ключ (бит)")
    table("key_recon_mean", "key_recon_std", "{:.0f}", "Ключ после согласования (бит)")
    table("key_pa_mean", "key_pa_std", "{:.0f}", "Ключ после усиления (бит)")
    table("success_pct", None, "{:.0f}", "Успешных сеансов, %")

    # Детализация гибрида
    lines.append("## Детализация гибрида: QBER по фазам\n")
    header = "| Сценарий | QBER ф1 (канал E91) | QBER ф2 (финальный ключ) |"
    lines.append(header)
    lines.append("|---|---|---|")
    for scen_name, _ in SCENARIOS:
        rec = data['hybrid'][scen_name]
        lines.append(f"| {scen_name} | "
                     f"{rec['qber_p1_mean']*100:.2f} ± {rec['qber_p1_std']*100:.2f} | "
                     f"{rec['qber_p2_mean']*100:.2f} ± {rec['qber_p2_std']*100:.2f} |")
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Markdown: {path}")


def main():
    parser = argparse.ArgumentParser(
        description="Сравнение 5 протоколов КРК по 7 сценариям")
    parser.add_argument("--runs", type=int, default=10,
                        help="прогонов на точку (по умолчанию 10)")
    parser.add_argument("--pairs", type=int, default=10000,
                        help="пар на прогон (по умолчанию 10000)")
    parser.add_argument("--quick", action="store_true",
                        help="быстрый режим: 3 прогона × 3000 пар")
    args = parser.parse_args()

    if args.quick:
        args.runs = 3
        args.pairs = 3000

    print("=" * 120)
    print(f"СРАВНЕНИЕ ПРОТОКОЛОВ КРК")
    print(f"  7 сценариев × 5 протоколов × {args.runs} прогонов × {args.pairs} пар")
    print(f"  force_continue=True для всех")
    print("=" * 120)

    data = run_all(args.runs, args.pairs)

    print("\n" + "=" * 120)
    print("СВОДНЫЕ МАТРИЦЫ (mean ± std)")
    print("=" * 120)

    print_matrix("S (CHSH-параметр)", data, "S_mean", "S_std",
                 "{:.2f}", "|S| > 2 — канал безопасен")
    print_matrix("QBER, %", data, "qber_p1_mean", "qber_p1_std",
                 "{:.2f}", "фаза 1 для гибрида, единственный для остальных")
    print_matrix("Ключ сырой (бит)", data, "key_raw_mean", "key_raw_std", "{:.0f}")
    print_matrix("Ключ после согласования (бит)", data,
                 "key_recon_mean", "key_recon_std", "{:.0f}")
    print_matrix("Ключ после PA (бит)", data,
                 "key_pa_mean", "key_pa_std", "{:.0f}")
    print_matrix("Успешных сеансов, %", data, "success_pct", None, "{:.0f}")

    print_hybrid_detail(data)

    print()
    save_csv(data, "compare_results.csv")
    save_markdown(data, "compare_results.md", args.runs, args.pairs)


if __name__ == "__main__":
    main()