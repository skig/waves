import os
import tkinter as tk
from tkinter import ttk, filedialog
from typing import Dict, List, Optional, Tuple
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from toolset.processing.sensing_features import (
    build_feature_vector, sensing_drop_reason,
)
from toolset.gui.cs_theme import _Theme

_DATASETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'datasets')
_MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'models')

# Fraction of samples treated as outliers per label by LocalOutlierFactor.
# Raise to remove more aggressively (e.g. 0.1 = ~10%), lower to be more conservative.
_LOF_CONTAMINATION = 0.05


class GestureTabMixin:
    """Gesture tab: data collection, training, and real-time recognition."""

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_gesture_tab(self, tab_frame: ttk.Frame):
        self._gesture_label_var = tk.StringVar(value='')
        self._gesture_recording = False
        self._gesture_static_target: int = 0
        self._gesture_static_collected: int = 0

        # Stored data: list of (label, feature_vector)
        self._gesture_samples: List[Tuple[str, np.ndarray]] = []
        self._gesture_labels_order: List[str] = []
        self._gesture_dropped: int = 0

        self._gesture_static_count = tk.IntVar(value=1)

        # Trained model (sklearn Pipeline or None)
        self._gesture_pipeline = None
        self._gesture_classes: List[str] = []

        # Live recognition state
        self._gesture_recognizing = False

        # Use-feature flags (same as sensing tab)
        self._gesture_use_phase = tk.BooleanVar(value=True)
        self._gesture_use_amplitude_response = tk.BooleanVar(value=True)

        # Plot view toggle: 'pca' or 'confusion'
        self._gesture_plot_view: str = 'pca'
        self._gesture_pca_dirty: bool = False
        self._gesture_pca_transform: Optional[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = None
        self._gesture_live_artist = None
        self._gesture_last_cm: Optional[Tuple[np.ndarray, List[str]]] = None  # cached (cm, labels)
        self._gesture_proba_bars = None
        self._gesture_pre_recognition_view: str = 'pca'

        # ---- row 0: recording options ----
        opts_frame = ttk.Frame(tab_frame)
        opts_frame.grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        ttk.Label(opts_frame, text='Count:').grid(row=0, column=0, sticky=tk.W)
        self._gesture_count_spin = ttk.Spinbox(
            opts_frame, from_=1, to=1000, increment=1,
            textvariable=self._gesture_static_count, width=5,
        )
        self._gesture_count_spin.grid(row=0, column=1, padx=(4, 0))

        # Feature checkboxes
        ttk.Label(opts_frame, text='Features:').grid(row=0, column=2, padx=(20, 0))
        ttk.Checkbutton(opts_frame, text='Phase', variable=self._gesture_use_phase).grid(row=0, column=3, padx=(4, 0))
        ttk.Checkbutton(opts_frame, text='Ampl. response', variable=self._gesture_use_amplitude_response).grid(row=0, column=4, padx=(4, 0))

        # ---- row 1: recording controls ----
        ctrl = ttk.Frame(tab_frame)
        ctrl.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 8))

        ttk.Label(ctrl, text='Label:').grid(row=0, column=0, sticky=tk.W)
        label_entry = ttk.Entry(ctrl, textvariable=self._gesture_label_var, width=20)
        label_entry.grid(row=0, column=1, sticky=tk.W, padx=(6, 0))

        self._gesture_record_btn = ttk.Button(ctrl, text='Record sample', command=self._on_gesture_record)
        self._gesture_record_btn.grid(row=0, column=2, padx=(12, 0))

        ttk.Button(ctrl, text='Clear all', command=self._on_gesture_clear).grid(row=0, column=3, padx=(6, 0))
        ttk.Button(ctrl, text='Remove outliers', command=self._on_gesture_remove_outliers).grid(row=0, column=4, padx=(6, 0))
        ttk.Button(ctrl, text='Save dataset', command=self._on_gesture_save_dataset).grid(row=0, column=5, padx=(6, 0))
        ttk.Button(ctrl, text='Load dataset', command=self._on_gesture_load_dataset).grid(row=0, column=6, padx=(6, 0))

        self._gesture_status = ttk.Label(ctrl, text='0 samples')
        self._gesture_status.grid(row=0, column=7, padx=(16, 0), sticky=tk.W)

        # ---- row 2: sample summary ----
        self._gesture_summary = tk.Text(
            tab_frame, height=6, wrap=tk.WORD, state=tk.DISABLED,
            bg=_Theme.AltBackground, fg=_Theme.Foreground,
            relief=tk.FLAT, padx=8, pady=4,
        )
        self._gesture_summary.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 8))

        # ---- row 3: training controls ----
        train_frame = ttk.Frame(tab_frame)
        train_frame.grid(row=3, column=0, sticky=tk.W, pady=(0, 4))
        ttk.Button(train_frame, text='Train', command=self._on_gesture_train).grid(row=0, column=0)
        ttk.Button(train_frame, text='Save model', command=self._on_gesture_save_model).grid(row=0, column=1, padx=(6, 0))
        ttk.Button(train_frame, text='Load model', command=self._on_gesture_load_model).grid(row=0, column=2, padx=(6, 0))
        self._gesture_recognize_btn = ttk.Button(train_frame, text='Start recognition', command=self._on_gesture_toggle_recognition)
        self._gesture_recognize_btn.grid(row=0, column=3, padx=(6, 0))
        self._gesture_train_status = ttk.Label(train_frame, text='')
        self._gesture_train_status.grid(row=0, column=4, padx=(12, 0), sticky=tk.W)

        # ---- row 4: plot view toggle ----
        plot_toggle_frame = ttk.Frame(tab_frame)
        plot_toggle_frame.grid(row=4, column=0, sticky=tk.W, pady=(0, 4))
        self._gesture_pca_btn = ttk.Button(
            plot_toggle_frame, text='PCA', command=lambda: self._gesture_switch_plot_view('pca'),
        )
        self._gesture_pca_btn.grid(row=0, column=0)
        self._gesture_cm_btn = ttk.Button(
            plot_toggle_frame, text='Confusion Matrix',
            command=lambda: self._gesture_switch_plot_view('confusion'),
            state=tk.DISABLED,
        )
        self._gesture_cm_btn.grid(row=0, column=1, padx=(6, 0))

        # ---- row 5: live prediction display ----
        pred_frame = ttk.Frame(tab_frame)
        pred_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        pred_frame.columnconfigure(0, weight=1)

        self._gesture_pred_label = tk.Label(
            pred_frame, text='', font=('TkDefaultFont', 48, 'bold'),
            bg=_Theme.AltBackground, fg=_Theme.Foreground,
            anchor=tk.CENTER, height=2,
        )
        self._gesture_pred_label.grid(row=0, column=0, sticky=(tk.W, tk.E))

        # ---- row 6: plot area (PCA scatter / confusion matrix) ----
        self._gesture_fig = Figure(figsize=(5, 4), dpi=100)
        self._gesture_ax = self._gesture_fig.add_subplot(111)
        self._gesture_ax.set_visible(False)
        self._apply_gesture_plot_theme()

        self._gesture_canvas = FigureCanvasTkAgg(self._gesture_fig, master=tab_frame)
        self._gesture_canvas.get_tk_widget().configure(bg=_Theme.PlotBackground)
        self._gesture_canvas.get_tk_widget().grid(row=6, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        tab_frame.rowconfigure(6, weight=1)
        tab_frame.columnconfigure(0, weight=1)

    # ------------------------------------------------------------------
    # Update (called whenever tab is active and data changes)
    # ------------------------------------------------------------------

    def _update_gesture_tab(self):
        if self._gesture_recording:
            self._gesture_capture_static_batch()
        elif self._gesture_recognizing:
            self._gesture_predict_current()

        # Deferred PCA recompute (e.g. after batch recording finishes)
        if self._gesture_pca_dirty and not self._gesture_recording:
            self._gesture_pca_dirty = False
            if self._gesture_plot_view == 'pca':
                self._gesture_draw_pca()

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def _on_gesture_record(self):
        label = self._gesture_label_var.get().strip()
        if not label:
            self._gesture_status.config(text='Enter a label first')
            return

        target = self._gesture_static_count.get()
        if target <= 1:
            self._gesture_record_static(label)
        else:
            if self._gesture_recording:
                self._gesture_stop_recording()
            else:
                self._gesture_start_static_batch(label, target)

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
        self._gesture_notify_samples_changed()
        self._gesture_status.config(text=f'{len(self._gesture_samples)} samples — recorded static [{label}]')

    def _gesture_start_static_batch(self, label: str, target: int):
        """Begin auto-collecting static samples until target count is reached."""
        self._gesture_recording = True
        self._gesture_static_target = target
        self._gesture_static_collected = 0
        self._gesture_record_btn.config(text='Stop recording')
        self._gesture_status.config(text=f'Collecting 0/{target} static samples [{label}]...')

    def _gesture_capture_static_batch(self):
        """Auto-capture one static sample per update call during batch collection."""
        label = self._gesture_label_var.get().strip()
        if not label:
            self._gesture_stop_recording()
            return

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
        if vec is None:
            return

        self._gesture_samples.append((label, vec))
        if label not in self._gesture_labels_order:
            self._gesture_labels_order.append(label)
        self._gesture_static_collected += 1

        target = self._gesture_static_target
        self._gesture_status.config(
            text=f'Collecting {self._gesture_static_collected}/{target} static samples [{label}]...'
        )

        if self._gesture_static_collected >= target:
            self._gesture_recording = False
            self._gesture_record_btn.config(text='Record sample')
            self._gesture_update_summary()
            self._gesture_pca_dirty = True
            self._gesture_status.config(
                text=f'{len(self._gesture_samples)} samples — collected {self._gesture_static_collected} static [{label}]'
            )

    def _gesture_stop_recording(self):
        """Stop batch recording."""
        self._gesture_recording = False
        self._gesture_record_btn.config(text='Record sample')
        self._gesture_update_summary()
        self._gesture_pca_dirty = True
        self._gesture_status.config(
            text=f'{len(self._gesture_samples)} samples — recording stopped'
        )

    # ------------------------------------------------------------------
    # Outlier removal
    # ------------------------------------------------------------------

    def _on_gesture_remove_outliers(self):
        from sklearn.neighbors import LocalOutlierFactor

        if not self._gesture_samples:
            self._gesture_status.config(text='No samples to filter')
            return

        # Group indices by label
        label_indices: Dict[str, List[int]] = {}
        for i, (lbl, _) in enumerate(self._gesture_samples):
            label_indices.setdefault(lbl, []).append(i)

        _MIN_SAMPLES = 5  # LOF needs enough neighbours to be meaningful
        keep = [True] * len(self._gesture_samples)

        for lbl, indices in label_indices.items():
            if len(indices) < _MIN_SAMPLES:
                continue

            X = np.stack([self._gesture_samples[i][1] for i in indices])
            lof = LocalOutlierFactor(n_neighbors=min(20, len(indices) - 1),
                                     contamination=_LOF_CONTAMINATION)
            preds = lof.fit_predict(X)  # -1 = outlier, 1 = inlier
            for idx, pred in zip(indices, preds):
                if pred == -1:
                    keep[idx] = False

        self._gesture_samples = [s for s, k in zip(self._gesture_samples, keep) if k]
        # Rebuild label order, dropping labels that lost all their samples
        remaining_labels = {s[0] for s in self._gesture_samples}
        self._gesture_labels_order = [l for l in self._gesture_labels_order if l in remaining_labels]

        total_before = len(keep)
        total_removed = keep.count(False)
        pct = total_removed / total_before * 100 if total_before else 0
        self._gesture_update_summary()
        self._gesture_notify_samples_changed()
        self._gesture_status.config(
            text=f'Removed {total_removed} outliers ({pct:.1f}%) — {len(self._gesture_samples)} samples remain'
        )

    # ------------------------------------------------------------------
    # Clear
    # ------------------------------------------------------------------

    def _on_gesture_clear(self):
        self._gesture_samples.clear()
        self._gesture_labels_order.clear()
        self._gesture_dropped = 0
        self._gesture_recording = False
        self._gesture_static_target = 0
        self._gesture_static_collected = 0
        self._gesture_pipeline = None
        self._gesture_classes.clear()
        self._gesture_pca_transform = None
        self._gesture_live_artist = None
        self._gesture_last_cm = None
        self._gesture_proba_bars = None
        self._gesture_pca_dirty = False
        self._gesture_plot_view = 'pca'
        self._gesture_stop_recognition()
        self._gesture_record_btn.config(text='Record sample')
        self._gesture_status.config(text='0 samples')
        self._gesture_train_status.config(text='')
        self._gesture_cm_btn.config(state=tk.DISABLED)
        self._gesture_ax.cla()
        self._gesture_ax.set_visible(False)
        self._apply_gesture_plot_theme()
        self._gesture_canvas.draw()
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

        loaded_labels = data['labels']
        loaded_features = data['features']

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
        self._gesture_notify_samples_changed()
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

        if self._gesture_samples:
            dim = self._gesture_samples[0][1].shape[0]
        else:
            dim = '?'

        lines = [f'Feature dim: {dim}  |  Total: {len(self._gesture_samples)} samples  |  Dropped: {self._gesture_dropped}']
        lines.append('')
        for label in self._gesture_labels_order:
            count = counts.get(label, 0)
            lines.append(f'  {label}: {count} samples')

        self._gesture_summary.config(state=tk.NORMAL)
        self._gesture_summary.delete('1.0', tk.END)
        self._gesture_summary.insert(tk.END, '\n'.join(lines))
        self._gesture_summary.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Plot theme
    # ------------------------------------------------------------------

    def _apply_gesture_plot_theme(self):
        self._gesture_fig.patch.set_facecolor(_Theme.PlotBackground)
        self._gesture_ax.set_facecolor(_Theme.PlotBackground)
        self._gesture_ax.tick_params(colors=_Theme.PlotForeground, which='both')
        self._gesture_ax.xaxis.label.set_color(_Theme.PlotForeground)
        self._gesture_ax.yaxis.label.set_color(_Theme.PlotForeground)
        self._gesture_ax.title.set_color(_Theme.PlotForeground)
        for spine in self._gesture_ax.spines.values():
            spine.set_edgecolor(_Theme.Border)

    # ------------------------------------------------------------------
    # Plot view toggle (PCA / Confusion Matrix)
    # ------------------------------------------------------------------

    _LABEL_COLORS = [
        '#4e79a7', '#f28e2b', '#e15759', '#76b7b2',
        '#59a14f', '#edc948', '#b07aa1', '#ff9da7',
        '#9c755f', '#bab0ac',
    ]

    def _gesture_switch_plot_view(self, view: str):
        """Toggle between 'pca' and 'confusion' plot views."""
        self._gesture_plot_view = view
        if view == 'pca':
            self._gesture_draw_pca()
        elif view == 'confusion':
            self._gesture_redraw_confusion_matrix()

    def _gesture_notify_samples_changed(self):
        """Called whenever samples are added or loaded. Auto-recomputes PCA if active."""
        if self._gesture_plot_view == 'pca' and not self._gesture_recording:
            self._gesture_draw_pca()
        else:
            self._gesture_pca_dirty = True

    def _gesture_draw_pca(self):
        """Compute PCA on current samples and render scatter plot."""
        ax = self._gesture_ax
        ax.cla()

        if len(self._gesture_samples) < 2:
            ax.set_visible(False)
            self._apply_gesture_plot_theme()
            self._gesture_pca_transform = None
            self._gesture_live_artist = None
            self._gesture_canvas.draw()
            return

        ax.set_visible(True)
        self._apply_gesture_plot_theme()
        ax.grid(True, color=_Theme.PlotGridColor, alpha=0.4)

        labels = [s[0] for s in self._gesture_samples]
        X = np.stack([s[1] for s in self._gesture_samples])

        mean = X.mean(axis=0)
        std = X.std(axis=0)
        std[std == 0] = 1.0
        X_norm = (X - mean) / std

        center = X_norm.mean(axis=0)
        X_centered = X_norm - center
        _, _, Vt = np.linalg.svd(X_centered, full_matrices=False)
        W2 = Vt[:2]  # (2, n_features)
        embedding = X_centered @ W2.T  # (n_samples, 2)

        unique_labels = list(dict.fromkeys(labels))
        for i, lbl in enumerate(unique_labels):
            mask = np.array([l == lbl for l in labels])
            pts = embedding[mask]
            color = self._LABEL_COLORS[i % len(self._LABEL_COLORS)]
            ax.scatter(pts[:, 0], pts[:, 1], label=lbl, color=color, alpha=0.7, s=30)

        legend = ax.legend()
        legend.get_frame().set_facecolor(_Theme.PlotBackground)
        legend.get_frame().set_edgecolor(_Theme.Border)
        for text in legend.get_texts():
            text.set_color(_Theme.PlotForeground)

        n_labels = len(unique_labels)
        ax.set_title(f'PCA — {len(self._gesture_samples)} samples, {n_labels} labels')
        ax.set_xlabel('Component 1')
        ax.set_ylabel('Component 2')

        # Live-dot artist (empty until recognition feeds it)
        self._gesture_live_artist = ax.scatter(
            [], [], marker='*', s=250, color='white',
            edgecolors='black', linewidths=0.8, zorder=6, label='_nolegend_',
        )

        # Store transform for live projection
        self._gesture_pca_transform = (mean, std, center, W2)

        self._gesture_fig.tight_layout()
        self._gesture_canvas.draw()

    def _gesture_update_live_dot(self, feature_vec: np.ndarray):
        """Project a feature vector into PCA space and update the live-dot marker."""
        if self._gesture_pca_transform is None or self._gesture_live_artist is None:
            return
        if self._gesture_plot_view != 'pca':
            return

        mean, std, center, W2 = self._gesture_pca_transform
        vec_norm = (feature_vec - mean) / std
        pt = (vec_norm - center) @ W2.T  # shape (2,)

        self._gesture_live_artist.set_offsets([[pt[0], pt[1]]])
        self._gesture_canvas.draw_idle()

    def _gesture_init_proba_chart(self):
        """Draw a vertical bar chart for live probability display."""
        ax = self._gesture_ax
        ax.cla()
        ax.set_visible(True)
        self._apply_gesture_plot_theme()

        classes = self._gesture_classes
        n = len(classes)
        x_pos = np.arange(n)
        colors = [self._LABEL_COLORS[i % len(self._LABEL_COLORS)] for i in range(n)]

        bars = ax.bar(x_pos, np.zeros(n), align='center', color=colors, alpha=0.85)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(classes, rotation=30, ha='right')
        ax.set_ylim(0, 1)
        ax.set_ylabel('Probability')
        ax.set_title('Live recognition probabilities')
        ax.axhline(y=0.5, color=_Theme.Border, linestyle='--', alpha=0.5, linewidth=1)
        ax.grid(True, axis='y', color=_Theme.PlotGridColor, alpha=0.4)

        self._gesture_proba_bars = bars
        self._gesture_fig.tight_layout()
        self._gesture_canvas.draw()

    def _gesture_update_proba_bars(self, proba: np.ndarray):
        """Update bar heights with the latest class probabilities (fast path)."""
        if self._gesture_proba_bars is None or self._gesture_plot_view != 'proba':
            return
        for bar, p in zip(self._gesture_proba_bars, proba):
            bar.set_height(p)
        self._gesture_canvas.draw_idle()

    def _gesture_redraw_confusion_matrix(self):
        """Redraw the cached confusion matrix (if any)."""
        if self._gesture_last_cm is None:
            return
        cm, labels = self._gesture_last_cm
        self._gesture_plot_confusion_matrix(cm, labels)

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def _on_gesture_train(self):
        from sklearn.svm import SVC
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline
        from sklearn.model_selection import StratifiedKFold, cross_val_score, cross_val_predict
        from sklearn.metrics import confusion_matrix

        # Validate we have enough data
        labels = [s[0] for s in self._gesture_samples]
        unique_labels = list(dict.fromkeys(labels))
        if len(unique_labels) < 2:
            self._gesture_train_status.config(text='Need at least 2 different labels')
            return

        label_counts = {}
        for lbl in labels:
            label_counts[lbl] = label_counts.get(lbl, 0) + 1
        too_few = [lbl for lbl, cnt in label_counts.items() if cnt < 3]
        if too_few:
            self._gesture_train_status.config(
                text=f'Need ≥3 samples per label. Too few: {", ".join(too_few)}'
            )
            return

        X = np.stack([s[1] for s in self._gesture_samples])
        y = np.array(labels)

        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('svc', SVC(kernel='rbf', probability=True)),
        ])

        # Cross-validation
        n_splits = min(5, min(label_counts.values()))
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

        scores = cross_val_score(pipeline, X, y, cv=cv, scoring='accuracy')
        y_pred = cross_val_predict(pipeline, X, y, cv=cv)

        # Train final model on all data
        pipeline.fit(X, y)
        self._gesture_pipeline = pipeline
        self._gesture_classes = list(pipeline.classes_)

        # Show confusion matrix
        cm = confusion_matrix(y, y_pred, labels=unique_labels)
        self._gesture_last_cm = (cm, unique_labels)
        self._gesture_cm_btn.config(state=tk.NORMAL)
        self._gesture_plot_view = 'confusion'
        self._gesture_plot_confusion_matrix(cm, unique_labels)

        acc_mean = scores.mean() * 100
        acc_std = scores.std() * 100
        self._gesture_train_status.config(
            text=f'CV accuracy: {acc_mean:.1f}% ± {acc_std:.1f}%  ({n_splits}-fold)  |  Model ready'
        )

    def _gesture_plot_confusion_matrix(self, cm: np.ndarray, labels: List[str]):
        ax = self._gesture_ax
        ax.cla()
        ax.set_visible(True)
        self._apply_gesture_plot_theme()

        n = len(labels)
        im = ax.imshow(cm, interpolation='nearest', cmap='Blues', aspect='equal')

        # Annotate cells
        thresh = cm.max() / 2.0
        for i in range(n):
            for j in range(n):
                color = 'white' if cm[i, j] > thresh else _Theme.PlotForeground
                ax.text(j, i, str(cm[i, j]), ha='center', va='center', color=color, fontsize=12)

        ax.set_xticks(range(n))
        ax.set_yticks(range(n))
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.set_yticklabels(labels)
        ax.set_xlabel('Predicted')
        ax.set_ylabel('True')
        ax.set_title('Confusion Matrix (cross-validation)')
        self._gesture_fig.tight_layout()
        self._gesture_canvas.draw()

    # ------------------------------------------------------------------
    # Model save / load
    # ------------------------------------------------------------------

    def _on_gesture_save_model(self):
        import joblib

        if self._gesture_pipeline is None:
            self._gesture_train_status.config(text='No trained model to save')
            return

        os.makedirs(_MODELS_DIR, exist_ok=True)
        path = filedialog.asksaveasfilename(
            initialdir=_MODELS_DIR,
            defaultextension='.joblib',
            filetypes=[('Joblib model', '*.joblib')],
            title='Save gesture model',
        )
        if not path:
            return

        model_data = {
            'pipeline': self._gesture_pipeline,
            'classes': self._gesture_classes,
            'use_phase': self._gesture_use_phase.get(),
            'use_amplitude_response': self._gesture_use_amplitude_response.get(),
        }
        joblib.dump(model_data, path)
        self._gesture_train_status.config(text=f'Model saved to {os.path.basename(path)}')

    def _on_gesture_load_model(self):
        import joblib

        if os.path.isdir(_MODELS_DIR):
            initial = _MODELS_DIR
        else:
            initial = os.getcwd()

        path = filedialog.askopenfilename(
            initialdir=initial,
            filetypes=[('Joblib model', '*.joblib')],
            title='Load gesture model',
        )
        if not path:
            return

        try:
            model_data = joblib.load(path)
        except Exception as e:
            self._gesture_train_status.config(text=f'Load error: {e}')
            return

        self._gesture_pipeline = model_data['pipeline']
        self._gesture_classes = model_data['classes']
        if 'use_phase' in model_data:
            self._gesture_use_phase.set(model_data['use_phase'])
        if 'use_amplitude_response' in model_data:
            self._gesture_use_amplitude_response.set(model_data['use_amplitude_response'])

        classes_str = ', '.join(self._gesture_classes)
        self._gesture_train_status.config(
            text=f'Loaded model from {os.path.basename(path)} — classes: [{classes_str}]'
        )

    # ------------------------------------------------------------------
    # Live recognition
    # ------------------------------------------------------------------

    def _on_gesture_toggle_recognition(self):
        if self._gesture_recognizing:
            self._gesture_stop_recognition()
        else:
            self._gesture_start_recognition()

    def _gesture_start_recognition(self):
        if self._gesture_pipeline is None:
            self._gesture_train_status.config(text='Train or load a model first')
            return
        if self._gesture_recording:
            self._gesture_status.config(text='Stop recording before starting recognition')
            return

        self._gesture_recognizing = True
        self._gesture_recognize_btn.config(text='Stop recognition')
        self._gesture_pred_label.config(text='Waiting...', bg=_Theme.AltBackground, fg=_Theme.Foreground)
        self._gesture_pre_recognition_view = self._gesture_plot_view
        self._gesture_plot_view = 'proba'
        self._gesture_init_proba_chart()

    def _gesture_stop_recognition(self):
        self._gesture_recognizing = False
        self._gesture_recognize_btn.config(text='Start recognition')
        self._gesture_pred_label.config(text='', bg=_Theme.AltBackground, fg=_Theme.Foreground)
        self._gesture_proba_bars = None
        view = getattr(self, '_gesture_pre_recognition_view', 'pca')
        self._gesture_plot_view = view
        if view == 'pca':
            self._gesture_draw_pca()
        elif view == 'confusion':
            self._gesture_redraw_confusion_matrix()

    def _gesture_predict_current(self):
        """Run one prediction cycle using the current subevent data."""
        phase_data = getattr(self, '_current_phase_slope_data', None)
        amplitude_response = getattr(self, '_current_amplitude_response_data', None)
        initiator = getattr(self, '_current_initiator', None)
        reflector = getattr(self, '_current_reflector', None)

        drop_reason = sensing_drop_reason(initiator, reflector, phase_data, amplitude_response)
        if drop_reason:
            return  # silently skip bad subevents

        vec = build_feature_vector(
            phase_data, amplitude_response,
            use_phase=self._gesture_use_phase.get(),
            use_amplitude_response=self._gesture_use_amplitude_response.get(),
        )
        if vec is None:
            return

        self._gesture_predict_and_display(vec)

    def _gesture_predict_and_display(self, feature_vec: np.ndarray):
        """Run predict_proba and update the large prediction label."""
        X = feature_vec.reshape(1, -1)
        proba = self._gesture_pipeline.predict_proba(X)[0]
        best_idx = int(np.argmax(proba))
        confidence = proba[best_idx]
        label = self._gesture_classes[best_idx]

        pct = confidence * 100
        text = f'{label}  ({pct:.0f}%)'

        if confidence >= 0.8:
            bg = '#1b5e20'  # dark green
            fg = '#a5d6a7'  # light green
        elif confidence >= 0.5:
            bg = '#f57f17'  # dark yellow/amber
            fg = '#fff9c4'  # light yellow
        else:
            bg = '#b71c1c'  # dark red
            fg = '#ef9a9a'  # light red

        self._gesture_pred_label.config(text=text, bg=bg, fg=fg)

        # Update probability bar chart if active
        self._gesture_update_proba_bars(proba)

        # Update live dot on PCA scatter
        self._gesture_update_live_dot(feature_vec)
