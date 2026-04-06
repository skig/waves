from typing import Dict, Optional
import numpy as np
from toolset.constants import SPEED_OF_LIGHT


def compute_ifft_response(
    phase_data: Dict[int, float],
    amplitude_data: Dict[int, float],
) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """Return (t_ns, magnitude) arrays from phase/amplitude channel data, or (None, None)."""
    common_channels = sorted(set(phase_data) & set(amplitude_data))
    if len(common_channels) < 2:
        return None, None

    ch_min, ch_max = common_channels[0], common_channels[-1]
    n = ch_max - ch_min + 1
    f_step = 1e6  # BLE CS 1 MHz channel spacing

    spectrum = np.zeros(n, dtype=complex)
    for ch in common_channels:
        amplitude_linear = 10 ** (amplitude_data[ch] / 20.0)
        spectrum[ch - ch_min] = amplitude_linear * np.exp(1j * phase_data[ch])

    magnitude = np.abs(np.fft.ifft(spectrum))

    # t[k] = k / (N * f_step), converted to nanoseconds
    t_ns = np.arange(n) / (n * f_step) * 1e9
    return t_ns, magnitude


def calculate_distance_from_ifft(
    t_ns: np.ndarray,
    magnitude: np.ndarray,
) -> float:
    """Return the distance (m) corresponding to the IFFT magnitude peak."""
    return float(t_ns[np.argmax(magnitude)]) * SPEED_OF_LIGHT / 1e9
