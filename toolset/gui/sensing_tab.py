import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional, Tuple
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from toolset.cs_utils.cs_subevent import SubeventResults
from toolset.cs_utils.cs_step import CSStepMode2, ToneQualityIndicator, ToneQualityIndicatorExtensionSlot
from toolset.gui.cs_theme import _Theme

# Fixed BLE CS channel set used for feature vector alignment (channels 2–78, excluding advertising channels 0/1/37/38/39)
_PHASE_CHANNELS = [ch for ch in range(2, 79) if ch not in (37, 38, 39)]
_N_PHASE = len(_PHASE_CHANNELS)
_CHANNEL_INDEX = {ch: i for i, ch in enumerate(_PHASE_CHANNELS)}

_LABEL_COLORS = [
    '#4e79a7', '#f28e2b', '#e15759', '#76b7b2',
    '#59a14f', '#edc948', '#b07aa1', '#ff9da7',
    '#9c755f', '#bab0ac',
]


def _sensing_drop_reason(
    initiator: Optional[SubeventResults],
    reflector: Optional[SubeventResults],
    phase_data: Optional[Dict[int, float]],
    rssi_ini: Optional[Dict[int, float]],
    rssi_ref: Optional[Dict[int, float]],
) -> Optional[str]:
    """Return a human-readable drop reason, or None if the sample is acceptable."""
    if initiator is None:
        return 'initiator subevent is None'
    if reflector is None:
        return 'reflector subevent is None'
    if not phase_data:
        return 'no phase slope data'
    if not rssi_ini:
        return 'no initiator RSSI data'
    if not rssi_ref:
        return 'no reflector RSSI data'

    bad_ini = _first_bad_tone(initiator)
    if bad_ini:
        return f'initiator {bad_ini}'
    bad_ref = _first_bad_tone(reflector)
    if bad_ref:
        return f'reflector {bad_ref}'

    emission_ini = _ext_slot_emission(initiator)
    if emission_ini:
        return f'initiator {emission_ini}'
    emission_ref = _ext_slot_emission(reflector)
    if emission_ref:
        return f'reflector {emission_ref}'

    return None


def _ext_slot_emission(subevent: SubeventResults, threshold: float = 20.0) -> Optional[str]:
    """Return description if any TONE_EXTENSION_NOT_EXPECTED slot has magnitude above threshold.

    A large magnitude in an extension slot indicates external RF emission on that channel.
    """
    for step in subevent.steps:
        if not isinstance(step, CSStepMode2):
            continue
        for tone in step.tones:
            if tone.quality_extension_slot != ToneQualityIndicatorExtensionSlot.TONE_EXTENSION_NOT_EXPECTED:
                continue
            mag = (tone.pct_i ** 2 + tone.pct_q ** 2) ** 0.5
            if mag > threshold:
                return f'ext slot emission on ch {step.channel}: mag={mag:.1f}'
    return None


def _first_bad_tone(subevent: SubeventResults) -> Optional[str]:
    """Return description when at least 1 bad tone is found, or None."""
    bad = []
    for step in subevent.steps:
        if not isinstance(step, CSStepMode2):
            continue
        for tone in step.tones:
            if tone.quality_extension_slot == ToneQualityIndicatorExtensionSlot.TONE_EXTENSION_NOT_EXPECTED:
                continue
            if tone.quality in (ToneQualityIndicator.TONE_QUALITY_MEDIUM,
                                ToneQualityIndicator.TONE_QUALITY_LOW):
                bad.append(f'ch {step.channel}={tone.quality.name}')
                if len(bad) >= 1:
                    return f'{len(bad)} bad tones: {", ".join(bad)}'
    return None


def _subevent_quality_ok(subevent: Optional[SubeventResults]) -> bool:
    """Return False if any mode-2 step has a MEDIUM or LOW tone quality."""
    if subevent is None:
        return False
    for step in subevent.steps:
        if not isinstance(step, CSStepMode2):
            continue
        for tone in step.tones:
            if tone.quality in (ToneQualityIndicator.TONE_QUALITY_MEDIUM,
                                ToneQualityIndicator.TONE_QUALITY_LOW):
                return False
    return True


