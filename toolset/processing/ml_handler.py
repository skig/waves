"""Loader for user-supplied ML handler scripts.

A handler script may define any combination of these module-level functions:

    def on_recognition_start(classes: list[str]) -> None:
        \"\"\"Called once when recognition begins. 'classes' lists all trained labels.\"\"\"

    def on_prediction(label: str, confidence: float, probabilities: dict[str, float]) -> None:
        \"\"\"Called on every prediction cycle.
        'label'         – best predicted class
        'confidence'    – probability of the best class (0.0–1.0)
        'probabilities' – mapping of every class name to its probability
        \"\"\"

    def on_recognition_stop() -> None:
        \"\"\"Called once when recognition ends.\"\"\"

All three are optional; only the functions present in the script are invoked.
Exceptions inside handler calls are caught and printed without crashing the app.
"""

import importlib.util
import sys
import traceback
from typing import Optional


class MLHandler:
    """Wraps a user script and calls its optional hook functions safely."""

    def __init__(self, script_path: str):
        spec = importlib.util.spec_from_file_location('_ml_handler_script', script_path)
        if spec is None or spec.loader is None:
            raise ImportError(f'Cannot load ML handler script: {script_path}')
        module = importlib.util.module_from_spec(spec)
        sys.modules['_ml_handler_script'] = module
        spec.loader.exec_module(module)
        self._mod = module
        self._script_path = script_path

    def on_recognition_start(self, classes: list) -> None:
        fn = getattr(self._mod, 'on_recognition_start', None)
        if fn is None:
            return
        try:
            fn(classes)
        except Exception:
            print(f'[ml_handler] error in on_recognition_start:')
            traceback.print_exc()

    def on_prediction(self, label: str, confidence: float, probabilities: dict) -> None:
        fn = getattr(self._mod, 'on_prediction', None)
        if fn is None:
            return
        try:
            fn(label, confidence, probabilities)
        except Exception:
            print(f'[ml_handler] error in on_prediction:')
            traceback.print_exc()

    def on_recognition_stop(self) -> None:
        fn = getattr(self._mod, 'on_recognition_stop', None)
        if fn is None:
            return
        try:
            fn()
        except Exception:
            print(f'[ml_handler] error in on_recognition_stop:')
            traceback.print_exc()


def load_ml_handler(script_path: Optional[str]) -> Optional[MLHandler]:
    """Load and return an MLHandler, or None if no path is given."""
    if script_path is None:
        return None
    return MLHandler(script_path)
