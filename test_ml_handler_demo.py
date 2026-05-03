"""Quick manual test for ml_handler_demo.py.

Simulates the ML handler interface without run.py or a real model.
Feeds the chosen label with full probability 4 times (to fill the
averaging window) so the image appears immediately.

Usage:
    python3 test_ml_handler_demo.py [label]

    label — one of: box, apple, left, right  (case-insensitive)
            if omitted, the script prompts interactively.
"""

import sys
import importlib.util
import os

# ── load handler without importing it as a regular module ────────────────────
_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ml_handler_demo.py')
spec   = importlib.util.spec_from_file_location('ml_handler_demo', _script)
mod    = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

CLASSES = ['box', 'apple', 'left', 'right']


def _send(label: str) -> None:
    """Feed 4 identical predictions to fill the averaging window."""
    proba = {cls: (1.0 if cls == label.lower().strip() else 0.0) for cls in CLASSES}
    for _ in range(4):
        mod.on_prediction(label, 1.0, proba)
    import matplotlib.pyplot as plt
    plt.pause(0.05)


# ── start recognition ────────────────────────────────────────────────────────
mod.on_recognition_start(CLASSES)

# ── initial label from CLI or prompt ────────────────────────────────────────
if len(sys.argv) > 1:
    _send(sys.argv[1])

print(f'Labels: {", ".join(CLASSES)}')
print('Type a label and press Enter to switch the image.  Empty line to quit.')

while True:
    try:
        raw = input('label> ').strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not raw:
        break
    if raw.lower() not in CLASSES:
        print(f'  Unknown label. Choose from: {", ".join(CLASSES)}')
        continue
    _send(raw)

mod.on_recognition_stop()