def _build_feature_vector(
    phase_data: Optional[Dict[int, float]],
    rssi_ini: Optional[Dict[int, float]],
    rssi_ref: Optional[Dict[int, float]],
    use_phase: bool = True,
    use_rssi_ini: bool = True,
    use_rssi_ref: bool = True,
) -> Optional[np.ndarray]:
    """Build a fixed-length feature vector from per-channel dicts.

    Layout: [phase_ch2..ch78 (excl. adv), rssi_ini_ch2..ch78, rssi_ref_ch2..ch78]
    Missing channels are filled with 0. Sections can be disabled via use_* flags.
    """
    if not phase_data and not rssi_ini and not rssi_ref:
        return None

    vec = np.zeros(3 * _N_PHASE, dtype=np.float32)

    if phase_data and use_phase:
        channels = list(phase_data.keys())
        offset = phase_data[channels[0]]
        for ch in channels:
            idx = _CHANNEL_INDEX.get(ch)
            if idx is not None:
                vec[idx] = phase_data[ch] - offset

    if rssi_ini and use_rssi_ini:
        values = list(rssi_ini.values())
        offset = min(values)
        for ch, val in rssi_ini.items():
            idx = _CHANNEL_INDEX.get(ch)
            if idx is not None:
                vec[_N_PHASE + idx] = val - offset

    if rssi_ref and use_rssi_ref:
        values = list(rssi_ref.values())
        offset = min(values)
        for ch, val in rssi_ref.items():
            idx = _CHANNEL_INDEX.get(ch)
            if idx is not None:
                vec[2 * _N_PHASE + idx] = val - offset

    return vec


