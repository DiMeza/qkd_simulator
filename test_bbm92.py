"""Проверка BBM92: plain и CHSH+DBA режимы."""
import numpy as np

from core.configs import BBM92Config, NoiseConfig, ReconciliationConfig
from protocols.bbm92 import BBM92Protocol


def run_scenario(name, N, trials, plain_mode, noise_p=0.0, eve_q=0.0):
    cfg = BBM92Config(
        p=0.15, k=1.5, z_u=5.0, z_gamma=5.0,
        qber_threshold=0.11, eve_q=eve_q, eve_basis=(0.0, 45.0),
        plain_mode=plain_mode, seed=None)
    noise = NoiseConfig(
        noise_model_name="depolarizing" if noise_p > 0 else "none",
        noise_p=noise_p)
    recon = ReconciliationConfig(
        enabled=True, frame_size=1024, success_prob=0.9,
        efficiency=1.1, pa_entropy_loss=0.1)

    proto = BBM92Protocol(cfg, noise, recon, verbose=False)
    agg = proto.run_trials(N, trials=trials, plain_mode=plain_mode)
    m, s = agg['mean'], agg['std']

    print(f"\n--- {name} ---")
    if plain_mode:
        print(f"  QBER            = {m['e']*100:.2f}% ± {s['e']*100:.2f}%")
        print(f"  de              = {m['de']:.4f} ± {s['de']:.4f}")
    else:
        sa = f"{m['S_A']:.3f} ± {s['S_A']:.3f}" if not np.isnan(m['S_A']) else "N/A"
        sb = f"{m['S_B']:.3f} ± {s['S_B']:.3f}" if not np.isnan(m['S_B']) else "N/A"
        print(f"  S_A             = {sa}")
        print(f"  S_B             = {sb}")
        print(f"  QBER            = {m['e']*100:.2f}% ± {s['e']*100:.2f}%")
        print(f"  e_A             = {m['e_A']:.4f}")
        print(f"  E_corr          = {m['E_corr']:.4f}  (u = {m['u']:.4f})")
    print(f"  Ключ до recon   = {m['key_bits_raw']:.1f} ± {s['key_bits_raw']:.1f}")
    print(f"  Ключ после recon= {m['key_bits_after_recon']:.1f} ± {s['key_bits_after_recon']:.1f}")
    print(f"  Ключ после PA   = {m['key_bits_after_pa']:.1f} ± {s['key_bits_after_pa']:.1f}")
    print(f"  Ева перехватила = {m['eve_intercepted']:.1f} пар")
    sift = max(1.0, m['sifted_bits_total'])
    eve_pct = 100.0 * m['eve_knows_key_bits'] / sift
    print(f"  Ева знает ключ  = {m['eve_knows_key_bits']:.1f} из "
          f"{m['sifted_bits_total']:.0f} бит ({eve_pct:.1f}%)")
    print(f"  Абортов:        {int(agg['abort_rate']*trials)}/{trials}")
    if agg['abort_reasons']:
        print(f"  Причины:        {agg['abort_reasons']}")
    print(f"  Полностью успешных: {agg['success_count']}/{trials}")


if __name__ == "__main__":
    print("=" * 70)
    print("BBM92 + CHSH + DBA (модификация)")
    print("=" * 70)
    run_scenario("1. Baseline (без шума, без Eve)", 10000, 10, plain_mode=False)
    run_scenario("4. Шум p=0.30", 10000, 10, plain_mode=False, noise_p=0.30)
    run_scenario("5. Eve q=0.10", 10000, 10, plain_mode=False, eve_q=0.10)
    run_scenario("6. Eve q=0.50", 10000, 10, plain_mode=False, eve_q=0.50)
    run_scenario("7. Eve q=1.00", 10000, 10, plain_mode=False, eve_q=1.00)

    print("\n" + "=" * 70)
    print("BBM92 plain (оригинальный, без CHSH/DBA)")
    print("=" * 70)
    run_scenario("10. Plain baseline", 10000, 10, plain_mode=True)