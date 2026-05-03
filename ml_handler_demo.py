"""Demo ML handler — displays a picture for the recognized object.

Categories: box, apple, left, right (case-insensitive).
Probabilities are averaged over the last 4 predictions before the
displayed image is updated.

Requires:
    pip install cairosvg Pillow

Usage:
    python3 run.py -i <ini> -r <ref> --uart --ml --ml-handler ml_handler_demo.py
"""

import collections
import io
import os

import matplotlib.pyplot as plt

_IMGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'imgs')

_IMAGE_MAP = {
    'box':      os.path.join(_IMGS_DIR, 'demo_empty_box.svg'),
    'apple':    os.path.join(_IMGS_DIR, 'demo_apple.svg'),
    'left':   os.path.join(_IMGS_DIR, 'demo_left.svg'),
    'right':   os.path.join(_IMGS_DIR, 'demo_right.svg'),
}

_HISTORY_SIZE = 4

_fig            = None
_ax             = None
_proba_history  = None   # deque of per-category probability dicts
_displayed_label = None
_img_cache      = {}     # label -> numpy array (loaded on first use)


_SVG_SIZE = 800  # render all SVGs to this square pixel size


def _svg_to_array(path: str):
    import cairosvg
    import numpy as np
    from PIL import Image

    png_bytes = cairosvg.svg2png(url=path, output_width=_SVG_SIZE, output_height=_SVG_SIZE)
    return np.array(Image.open(io.BytesIO(png_bytes)))


def _get_image(label: str):
    if label not in _img_cache:
        _img_cache[label] = _svg_to_array(_IMAGE_MAP[label])
    return _img_cache[label]


def _show_label(label: str) -> None:
    global _displayed_label

    if label == _displayed_label:
        return
    _displayed_label = label

    _ax.cla()
    _ax.axis('off')
    _ax.imshow(_get_image(label))
    _fig.texts.clear()
    _fig.text(0.5, 0.01, label.lower(), ha='center', va='bottom',
              fontsize=28, fontweight='bold')
    _fig.canvas.draw_idle()
    _fig.canvas.flush_events()


def on_recognition_start(classes: list) -> None:
    global _fig, _ax, _proba_history, _displayed_label

    _proba_history   = collections.deque(maxlen=_HISTORY_SIZE)
    _displayed_label = None

    _fig, _ax = plt.subplots(figsize=(9, 9))
    _fig.canvas.manager.set_window_title('Object recognition')
    _fig.subplots_adjust(left=0, right=1, top=1, bottom=0.05)
    _ax.axis('off')
    plt.ion()
    plt.show()


def on_prediction(label: str, confidence: float, probabilities: dict) -> None:
    if _fig is None or _proba_history is None:
        return

    # Normalise keys to lower-case so BOX == box, etc.
    norm_proba = {k.lower().strip(): v for k, v in probabilities.items()}
    entry = {cat: norm_proba.get(cat, 0.0) for cat in _IMAGE_MAP}
    _proba_history.append(entry)

    if len(_proba_history) < _HISTORY_SIZE:
        return  # not enough history yet

    # Average probabilities across the history window and pick the winner
    avg  = {cat: sum(e[cat] for e in _proba_history) / _HISTORY_SIZE for cat in _IMAGE_MAP}
    best = max(avg, key=avg.__getitem__)
    _show_label(best)


def on_recognition_stop() -> None:
    global _fig, _ax, _proba_history, _displayed_label

    if _fig is not None:
        plt.close(_fig)

    _fig = _ax = _proba_history = _displayed_label = None
