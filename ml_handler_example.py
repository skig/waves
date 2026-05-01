"""Example ML handler — live probability bar chart in a separate window.

Usage:
    python3 run.py -i <ini> -r <ref> --uart --ml --ml-handler ml_handler_example.py
"""

import matplotlib.pyplot as plt
import numpy as np

_fig = None
_ax = None
_bars = None
_classes = None


def on_recognition_start(classes: list) -> None:
    global _fig, _ax, _bars, _classes

    _classes = classes
    n = len(classes)

    _fig, _ax = plt.subplots(figsize=(max(4, n * 0.9), 4))
    _fig.canvas.manager.set_window_title('ML probabilities')

    x = np.arange(n)
    colors = plt.cm.tab10(np.linspace(0, 1, n))
    _bars = _ax.bar(x, np.zeros(n), align='center', color=colors, alpha=0.85)

    _ax.set_xticks(x)
    _ax.set_xticklabels(classes, rotation=30, ha='right')
    _ax.set_ylim(0, 1)
    _ax.set_ylabel('Probability')
    _ax.set_title('Live ML probabilities')
    _ax.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5, linewidth=1)
    _ax.grid(True, axis='y', alpha=0.4)

    _fig.tight_layout()
    plt.ion()
    plt.show()


def on_prediction(label: str, confidence: float, probabilities: dict) -> None:
    if _bars is None or _classes is None:
        return

    for bar, cls in zip(_bars, _classes):
        bar.set_height(probabilities.get(cls, 0.0))

    _ax.set_title(f'{label}  ({confidence:.0%})')
    _fig.canvas.draw_idle()
    _fig.canvas.flush_events()


def on_recognition_stop() -> None:
    global _fig, _ax, _bars, _classes

    if _fig is not None:
        plt.close(_fig)

    _fig = _ax = _bars = _classes = None
