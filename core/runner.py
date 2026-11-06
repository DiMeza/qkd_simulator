"""Запуск серий экспериментов и печать отчёта."""
from collections import defaultdict
from typing import Optional

import numpy as np

from .configs import (
    ProtocolConfig, EveConfig, NoiseConfig, ReconciliationConfig,
    E91Config, E91AltConfig, BBM92Config
)
from .context import SessionContext
from .channel import ChannelSimulator
from .eve import EveModel
from .analyzer import SecurityAnalyzer
from .reconciler import Reconciler
from .stats import SessionStats


def run_unified(protocol_name: str,
                num_runs: int = 10,
                num_pairs: int = 10000,
                noise_p: float = 0.0,
                eve_q: float = 0.0,
                s_threshold: float = 2.0,
                force_continue: bool = False,
                plain_mode: Optional[bool] = None,
                seed: Optional[int] = None,
                **kwargs) -> dict:
    """Универсальный прогон с поддержкой скрытых параметров через **kwargs."""

    from core.configs import E91Config, E91AltConfig, BBM92Config

    noise_name = "depolarizing" if noise_p > 0 else "none"
    noise_cfg = NoiseConfig(noise_model_name=noise_name, noise_p=noise_p)
    
    # Общие параметры согласования
    frame_size = kwargs.get('frame_size', 1024)
    frame_size_p1 = kwargs.get('frame_size_p1', 16)
    success_prob = kwargs.get('success_prob', 0.9)
    efficiency = kwargs.get('efficiency', 1.1)
    pa_loss = kwargs.get('pa_entropy_loss', 0.1)

    recon_cfg = ReconciliationConfig(
        enabled=True, frame_size=frame_size, success_prob=success_prob,
        efficiency=efficiency, pa_entropy_loss=pa_loss,
        enabled_p1=True, frame_size_p1=frame_size_p1)

    # ---------- HYBRID ----------
    if protocol_name == "hybrid":
        from protocols.hybrid import HybridProtocol
        # Раздельные параметры для фаз
        eve_p1 = kwargs.get('eve_p1', eve_q)
        eve_p2 = kwargs.get('eve_p2', eve_q)
        noise_p1 = kwargs.get('noise_p1', noise_p)
        noise_p2 = kwargs.get('noise_p2', noise_p)

        p_cfg = ProtocolConfig(
            total_pairs=num_pairs,
            phase1_ratio=kwargs.get('phase1_ratio', 0.4),
            phase2_ratio=1.0 - kwargs.get('phase1_ratio', 0.4), # Умный расчет
            test_ratio=kwargs.get('test_ratio', 0.1),
            threshold_s=s_threshold,
            iteration=0,
            min_secret_bits=kwargs.get('min_secret_bits', 20),
            bob_mismatch_prob=kwargs.get('bob_mismatch_prob', 0.0),
            force_continue=force_continue,
            noise_p1=noise_p1,
            noise_p2=noise_p2)
            
        eve_cfg = EveConfig(
            eve_phase1=eve_p1 > 0, eve_phase2=eve_p2 > 0,
            eve_intercept_p1=eve_p1, eve_intercept_p2=eve_p2,
            eve_uses_k1_phase2=kwargs.get('eve_uses_k1_phase2', False),
            eve_k1_ber=kwargs.get('eve_k1_ber', 0.0))
            
        ctx = SessionContext(
            protocol=p_cfg, recon=recon_cfg,
            channel=ChannelSimulator(NoiseConfig(noise_model_name="none")),
            eve=EveModel(eve_cfg), analyzer=SecurityAnalyzer(),
            reconciler=Reconciler(), stats=SessionStats())
            
        proto = HybridProtocol(ctx, verbose=False)
        
        results = defaultdict(list)
        for i in range(num_runs):
            res = proto.run()
            results['S1'].append(res.S_phase1)
            results['S2'].append(res.S_phase2)
            results['qber_p1'].append(res.qber_phase1)
            results['qber_p2'].append(res.qber_phase2)
            results['qber_k1'].append(res.qber_k1)
            results['K1_raw'].append(res.key_before_recon_p1)
            results['K1_recon'].append(res.key_after_recon_p1)
            results['key_raw'].append(res.key_length_before_recon)
            results['key_recon'].append(res.key_length_after_recon)
            results['key_pa'].append(res.key_length_after_pa)
            results['eve_int_p1'].append(res.eve_intercepted_p1)
            results['eve_int_p2'].append(res.eve_intercepted_p2)
            results['eve_raw_bits'].append(res.eve_knows_raw_key_bits)
            results['raw_tot'].append(res.raw_key_bits_total)
            results['S1_ok'].append(int(res.S1_ok))
            results['key_ok'].append(int(res.key_ok))
            results['success'].append(int(res.success))
            results['phase2_ran'].append(int(res.phase2_ran))
            
        out = {}
        for key, vals in results.items():
            if key in ('S1_ok', 'key_ok', 'success', 'phase2_ran'):
                out[f'{key}_count'] = int(sum(vals))
            else:
                out[f'{key}_mean'] = float(np.mean(vals)) if vals else 0.0
                out[f'{key}_std'] = float(np.std(vals)) if vals else 0.0

        raw_tot = max(1.0, out.get('raw_tot_mean', 0))
        eve_pct = 100.0 * out.get('eve_raw_bits_mean', 0) / raw_tot
        has_k1_mismatch = (out['qber_k1_mean'] - out['qber_p1_mean']) > 1e-3

        return {
            'protocol': 'hybrid', 'num_runs': num_runs,
            'S_mean': out['S1_mean'], 'S_std': out['S1_std'],
            'S2_mean': out['S2_mean'], 'S2_std': out['S2_std'],
            'qber_mean': out['qber_p1_mean'], 'qber_std': out['qber_p1_std'],
            'qber_phase2_mean': out['qber_p2_mean'], 'qber_phase2_std': out['qber_p2_std'],
            'qber_k1_mean': out['qber_k1_mean'], 'qber_k1_std': out['qber_k1_std'],
            'has_k1_mismatch': has_k1_mismatch,
            'K1_before_recon_mean': out['K1_raw_mean'], 'K1_before_recon_std': out['K1_raw_std'],
            'K1_after_recon_mean': out['K1_recon_mean'], 'K1_after_recon_std': out['K1_recon_std'],
            'key_before_recon_mean': out['key_raw_mean'], 'key_before_recon_std': out['key_raw_std'],
            'key_after_recon_mean': out['key_recon_mean'], 'key_after_recon_std': out['key_recon_std'],
            'key_after_pa_mean': out['key_pa_mean'], 'key_after_pa_std': out['key_pa_std'],
            'eve_intercepted_mean': out['eve_int_p1_mean'] + out['eve_int_p2_mean'],
            'eve_knows_pct_mean': eve_pct,
            'S_ok_count': out['S1_ok_count'],
            'key_ok_count': out['key_ok_count'],
            'success_count': out['success_count'],
            'phase2_ran_count': out['phase2_ran_count'],
            'abort_rate': 0.0,
        }

    # ---------- E91 ----------
    if protocol_name in ("e91_basic", "e91_alt"):
        from protocols.e91_basic import E91BasicProtocol
        from protocols.e91_alt import E91AltProtocol
        # ... (остается без изменений, как было) ...
        cfg_cls = E91Config if protocol_name == "e91_basic" else E91AltConfig
        proto_cls = E91BasicProtocol if protocol_name == "e91_basic" else E91AltProtocol
        cfg = cfg_cls(
            num_pairs=num_pairs, iteration=0,
            eve_enabled=eve_q > 0, eve_intercept=eve_q,
            s_threshold=s_threshold)
            
        recon_cfg_e91 = ReconciliationConfig(
            enabled=True, frame_size=frame_size_p1, 
            success_prob=success_prob, efficiency=efficiency, pa_entropy_loss=pa_loss)
            
        proto = proto_cls(cfg, noise_cfg, recon_cfg_e91, verbose=False)
        agg = proto.run_trials(trials=num_runs)
        m, s = agg['mean'], agg['std']
        sift = max(1.0, m.get('sifted_bits_total', 0))
        
        return {
            'protocol': protocol_name, 'num_runs': num_runs,
            'S_mean': m.get('S', 0.0), 'S_std': s.get('S', 0.0),
            'S2_mean': 0.0, 'S2_std': 0.0,
            'qber_mean': m.get('qber', 0.0), 'qber_std': s.get('qber', 0.0),
            'qber_k1_mean': 0.0, 'qber_k1_std': 0.0,
            'qber_phase2_mean': 0.0, 'qber_phase2_std': 0.0,
            'K1_before_recon_mean': 0.0, 'K1_before_recon_std': 0.0,
            'K1_after_recon_mean': 0.0, 'K1_after_recon_std': 0.0,
            'key_before_recon_mean': m.get('key_before_recon', 0.0),
            'key_before_recon_std': s.get('key_before_recon', 0.0),
            'key_after_recon_mean': m.get('key_after_recon', 0.0),
            'key_after_recon_std': s.get('key_after_recon', 0.0),
            'key_after_pa_mean': m.get('key_after_pa', 0.0),
            'key_after_pa_std': s.get('key_after_pa', 0.0),
            'eve_intercepted_mean': m.get('eve_intercepted', 0.0),
            'eve_knows_pct_mean': 100.0 * m.get('eve_knows_key_bits', 0) / sift,
            'S_ok_count': agg.get('S_ok_count', 0),
            'key_ok_count': agg.get('key_ok_count', 0),
            'success_count': agg.get('success_count', 0),
            'phase2_ran_count': 0, 'abort_rate': 0.0,
        }

    # ---------- BBM92 ----------
    if protocol_name in ("bbm92_plain", "bbm92_chsh"):
        from protocols.bbm92 import BBM92Protocol
        is_plain = (protocol_name == "bbm92_plain") if plain_mode is None else plain_mode
        
        cfg = BBM92Config(
            p=kwargs.get('p', 0.15), 
            k=kwargs.get('k', 1.5),            # НОВЫЙ ПАРАМЕТР
            z_u=kwargs.get('z_u', 5.0),        # НОВЫЙ ПАРАМЕТР
            z_gamma=kwargs.get('z_gamma', 5.0),# НОВЫЙ ПАРАМЕТР
            qber_threshold=kwargs.get('qber_threshold', 0.11), 
            eve_q=eve_q, eve_basis=(0.0, 45.0), plain_mode=is_plain, seed=seed)
            
        proto = BBM92Protocol(cfg, noise_cfg, recon_cfg, verbose=False)
        agg = proto.run_trials(num_pairs, trials=num_runs, plain_mode=is_plain)
        m, s = agg['mean'], agg['std']
        
        S_A = m.get('S_A')
        if S_A is None or (isinstance(S_A, float) and np.isnan(S_A)):
            S_mean, S_std = 0.0, 0.0
        else:
            S_mean = float(S_A)
            sa_s = s.get('S_A')
            S_std = 0.0 if (sa_s is None or (isinstance(sa_s, float) and np.isnan(sa_s))) else float(sa_s)
            
        sift = max(1.0, m.get('sifted_bits_total', 0))
        
        return {
            'protocol': protocol_name, 'num_runs': num_runs,
            'S_mean': S_mean, 'S_std': S_std,
            'S2_mean': 0.0, 'S2_std': 0.0,
            'qber_mean': m.get('e', 0.0), 'qber_std': s.get('e', 0.0),
            'qber_k1_mean': 0.0, 'qber_k1_std': 0.0,
            'qber_phase2_mean': 0.0, 'qber_phase2_std': 0.0,
            'K1_before_recon_mean': 0.0, 'K1_before_recon_std': 0.0,
            'K1_after_recon_mean': 0.0, 'K1_after_recon_std': 0.0,
            'key_before_recon_mean': m.get('key_bits_raw', 0.0),
            'key_before_recon_std': s.get('key_bits_raw', 0.0),
            'key_after_recon_mean': m.get('key_bits_after_recon', 0.0),
            'key_after_recon_std': s.get('key_bits_after_recon', 0.0),
            'key_after_pa_mean': m.get('key_bits_after_pa', 0.0),
            'key_after_pa_std': s.get('key_bits_after_pa', 0.0),
            'eve_intercepted_mean': m.get('eve_intercepted', 0.0),
            'eve_knows_pct_mean': 100.0 * m.get('eve_knows_key_bits', 0) / sift,
            'S_ok_count': agg.get('S_ok_count', 0),
            'key_ok_count': agg.get('key_ok_count', 0),
            'success_count': agg.get('success_count', 0),
            'phase2_ran_count': 0, 'abort_rate': agg.get('abort_rate', 0.0),
        }

    raise ValueError(f"Неизвестный протокол: {protocol_name}")


