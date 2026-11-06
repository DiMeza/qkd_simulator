"""Интеграционные тесты: физика протоколов.

Эти тесты медленные (5-15 секунд каждый), но проверяют, что вся цепочка
от схемы до ключа работает. Запускать отдельно:
    pytest -m slow
"""
import pytest

from core.runner import run_unified


pytestmark = pytest.mark.slow


def test_hybrid_baseline_no_eve():
    """Гибрид без атак: S1 ≈ 2.83, QBER ≈ 0, ключ есть."""
    r = run_unified("hybrid", num_runs=2, num_pairs=2000,
                    noise_p=0.0, eve_q=0.0)
    assert r['S_mean'] > 2.6
    assert r['qber_mean'] < 0.01
    assert r['key_after_pa_mean'] > 0
    assert r['success_count'] == 2


def test_hybrid_full_eve():
    """Гибрид с Eve 100%: S1 падает, QBER ~45%, ключа нет."""
    r = run_unified("hybrid", num_runs=2, num_pairs=2000,
                    noise_p=0.0, eve_q=1.0, force_continue=False)
    assert r['S_mean'] < 1.0
    assert r['qber_mean'] > 0.30
    assert r['success_count'] == 0


def test_e91_basic_baseline():
    """E91 Экерт без атак: |S| ≈ 2.83, ключ есть."""
    r = run_unified("e91_basic", num_runs=2, num_pairs=5000,
                    noise_p=0.0, eve_q=0.0)
    assert abs(r['S_mean']) > 2.6
    assert r['success_count'] == 2


def test_e91_alt_baseline():
    """E91 alt без атак: S ≈ 2.83, ключ есть."""
    r = run_unified("e91_alt", num_runs=2, num_pairs=5000,
                    noise_p=0.0, eve_q=0.0)
    assert r['S_mean'] > 2.6
    assert r['success_count'] == 2


def test_bbm92_chsh_baseline():
    """BBM92 CHSH без атак: S ≈ 2.83, ключ есть."""
    r = run_unified("bbm92_chsh", num_runs=3, num_pairs=5000,
                    noise_p=0.0, eve_q=0.0, seed=42)
    assert r['S_mean'] > 2.5
    # допускаем 1 редкий аборт из 3
    assert r['success_count'] >= 2


def test_bbm92_chsh_eve_50():
    """BBM92 CHSH с Eve 50%: S падает ниже 2, аборт."""
    r = run_unified("bbm92_chsh", num_runs=3, num_pairs=5000,
                    noise_p=0.0, eve_q=0.5, seed=42)
    assert r['S_mean'] < 2.4
    # допускаем 1 редкий успех из 3
    assert r['success_count'] <= 1


def test_bbm92_plain_no_chsh():
    """Plain BBM92: S не вычисляется, QBER ≈ 0, ключ есть."""
    r = run_unified("bbm92_plain", num_runs=2, num_pairs=3000,
                    noise_p=0.0, eve_q=0.0)
    assert r['S_mean'] == 0.0
    assert r['qber_mean'] < 0.01
    assert r['key_after_pa_mean'] > 0