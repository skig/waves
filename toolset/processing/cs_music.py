from typing import Dict, Optional
import numpy as np
from toolset.constants import SPEED_OF_LIGHT

# --- Hardcoded MUSIC parameters ---
_N_SIGNALS = 1        # number of signal sources (dominant paths)
_SUBARRAY_LEN = None  # None → auto = N // 2
_MAX_DELAY_NS = 500.0 # unambiguous range: 0.5 / f_step = 500 ns at 1 MHz spacing
_N_DELAY_POINTS = 512 # resolution of the pseudo-spectrum delay grid


def compute_music_spectrum(
    phase_data: Dict[int, float],
    amplitude_data: Dict[int, float],
) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """Return (delays_ns, pseudo_spectrum) arrays using t>he MUSIC algorithm, or (None, None)."""
    common_channels = sorted(set(phase_data) & set(amplitude_data))
    n = len(common_channels)
    if n < 4:
        return None, None

    f_step = 1e6  # BLE CS 1 MHz channel spacing

    # Build complex channel vector
    x = np.array([
        10 ** (amplitude_data[ch] / 20.0) * np.exp(1j * phase_data[ch])
        for ch in common_channels
    ], dtype=complex)

    # Spatial smoothing: build covariance from overlapping subarrays
    L = _SUBARRAY_LEN if _SUBARRAY_LEN is not None else n // 2
    L = max(L, _N_SIGNALS + 1)
    n_sub = n - L + 1  # number of subarrays

    R = np.zeros((L, L), dtype=complex)
    for i in range(n_sub):
        sub = x[i:i + L]
        R += np.outer(sub, sub.conj())
    R /= n_sub

    # Eigendecomposition – eigenvalues in ascending order
    eigvals, eigvecs = np.linalg.eigh(R)
    # Noise subspace: all eigenvectors except the _N_SIGNALS largest
    noise_vecs = eigvecs[:, : L - _N_SIGNALS]  # shape (L, L - n_signals)

    # Build MUSIC pseudo-spectrum over delay grid
    delays_ns = np.linspace(0.0, _MAX_DELAY_NS, _N_DELAY_POINTS)
    delays_s = delays_ns * 1e-9

    # Steering vectors: a(tau) = [exp(-j*2*pi*f_step*0*tau), ..., exp(-j*2*pi*f_step*(L-1)*tau)]
    lags = np.arange(L)  # shape (L,)
    # A: shape (L, N_DELAY_POINTS)
    A = np.exp(-1j * 2 * np.pi * f_step * np.outer(lags, delays_s))

    # Noise projection denominator: ||U_N^H a||^2 for each delay
    proj = noise_vecs.conj().T @ A   # shape (L-n_signals, N_DELAY_POINTS)
    denom = np.sum(np.abs(proj) ** 2, axis=0)
    denom = np.maximum(denom, 1e-12)  # avoid division by zero

    pseudo_spectrum = 1.0 / denom

    return delays_ns, pseudo_spectrum


def calculate_distance_from_music(
    delays_ns: np.ndarray,
    pseudo_spectrum: np.ndarray,
) -> float:
    """Return the distance (m) corresponding to the MUSIC pseudo-spectrum peak."""
    return float(delays_ns[np.argmax(pseudo_spectrum)]) * SPEED_OF_LIGHT / 1e9