def print_unified_report(name: str, r: dict) -> None:
    """Печать унифицированного отчёта."""
    n = r['num_runs']
    print(f"=== {name} ({n} прогонов) ===")
    proto = r['protocol']

    if proto == 'bbm92_plain':
        print("S       = N/A (plain режим, CHSH не используется)")
    elif r['S_mean'] < 0:
        print(f"S       = {r['S_mean']:.3f} ± {r['S_std']:.3f}  (|S| = {abs(r['S_mean']):.3f})")
    else:
        print(f"S       = {r['S_mean']:.3f} ± {r['S_std']:.3f}")

    if proto == 'hybrid':
        print(f"S2      = {r.get('S2_mean', 0):.3f} ± {r.get('S2_std', 0):.3f}")

    if proto == 'hybrid':
        print(f"QBER ф1 = {r['qber_mean']*100:.2f}% ± {r['qber_std']*100:.2f}%  (канал E91)")
        print(f"QBER ф2 = {r['qber_phase2_mean']*100:.2f}% ± {r['qber_phase2_std']*100:.2f}%  (финальный ключ)")
        if r.get('has_k1_mismatch', False):
            print(f"QBER K1 = {r['qber_k1_mean']*100:.2f}% ± {r['qber_k1_std']*100:.2f}%  (рассогласование K1)")
    else:
        print(f"QBER    = {r['qber_mean']*100:.2f}% ± {r['qber_std']*100:.2f}%")

    if proto == 'hybrid':
        print(f"K1:   raw={r['K1_before_recon_mean']:.0f} ± {r['K1_before_recon_std']:.0f}, "
              f"recon={r['K1_after_recon_mean']:.0f} ± {r['K1_after_recon_std']:.0f} бит")
              
    print(f"Ключ: raw={r['key_before_recon_mean']:.0f} ± {r['key_before_recon_std']:.0f}, "
          f"recon={r['key_after_recon_mean']:.0f} ± {r['key_after_recon_std']:.0f}, "
          f"PA={r['key_after_pa_mean']:.0f} ± {r['key_after_pa_std']:.0f} бит")

    print(f"Ева перехватила = {r['eve_intercepted_mean']:.1f} пар")
    print(f"Ева знает ключ  = {r['eve_knows_pct_mean']:.1f}%")

    if r.get('abort_rate', 0) > 0:
        print(f"Абортов         = {r['abort_rate']*n:.0f}/{n}")
    if proto == 'hybrid':
        print(f"Фаза 2 запускалась = {r['phase2_ran_count']}/{n}")
    if proto == 'bbm92_plain':
        print("S-проверка:     N/A (plain режим)")
    else:
        print(f"S-проверка:     {r['S_ok_count']}/{n}")
    print(f"Согласование:   {r['key_ok_count']}/{n}")
    print(f"Успешных:       {r['success_count']}/{n}")
    print()