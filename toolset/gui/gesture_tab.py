import os
import time
import tkinter as tk
from tkinter import ttk, filedialog
from typing import Dict, List, Optional, Tuple
import numpy as np
from toolset.processing.sensing_features import (
    build_feature_vector, sensing_drop_reason,
)
from toolset.processing.gesture_features import build_gesture_feature_vector
from toolset.gui.cs_theme import _Theme

_DATASETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'datasets')


class GestureTabMixin:
    """Gesture tab: data collection, training, and real-time recognition."""

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_gesture_tab(self, tab_frame: ttk.Frame):
        self._gesture_mode = tk.StringVar(value='static')
        self._gesture_label_var = tk.StringVar(value='')
        self._gesture_window_duration = tk.DoubleVar(value=2.0)
        self._gesture_recording = False
        self._gesture_window_buffer: List[np.ndarray] = []
        self._gesture_window_start: Optional[float] = None

        # Stored data: list of (label, feature_vector)
        self._gesture_samples: List[Tuple[str, np.ndarray]] = []
        self._gesture_labels_order: List[str] = []
        self._gesture_dropped: int = 0

        # Use-feature flags (same as sensing tab)
        self._gesture_use_phase = tk.BooleanVar(value=True)
        self._gesture_use_amplitude_response = tk.BooleanVar(value=True)

        # ---- row 0: mode selector ----
        mode_frame = ttk.Frame(tab_frame)
        mode_frame.grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        ttk.Label(mode_frame, text='Mode:').grid(row=0, column=0, sticky=tk.W)
        ttk.Radiobutton(mode_frame, text='Static', variable=self._gesture_mode,
                        value='static', command=self._on_gesture_mode_changed).grid(row=0, column=1, padx=(8, 0))
        ttk.Radiobutton(mode_frame, text='Dynamic', variable=self._gesture_mode,
                        value='dynamic', command=self._on_gesture_mode_changed).grid(row=0, column=2, padx=(4, 0))

        # Window duration (only for dynamic)
        ttk.Label(mode_frame, text='Window (s):').grid(row=0, column=3, padx=(20, 0))
        self._gesture_window_spin = ttk.Spinbox(
            mode_frame, from_=0.5, to=10.0, increment=0.5,
            textvariable=self._gesture_window_duration, width=5,
        )
        self._gesture_window_spin.grid(row=0, column=4, padx=(4, 0))

        # Feature checkboxes
        ttk.Label(mode_frame, text='Features:').grid(row=0, column=5, padx=(20, 0))
        ttk.Checkbutton(mode_frame, text='Phase', variable=self._gesture_use_phase).grid(row=0, column=6, padx=(4, 0))
        ttk.Checkbutton(mode_frame, text='Ampl. response', variable=self._gesture_use_amplitude_response).grid(row=0, column=7, padx=(4, 0))

        # ---- row 1: recording controls ----
        ctrl = ttk.Frame(tab_frame)
        ctrl.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 8))

        ttk.Label(ctrl, text='Label:').grid(row=0, column=0, sticky=tk.W)
        label_entry = ttk.Entry(ctrl, textvariable=self._gesture_label_var, width=20)
        label_entry.grid(row=0, column=1, sticky=tk.W, padx=(6, 0))

        self._gesture_record_btn = ttk.Button(ctrl, text='Record sample', command=self._on_gesture_record)
        self._gesture_record_btn.grid(row=0, column=2, padx=(12, 0))

        ttk.Button(ctrl, text='Clear all', command=self._on_gesture_clear).grid(row=0, column=3, padx=(6, 0))
        ttk.Button(ctrl, text='Save dataset', command=self._on_gesture_save_dataset).grid(row=0, column=4, padx=(6, 0))
        ttk.Button(ctrl, text='Load dataset', command=self._on_gesture_load_dataset).grid(row=0, column=5, padx=(6, 0))

        self._gesture_status = ttk.Label(ctrl, text='0 samples')
        self._gesture_status.grid(row=0, column=6, padx=(16, 0), sticky=tk.W)

        # ---- row 2: sample summary ----
        self._gesture_summary = tk.Text(
            tab_frame, height=6, wrap=tk.WORD, state=tk.DISABLED,
            bg=_Theme.AltBackground, fg=_Theme.Foreground,
            relief=tk.FLAT, padx=8, pady=4,
        )
        self._gesture_summary.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 8))

        # ---- row 3: placeholder for future training/recognition UI ----
        self._gesture_main_frame = ttk.Frame(tab_frame)
        self._gesture_main_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        tab_frame.rowconfigure(3, weight=1)
        tab_frame.columnconfigure(0, weight=1)

        self._on_gesture_mode_changed()

    # ------------------------------------------------------------------
    # Update (called whenever tab is active and data changes)
    # ------------------------------------------------------------------

    def _update_gesture_tab(self):
        if self._gesture_recording and self._gesture_mode.get() == 'dynamic':
            self._gesture_capture_to_buffer()

    # ------------------------------------------------------------------
    # Mode
    # ------------------------------------------------------------------

    def _on_gesture_mode_changed(self):
        is_dynamic = self._gesture_mode.get() == 'dynamic'
        state = tk.NORMAL if is_dynamic else tk.DISABLED
        self._gesture_window_spin.config(state=state)
        if self._gesture_recording:
            self._gesture_stop_recording()

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def _on_gesture_record(self):
        label = self._gesture_label_var.get().strip()
        if not label:
            self._gesture_status.config(text='Enter a label first')
            return

        mode = self._gesture_mode.get()
        if mode == 'static':
            self._gesture_record_static(label)
        else:
            if self._gesture_recording:
                self._gesture_stop_recording()
            else:
                self._gesture_start_dynamic_recording()

    def _gesture_record_static(self, label: str):
        """Capture the current subevent as a single static sample."""
        phase_data = getattr(self, '_current_phase_slope_data', None)
        amplitude_response = getattr(self, '_current_amplitude_response_data', None)
        initiator = getattr(self, '_current_initiator', None)
        reflector = getattr(self, '_current_reflector', None)

        drop_reason = sensing_drop_reason(initiator, reflector, phase_data, amplitude_response)
        if drop_reason:
            self._gesture_dropped += 1
            self._gesture_status.config(text=f'Dropped: {drop_reason}')
            return

        vec = build_feature_vector(
            phase_data, amplitude_response,
            use_phase=self._gesture_use_phase.get(),
            use_amplitude_response=self._gesture_use_amplitude_response.get(),
        )
        if vec is None:
            self._gesture_status.config(text='No feature data available')
            return

        label = self._gesture_label_var.get().strip()
        self._gesture_samples.append((label, vec))
        if label not in self._gesture_labels_order:
            self._gesture_labels_order.append(label)
        self._gesture_update_summary()
        self._gesture_status.config(text=f'{len(self._gesture_samples)} samples — recorded static [{label}]')

    def _gesture_start_dynamic_recording(self):
        """Begin collecting subevents into the window buffer."""
        self._gesture_recording = True
        self._gesture_window_buffer.clear()
        self._gesture_window_start = time.monotonic()
        self._gesture_record_btn.config(text='Stop recording')
        self._gesture_status.config(text='Recording... (move now)')

    def _gesture_stop_recording(self):
        """Stop dynamic recording and finalize the sample."""
        self._gesture_recording = False
        self._gesture_record_btn.config(text='Record sample')

        buf = self._gesture_window_buffer
        if len(buf) < 2:
            self._gesture_status.config(
                text=f'Recording stopped — need at least 2 subevents, got {len(buf)}'
            )
            return

        vec = build_gesture_feature_vector(buf)
        label = self._gesture_label_var.get().strip()
        if not label:
            self._gesture_status.config(text='No label set — sample discarded')
            return

        self._gesture_samples.append((label, vec))
        if label not in self._gesture_labels_order:
            self._gesture_labels_order.append(label)
        self._gesture_update_summary()
        self._gesture_status.config(
            text=f'{len(self._gesture_samples)} samples — recorded dynamic [{label}] ({len(buf)} subevents)'
        )

    def _gesture_capture_to_buffer(self):
        """Append the current subevent's feature vector to the window buffer.

        Auto-stops when the window duration is reached.
        """
        phase_data = getattr(self, '_current_phase_slope_data', None)
        amplitude_response = getattr(self, '_current_amplitude_response_data', None)
        initiator = getattr(self, '_current_initiator', None)
        reflector = getattr(self, '_current_reflector', None)

        drop_reason = sensing_drop_reason(initiator, reflector, phase_data, amplitude_response)
        if drop_reason:
            self._gesture_dropped += 1
            return

        vec = build_feature_vector(
            phase_data, amplitude_response,
            use_phase=self._gesture_use_phase.get(),
            use_amplitude_response=self._gesture_use_amplitude_response.get(),
        )
        if vec is not None:
            self._gesture_window_buffer.append(vec)

        elapsed = time.monotonic() - self._gesture_window_start
        duration = self._gesture_window_duration.get()
        remaining = max(0, duration - elapsed)
        self._gesture_status.config(
            text=f'Recording... {len(self._gesture_window_buffer)} subevents, {remaining:.1f}s left'
        )

        if elapsed >= duration:
            self._gesture_stop_recording()

    # ------------------------------------------------------------------
    # Clear
    # ------------------------------------------------------------------

    def _on_gesture_clear(self):
        self._gesture_samples.clear()
        self._gesture_labels_order.clear()
        self._gesture_dropped = 0
        self._gesture_recording = False
        self._gesture_window_buffer.clear()
        self._gesture_window_start = None
        self._gesture_record_btn.config(text='Record sample')
        self._gesture_status.config(text='0 samples')
        self._gesture_update_summary()

    # ------------------------------------------------------------------
    # Dataset save / load
    # ------------------------------------------------------------------

    def _on_gesture_save_dataset(self):
        if not self._gesture_samples:
            self._gesture_status.config(text='No samples to save')
            return

        os.makedirs(_DATASETS_DIR, exist_ok=True)
        path = filedialog.asksaveasfilename(
            initialdir=_DATASETS_DIR,
            defaultextension='.npz',
            filetypes=[('NumPy archive', '*.npz')],
            title='Save gesture dataset',
        )
        if not path:
            return

        labels = np.array([s[0] for s in self._gesture_samples])
        features = np.stack([s[1] for s in self._gesture_samples])
        np.savez(
            path,
            labels=labels,
            features=features,
            mode=self._gesture_mode.get(),
            window_duration=self._gesture_window_duration.get(),
            use_phase=self._gesture_use_phase.get(),
            use_amplitude_response=self._gesture_use_amplitude_response.get(),
        )
        self._gesture_status.config(text=f'Saved {len(self._gesture_samples)} samples to {os.path.basename(path)}')

    def _on_gesture_load_dataset(self):
        if os.path.isdir(_DATASETS_DIR):
            initial = _DATASETS_DIR
        else:
            initial = os.getcwd()

        path = filedialog.askopenfilename(
            initialdir=initial,
            filetypes=[('NumPy archive', '*.npz')],
            title='Load gesture dataset',
        )
        if not path:
            return

        try:
            data = np.load(path, allow_pickle=False)
        except Exception as e:
            self._gesture_status.config(text=f'Load error: {e}')
            return

        loaded_mode = str(data.get('mode', 'static'))
        loaded_labels = data['labels']
        loaded_features = data['features']

        # Enforce mode consistency
        if self._gesture_samples:
            current_mode = self._gesture_mode.get()
            if loaded_mode != current_mode:
                self._gesture_status.config(
                    text=f'Mode mismatch: dataset is {loaded_mode}, current is {current_mode}. Clear first or switch mode.'
                )
                return

        # Apply loaded mode and settings
        self._gesture_mode.set(loaded_mode)
        self._on_gesture_mode_changed()
        if 'window_duration' in data:
            self._gesture_window_duration.set(float(data['window_duration']))
        if 'use_phase' in data:
            self._gesture_use_phase.set(bool(data['use_phase']))
        if 'use_amplitude_response' in data:
            self._gesture_use_amplitude_response.set(bool(data['use_amplitude_response']))

        added = 0
        for label, vec in zip(loaded_labels, loaded_features):
            label_str = str(label)
            self._gesture_samples.append((label_str, vec.astype(np.float32)))
            if label_str not in self._gesture_labels_order:
                self._gesture_labels_order.append(label_str)
            added += 1

        self._gesture_update_summary()
        self._gesture_status.config(
            text=f'Loaded {added} samples from {os.path.basename(path)} — total {len(self._gesture_samples)}'
        )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _gesture_update_summary(self):
        """Update the text widget showing per-label sample counts."""
        counts: Dict[str, int] = {}
        for label, _ in self._gesture_samples:
            counts[label] = counts.get(label, 0) + 1

        mode = self._gesture_mode.get()
        if self._gesture_samples:
            dim = self._gesture_samples[0][1].shape[0]
        else:
            dim = '?'

        lines = [f'Mode: {mode}  |  Feature dim: {dim}  |  Total: {len(self._gesture_samples)} samples  |  Dropped: {self._gesture_dropped}']
        lines.append('')
        for label in self._gesture_labels_order:
            count = counts.get(label, 0)
            lines.append(f'  {label}: {count} samples')

        self._gesture_summary.config(state=tk.NORMAL)
        self._gesture_summary.delete('1.0', tk.END)
        self._gesture_summary.insert(tk.END, '\n'.join(lines))
        self._gesture_summary.config(state=tk.DISABLED)
