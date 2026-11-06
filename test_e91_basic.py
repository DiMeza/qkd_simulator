"""Проверка E91 (Экерт, 1991): оригинальный протокол."""
from core.configs import E91Config, NoiseConfig, ReconciliationConfig
from protocols.e91_basic import E91BasicProtocol


def run_scenario(name, num_pairs=10000, trials=10,
                 eve_enabled=False, eve_intercept=1.0, noise_p=0.0):
    cfg = E91Config(
        num_pairs=num_pairs, iteration=0,
        eve_enabled=eve_enabled, eve_intercept=eve_intercept,
        s_threshold=2.0)
    noise = NoiseConfig(
        noise_model_name="depolarizing" if noise_p > 0 else "none",
        noise_p=noise_p)
    recon = ReconciliationConfig(
        enabled=True, frame_size=1024, success_prob=0.9,
        efficiency=1.1, pa_entropy_loss=0.1)

    proto = E91BasicProtocol(cfg, noise, recon, verbose=False)
    agg = proto.run_trials(trials=trials)
    m, s = agg['mean'], agg['std']

    print(f"\n--- {name} ---")
    print(f"  S       = {m['S']:.3f} ± {s['S']:.3f}")
    print(f"  QBER    = {m['qber']*100:.2f}% ± {s['qber']*100:.2f}%")
    print(f"  Ключ до recon   = {m['key_before_recon']:.1f} ± {s['key_before_recon']:.1f}")
    print(f"  Ключ после recon= {m['key_after_recon']:.1f} ± {s['key_after_recon']:.1f}")
    print(f"  Ключ после PA   = {m['key_after_pa']:.1f} ± {s['key_after_pa']:.1f}")
    print(f"  Ева перехватила = {m['eve_intercepted']:.1f} пар")
    sift = max(1.0, m['sifted_bits_total'])
    eve_pct = 100.0 * m['eve_knows_key_bits'] / sift
    print(f"  Ева знает ключ  = {m['eve_knows_key_bits']:.1f} из "
          f"{m['sifted_bits_total']:.0f} бит ({eve_pct:.1f}%)")
    print(f"  Прошли S-проверку:      {agg['S_ok_count']}/{trials}")
    print(f"  Согласование дало ключ: {agg['key_ok_count']}/{trials}")
    print(f"  Полностью успешных:     {agg['success_count']}/{trials}")


if __name__ == "__main__":
    print("=" * 70)
    print("E91 (Экерт, 1991) — оригинальный")
    print("=" * 70)

    run_scenario("1. Без Евы, без шума")
    run_scenario("2. Ева перехватывает 10%", eve_enabled=True, eve_intercept=0.10)
    run_scenario("3. Ева перехватывает 50%", eve_enabled=True, eve_intercept=0.50)
    run_scenario("4. Ева перехватывает 100%", eve_enabled=True, eve_intercept=1.00)
    run_scenario("6. Шум p=0.15 (без Евы)", noise_p=0.15)