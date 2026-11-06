"""Тесты диспетчеризации run_unified."""
import pytest
from core.runner import run_unified


def test_unknown_protocol():
    """Неизвестный протокол → ValueError."""
    with pytest.raises(ValueError, match="Неизвестный протокол"):
        run_unified("nonexistent", num_runs=1, num_pairs=100)


@pytest.mark.parametrize("proto", [
    "hybrid", "e91_basic", "e91_alt", "bbm92_plain", "bbm92_chsh"])
def test_all_protocols_return_dict(proto):
    """Все 5 протоколов возвращают dict с обязательными полями."""
    r = run_unified(proto, num_runs=1, num_pairs=500,
                    noise_p=0.0, eve_q=0.0)
    required = ["protocol", "num_runs", "S_mean", "S_std",
                "qber_mean", "key_before_recon_mean",
                "key_after_pa_mean", "success_count"]
    for key in required:
        assert key in r, f"Отсутствует поле {key} в {proto}"