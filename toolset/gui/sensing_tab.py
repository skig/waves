import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional, Tuple
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from toolset.cs_utils.cs_subevent import SubeventResults
from toolset.cs_utils.cs_step import CSStepMode2, ToneQualityIndicator, ToneQualityIndicatorExtensionSlot
from toolset.gui.cs_theme import _Theme
from toolset.processing.sensing_features import (
    PHASE_CHANNELS, N_PHASE, CHANNEL_INDEX,
    sensing_drop_reason, ext_slot_emission, first_bad_tone,
    subevent_quality_ok, build_feature_vector,
)

# Keep underscore-prefixed aliases for backward compatibility within this module
_PHASE_CHANNELS = PHASE_CHANNELS
_N_PHASE = N_PHASE
_CHANNEL_INDEX = CHANNEL_INDEX
_sensing_drop_reason = sensing_drop_reason
_ext_slot_emission = ext_slot_emission
_first_bad_tone = first_bad_tone
_subevent_quality_ok = subevent_quality_ok
_build_feature_vector = build_feature_vector

_LABEL_COLORS = [
    '#4e79a7', '#f28e2b', '#e15759', '#76b7b2',
    '#59a14f', '#edc948', '#b07aa1', '#ff9da7',
    '#9c755f', '#bab0ac',
]


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

        # Projection transform for live dot: (mean, std, center, W2) where W2 has shape (2, n_features)
        # Shared by PCA and LDA; projection = (x_norm - center) @ W2.T
        self._sensing_projection_transform: Optional[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = None
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
        ttk.Button(ctrl, text='Run LDA', command=self._on_sensing_run_lda).grid(row=0, column=6, padx=(6, 0))
        self._sensing_status = ttk.Label(ctrl, text='0 samples')
        self._sensing_status.grid(row=0, column=7, padx=(16, 0), sticky=tk.W)

        feat_frame = ttk.Frame(tab_frame)
        feat_frame.grid(row=1, column=0, sticky=tk.W, pady=(0, 4))
        ttk.Label(feat_frame, text='Features:').grid(row=0, column=0, sticky=tk.W)
        self._sensing_use_phase = tk.BooleanVar(value=True)
        self._sensing_use_amplitude_response = tk.BooleanVar(value=False)
        ttk.Checkbutton(feat_frame, text='Phase', variable=self._sensing_use_phase).grid(row=0, column=1, padx=(8, 0))
        ttk.Checkbutton(feat_frame, text='Ampl. response', variable=self._sensing_use_amplitude_response).grid(row=0, column=2, padx=(4, 0))

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
        # self._sensing_update_live_dot()

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
        self._sensing_projection_transform = None
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

        mean = X.mean(axis=0)
        std = X.std(axis=0)
        std[std == 0] = 1.0
        X_norm = (X - mean) / std

        center = X_norm.mean(axis=0)
        _, _, Vt = np.linalg.svd(X_norm - center, full_matrices=False)
        embedding = (X_norm - center) @ Vt[:2].T

        unique_labels = list(dict.fromkeys(labels))
        title = f'PCA — {len(self._sensing_samples)} samples, {len(unique_labels)} labels'
        self._sensing_plot_embedding(embedding, labels, unique_labels, title, mean, std, center, Vt[:2])
        self._sensing_status.config(text=f'{len(self._sensing_samples)} samples — PCA done')

    def _on_sensing_run_lda(self):
        if len(self._sensing_samples) < 4:
            self._sensing_status.config(text='Need at least 4 samples')
            return

        labels = [s[0] for s in self._sensing_samples]
        unique_labels = list(dict.fromkeys(labels))
        if len(unique_labels) < 2:
            self._sensing_status.config(text='Need at least 2 labels for LDA')
            return

        X = np.stack([s[1] for s in self._sensing_samples])
        mean = X.mean(axis=0)
        std = X.std(axis=0)
        std[std == 0] = 1.0
        X_norm = (X - mean) / std

        W = self._fit_lda(X_norm, labels)
        if W is None:
            self._sensing_status.config(text='LDA failed — try more samples')
            return

        center = X_norm.mean(axis=0)
        embedding = (X_norm - center) @ W  # (n, 2)

        title = f'LDA — {len(self._sensing_samples)} samples, {len(unique_labels)} labels'
        self._sensing_plot_embedding(embedding, labels, unique_labels, title, mean, std, center, W.T)
        self._sensing_status.config(text=f'{len(self._sensing_samples)} samples — LDA done')

    def _sensing_plot_embedding(
        self,
        embedding: np.ndarray,
        labels: list,
        unique_labels: list,
        title: str,
        mean: np.ndarray,
        std: np.ndarray,
        center: np.ndarray,
        W2: np.ndarray,
    ):
        """Render a 2-D embedding on the scatter plot and store the projection transform."""
        self._sensing_ax.cla()
        self._apply_sensing_plot_theme()

        for i, lbl in enumerate(unique_labels):
            mask = np.array([l == lbl for l in labels])
            pts = embedding[mask]
            color = _LABEL_COLORS[i % len(_LABEL_COLORS)]
            self._sensing_ax.scatter(pts[:, 0], pts[:, 1], label=lbl, color=color, alpha=0.7, s=30)

        legend = self._sensing_ax.legend()
        legend.get_frame().set_facecolor(_Theme.PlotBackground)
        legend.get_frame().set_edgecolor(_Theme.Border)
        for text in legend.get_texts():
            text.set_color(_Theme.PlotForeground)

        self._sensing_ax.set_title(title)
        self._sensing_ax.set_xlabel('Component 1')
        self._sensing_ax.set_ylabel('Component 2')
        self._apply_sensing_plot_theme()

        # Live-dot artist (empty until next subevent arrives)
        self._sensing_live_artist = self._sensing_ax.scatter(
            [], [], marker='*', s=250, color='white',
            edgecolors='black', linewidths=0.8, zorder=6, label='_nolegend_'
        )
        # Store transform: projection of x_norm -> (x_norm - center) @ W2.T
        self._sensing_projection_transform = (mean, std, center, W2)
        self._sensing_canvas.draw()

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
            amplitude_response = self.amplitude_response_map.get(counter)

            drop_reason = _sensing_drop_reason(initiator, reflector, phase_data, amplitude_response)
            if drop_reason:
                print(f'[SENSING] dropped subevent #{counter}: {drop_reason}')
                dropped += 1
                continue

            vec = _build_feature_vector(
                phase_data, amplitude_response,
                use_phase=self._sensing_use_phase.get(),
                use_amplitude_response=self._sensing_use_amplitude_response.get(),
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
            self._current_amplitude_response_data,
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
            self._current_amplitude_response_data,
            use_phase=self._sensing_use_phase.get(),
            use_amplitude_response=self._sensing_use_amplitude_response.get(),
        )

        label = self._sensing_label_var.get().strip()
        self._sensing_samples.append((label, vec))
        if label not in self._sensing_labels_order:
            self._sensing_labels_order.append(label)
        self._sensing_status.config(text=f'{len(self._sensing_samples)} samples  [{label}]')

    def _sensing_update_live_dot(self):
        """Project the current subevent into PCA space and move the live-dot marker."""
        if self._sensing_projection_transform is None or self._sensing_live_artist is None:
            return

        phase_data = getattr(self, '_current_phase_slope_data', None)
        amplitude_response = getattr(self, '_current_amplitude_response_data', None)

        vec = _build_feature_vector(
            phase_data, amplitude_response,
            use_phase=self._sensing_use_phase.get(),
            use_amplitude_response=self._sensing_use_amplitude_response.get(),
        )
        if vec is None:
            return

        mean, std, center, W2 = self._sensing_projection_transform
        vec_norm = (vec - mean) / std
        vec_centered = vec_norm - center
        pt = vec_centered @ W2.T  # shape (2,)

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
    def _fit_lda(X_norm: np.ndarray, labels: list) -> Optional[np.ndarray]:
        """LDA via PCA pre-whitening + scatter matrices.

        Returns W of shape (n_features, 2) so that the 2-D projection of a
        normalised sample x is  (x - center) @ W,  or None on failure.
        Pre-whitening with PCA avoids the singular within-class scatter matrix
        that occurs when the number of features exceeds the number of samples.
        """
        unique = list(dict.fromkeys(labels))
        n, d = X_norm.shape

        # Step 1: PCA whitening to a safe dimensionality
        center = X_norm.mean(axis=0)
        X_c = (X_norm - center).astype(np.float64)
        _, _, Vt_pca = np.linalg.svd(X_c, full_matrices=False)
        n_pca = min(n - 1, d)
        pca_W = Vt_pca[:n_pca].T    # (d, n_pca)
        X_pca = X_c @ pca_W         # (n, n_pca)

        # Step 2: within-class (S_W) and between-class (S_B) scatter in PCA space
        p = X_pca.shape[1]
        overall_mean = X_pca.mean(axis=0)
        S_W = np.zeros((p, p), dtype=np.float64)
        S_B = np.zeros((p, p), dtype=np.float64)
        for lbl in unique:
            mask = np.array([l == lbl for l in labels])
            X_cl = X_pca[mask]
            n_c = len(X_cl)
            mean_c = X_cl.mean(axis=0)
            S_W += (X_cl - mean_c).T @ (X_cl - mean_c)
            dm = (mean_c - overall_mean).reshape(-1, 1)
            S_B += n_c * (dm @ dm.T)

        trace = np.trace(S_W)
        S_W += np.eye(p) * (trace / p * 1e-6 + 1e-10)  # mild regularisation

        try:
            M = np.linalg.solve(S_W, S_B)
            vals, vecs = np.linalg.eig(M)
            vals, vecs = vals.real, vecs.real
            idx = np.argsort(vals)[::-1]
            W_lda = vecs[:, idx[:2]]   # (n_pca, 2)
        except np.linalg.LinAlgError:
            return None

        return pca_W @ W_lda           # (d, 2)

    @staticmethod
    def _reduce(X: np.ndarray) -> np.ndarray:
        X_centered = X - X.mean(axis=0)
        _, _, Vt = np.linalg.svd(X_centered, full_matrices=False)
        return X_centered @ Vt[:2].T