class SensingTabMixin:
    """Sensing tab: label recording and dimensionality-reduction scatter plot."""

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_sensing_tab(self, tab_frame: ttk.Frame):
        self._sensing_label_var = tk.StringVar(value='')
        self._sensing_recording = False

        # Stored data: list of (label, feature_vector)
        self._sensing_samples: List[Tuple[str, np.ndarray]] = []
        self._sensing_labels_order: List[str] = []   # insertion order
        self._sensing_dropped: int = 0

        # PCA transform for live projection: (mean, std, pca_center, Vt2)
        self._sensing_pca_transform: Optional[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = None
        self._sensing_live_artist = None

        # ---- controls row ----------------------------------------
        ctrl = ttk.Frame(tab_frame)
        ctrl.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 8))

        ttk.Label(ctrl, text='Label:').grid(row=0, column=0, sticky=tk.W)
        label_entry = ttk.Entry(ctrl, textvariable=self._sensing_label_var, width=20)
        label_entry.grid(row=0, column=1, sticky=tk.W, padx=(6, 0))

        self._sensing_record_btn = ttk.Button(ctrl, text='Start recording', command=self._on_sensing_record_toggle)
        self._sensing_record_btn.grid(row=0, column=2, padx=(12, 0))

        ttk.Button(ctrl, text='Add all loaded', command=self._on_sensing_add_all_loaded).grid(row=0, column=3, padx=(6, 0))
        ttk.Button(ctrl, text='Clear all', command=self._on_sensing_clear).grid(row=0, column=4, padx=(6, 0))
        ttk.Button(ctrl, text='Run PCA', command=self._on_sensing_run_pca).grid(row=0, column=5, padx=(6, 0))
        self._sensing_status = ttk.Label(ctrl, text='0 samples')
        self._sensing_status.grid(row=0, column=7, padx=(16, 0), sticky=tk.W)

        feat_frame = ttk.Frame(tab_frame)
        feat_frame.grid(row=1, column=0, sticky=tk.W, pady=(0, 4))
        ttk.Label(feat_frame, text='Features:').grid(row=0, column=0, sticky=tk.W)
        self._sensing_use_phase = tk.BooleanVar(value=True)
        self._sensing_use_rssi_ini = tk.BooleanVar(value=False)
        self._sensing_use_rssi_ref = tk.BooleanVar(value=False)
        ttk.Checkbutton(feat_frame, text='Phase', variable=self._sensing_use_phase).grid(row=0, column=1, padx=(8, 0))
        ttk.Checkbutton(feat_frame, text='RSSI ini', variable=self._sensing_use_rssi_ini).grid(row=0, column=2, padx=(4, 0))
        ttk.Checkbutton(feat_frame, text='RSSI ref', variable=self._sensing_use_rssi_ref).grid(row=0, column=3, padx=(4, 0))

        # ---- scatter plot ----------------------------------------
        self._sensing_fig = Figure(figsize=(7, 6), dpi=100)
        self._sensing_ax = self._sensing_fig.add_subplot(111)
        self._sensing_ax.set_title('Sensing space (run PCA)')
        self._apply_sensing_plot_theme()

        self._sensing_canvas = FigureCanvasTkAgg(self._sensing_fig, master=tab_frame)
        self._sensing_canvas.get_tk_widget().configure(bg=_Theme.PlotBackground)
        self._sensing_canvas.get_tk_widget().grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        tab_frame.rowconfigure(2, weight=1)
        tab_frame.columnconfigure(0, weight=1)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _apply_sensing_plot_theme(self):
        self._sensing_fig.patch.set_facecolor(_Theme.PlotBackground)
        self._sensing_ax.set_facecolor(_Theme.PlotBackground)
        self._sensing_ax.tick_params(colors=_Theme.PlotForeground, which='both')
        self._sensing_ax.xaxis.label.set_color(_Theme.PlotForeground)
        self._sensing_ax.yaxis.label.set_color(_Theme.PlotForeground)
        self._sensing_ax.title.set_color(_Theme.PlotForeground)
        for spine in self._sensing_ax.spines.values():
            spine.set_edgecolor(_Theme.Border)
        self._sensing_ax.grid(True, color=_Theme.PlotGridColor, alpha=0.4)

    # ------------------------------------------------------------------
    # Update (called whenever tab is active and data changes)
    # ------------------------------------------------------------------

    def _update_sensing_tab(self):
        if self._sensing_recording:
            self._sensing_capture_current()
        self._sensing_update_live_dot()

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------

    def _on_sensing_record_toggle(self):
        label = self._sensing_label_var.get().strip()
        if not self._sensing_recording:
            if not label:
                self._sensing_status.config(text='Enter a label first')
                return
            self._sensing_recording = True
            self._sensing_record_btn.config(text='Stop recording')
        else:
            self._sensing_recording = False
            self._sensing_record_btn.config(text='Start recording')
        self._sensing_status.config(text=f'{len(self._sensing_samples)} samples')

    def _on_sensing_clear(self):
        self._sensing_samples.clear()
        self._sensing_labels_order.clear()
        self._sensing_dropped = 0
        self._sensing_recording = False
        self._sensing_pca_transform = None
        self._sensing_live_artist = None
        self._sensing_record_btn.config(text='Start recording')
        self._sensing_status.config(text='0 samples')
        self._sensing_ax.cla()
        self._sensing_ax.set_title('Sensing space (run PCA)')
        self._apply_sensing_plot_theme()
        self._sensing_canvas.draw()

    def _on_sensing_run_pca(self):
        if len(self._sensing_samples) < 4:
            self._sensing_status.config(text='Need at least 4 samples')
            return

        labels = [s[0] for s in self._sensing_samples]
        X = np.stack([s[1] for s in self._sensing_samples])

        # Normalize: subtract mean, divide by std (per feature)
        mean = X.mean(axis=0)
        std = X.std(axis=0)
        std[std == 0] = 1.0
        X_norm = (X - mean) / std

        embedding = self._reduce(X_norm)

        self._sensing_ax.cla()
        self._apply_sensing_plot_theme()

        unique_labels = list(dict.fromkeys(labels))  # preserve insertion order
        for i, lbl in enumerate(unique_labels):
            mask = [l == lbl for l in labels]
            pts = embedding[mask]
            color = _LABEL_COLORS[i % len(_LABEL_COLORS)]
            self._sensing_ax.scatter(pts[:, 0], pts[:, 1], label=lbl, color=color, alpha=0.7, s=30)

        legend = self._sensing_ax.legend()
        legend.get_frame().set_facecolor(_Theme.PlotBackground)
        legend.get_frame().set_edgecolor(_Theme.Border)
        for text in legend.get_texts():
            text.set_color(_Theme.PlotForeground)

        self._sensing_ax.set_title(f'PCA — {len(self._sensing_samples)} samples, {len(unique_labels)} labels')
        self._sensing_ax.set_xlabel('Component 1')
        self._sensing_ax.set_ylabel('Component 2')
        self._apply_sensing_plot_theme()

        # Add live-dot artist (empty until next subevent arrives)
        self._sensing_live_artist = self._sensing_ax.scatter(
            [], [], marker='*', s=250, color='white',
            edgecolors='black', linewidths=0.8, zorder=6, label='_nolegend_'
        )

        # Store transform: (feature mean, feature std, pca center, Vt top-2)
        X_norm_center = X_norm.mean(axis=0)
        _, _, Vt_full = np.linalg.svd(X_norm - X_norm_center, full_matrices=False)
        self._sensing_pca_transform = (mean, std, X_norm_center, Vt_full[:2])

        self._sensing_canvas.draw()
        self._sensing_status.config(text=f'{len(self._sensing_samples)} samples — PCA done')

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _on_sensing_add_all_loaded(self):
        label = self._sensing_label_var.get().strip()
        if not label:
            self._sensing_status.config(text='Enter a label first')
            return

        counters = sorted(self.phase_slope_map.keys())
        added = 0
        dropped = 0
        for counter in counters:
            initiator = self.initiator_map.get(counter)
            reflector = self.reflector_map.get(counter)
            phase_data = self.phase_slope_map.get(counter)
            rssi_ini = self.rssi_ini_map.get(counter)
            rssi_ref = self.rssi_ref_map.get(counter)

            drop_reason = _sensing_drop_reason(initiator, reflector, phase_data, rssi_ini, rssi_ref)
            if drop_reason:
                print(f'[SENSING] dropped subevent #{counter}: {drop_reason}')
                dropped += 1
                continue

            vec = _build_feature_vector(
                phase_data, rssi_ini, rssi_ref,
                use_phase=self._sensing_use_phase.get(),
                use_rssi_ini=self._sensing_use_rssi_ini.get(),
                use_rssi_ref=self._sensing_use_rssi_ref.get(),
            )
            self._sensing_samples.append((label, vec))
            if label not in self._sensing_labels_order:
                self._sensing_labels_order.append(label)
            added += 1

        self._sensing_dropped += dropped
        print(f'[SENSING] add all loaded: added={added}, dropped={dropped}, label="{label}"')
        self._sensing_status.config(text=f'{len(self._sensing_samples)} samples — added {added}, dropped {dropped}')

    def _sensing_capture_current(self):
        drop_reason = _sensing_drop_reason(
            self._current_initiator,
            self._current_reflector,
            self._current_phase_slope_data,
            self._current_rssi_ini_data,
            self._current_rssi_ref_data,
        )
        if drop_reason:
            self._sensing_dropped += 1
            print(f'[SENSING] dropped subevent #{self._current_counter} (dropped={self._sensing_dropped}, kept={len(self._sensing_samples)}): {drop_reason}')
            self._sensing_status.config(
                text=f'{len(self._sensing_samples)} samples — dropped {self._sensing_dropped}: {drop_reason}'
            )
            return

        vec = _build_feature_vector(
            self._current_phase_slope_data,
            self._current_rssi_ini_data,
            self._current_rssi_ref_data,
            use_phase=self._sensing_use_phase.get(),
            use_rssi_ini=self._sensing_use_rssi_ini.get(),
            use_rssi_ref=self._sensing_use_rssi_ref.get(),
        )

        label = self._sensing_label_var.get().strip()
        self._sensing_samples.append((label, vec))
        if label not in self._sensing_labels_order:
            self._sensing_labels_order.append(label)
        self._sensing_status.config(text=f'{len(self._sensing_samples)} samples  [{label}]')

    def _sensing_update_live_dot(self):
        """Project the current subevent into PCA space and move the live-dot marker."""
        if self._sensing_pca_transform is None or self._sensing_live_artist is None:
            return

        phase_data = getattr(self, '_current_phase_slope_data', None)
        rssi_ini = getattr(self, '_current_rssi_ini_data', None)
        rssi_ref = getattr(self, '_current_rssi_ref_data', None)

        vec = _build_feature_vector(
            phase_data, rssi_ini, rssi_ref,
            use_phase=self._sensing_use_phase.get(),
            use_rssi_ini=self._sensing_use_rssi_ini.get(),
            use_rssi_ref=self._sensing_use_rssi_ref.get(),
        )
        if vec is None:
            return

        mean, std, pca_center, Vt2 = self._sensing_pca_transform
        vec_norm = (vec - mean) / std
        vec_centered = vec_norm - pca_center
        pt = vec_centered @ Vt2.T  # shape (2,)

        self._sensing_live_artist.set_offsets([[pt[0], pt[1]]])

        # Expand axes limits if the live dot falls outside the current view
        xmin, xmax = self._sensing_ax.get_xlim()
        ymin, ymax = self._sensing_ax.get_ylim()
        x_margin = (xmax - xmin) * 0.1 or 0.1
        y_margin = (ymax - ymin) * 0.1 or 0.1
        changed = False
        if pt[0] < xmin + x_margin:
            xmin = pt[0] - x_margin
            changed = True
        if pt[0] > xmax - x_margin:
            xmax = pt[0] + x_margin
            changed = True
        if pt[1] < ymin + y_margin:
            ymin = pt[1] - y_margin
            changed = True
        if pt[1] > ymax - y_margin:
            ymax = pt[1] + y_margin
            changed = True
        if changed:
            self._sensing_ax.set_xlim(xmin, xmax)
            self._sensing_ax.set_ylim(ymin, ymax)

        self._sensing_canvas.draw_idle()

    @staticmethod
    def _reduce(X: np.ndarray) -> np.ndarray:
        X_centered = X - X.mean(axis=0)
        _, _, Vt = np.linalg.svd(X_centered, full_matrices=False)
        return X_centered @ Vt[:2].T
