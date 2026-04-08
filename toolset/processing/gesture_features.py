"""Window-based gesture feature extraction for dynamic gesture recognition."""

from typing import List

import numpy as np


def build_gesture_feature_vector(window: List[np.ndarray]) -> np.ndarray:
    """Build a gesture feature vector from a time window of per-subevent vectors.

    Computes temporal statistics across the window:
      - mean per feature
      - std per feature
      - delta (last - first) per feature

    Args:
        window: List of per-subevent feature vectors (each 148-dim from
                build_feature_vector). Must contain at least 2 vectors.

    Returns:
        A 444-dim vector: [mean(148), std(148), delta(148)].

    Raises:
        ValueError: If window has fewer than 2 vectors.
    """
    if len(window) < 2:
        raise ValueError(f'Dynamic gesture window needs at least 2 subevents, got {len(window)}')

    stack = np.stack(window)  # (N, 148)
    mean = stack.mean(axis=0)
    std = stack.std(axis=0)
    delta = stack[-1] - stack[0]

    return np.concatenate([mean, std, delta]).astype(np.float32)
