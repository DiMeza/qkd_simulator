"""Счётчики и метрики сеанса."""
class SessionStats:
    """Счётчики и метрики текущего сеанса протокола."""

    def __init__(self):
        self.key_length_before_recon = 0
        self.key_length_after_recon = 0
        self.key_length_after_pa = 0
        self.recon_frames_total = 0
        self.recon_frames_success = 0
        self.recon_bits_leaked = 0
        self.recon_frames_total_p1 = 0
        self.recon_frames_success_p1 = 0
        self.recon_bits_leaked_p1 = 0
        self.key_length_before_recon_p1 = 0
        self.key_length_after_recon_p1 = 0
        self.eve_knows_k1_bits = 0
        self.k1_bits_total = 0
        self.eve_knows_raw_key_bits = 0
        self.raw_key_bits_total = 0
        self.eve_intercepted_p1 = 0
        self.eve_intercepted_p2 = 0

    def to_dict(self) -> dict:
        return {
            'key_length_before_recon': self.key_length_before_recon,
            'key_length_after_recon': self.key_length_after_recon,
            'key_length_after_pa': self.key_length_after_pa,
            'recon_frames_total': self.recon_frames_total,
            'recon_frames_success': self.recon_frames_success,
            'recon_bits_leaked': self.recon_bits_leaked,
            'recon_frames_total_p1': self.recon_frames_total_p1,
            'recon_frames_success_p1': self.recon_frames_success_p1,
            'recon_bits_leaked_p1': self.recon_bits_leaked_p1,
            'key_length_before_recon_p1': self.key_length_before_recon_p1,
            'key_length_after_recon_p1': self.key_length_after_recon_p1,
            'eve_knows_k1_bits': self.eve_knows_k1_bits,
            'k1_bits_total': self.k1_bits_total,
            'eve_knows_raw_key_bits': self.eve_knows_raw_key_bits,
            'raw_key_bits_total': self.raw_key_bits_total,
            'eve_intercepted_p1': self.eve_intercepted_p1,
            'eve_intercepted_p2': self.eve_intercepted_p2,
        }