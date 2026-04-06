import tkinter as tk
from tkinter import ttk
from typing import Optional
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from toolset.gui.cs_theme import _Theme
from toolset.processing.cs_music import compute_music_spectrum, calculate_distance_from_music


class MusicTabMixin:
    """MUSIC pseudo-spectrum plot tab."""

    def _apply_music_plot_theme(self):
        self._music_fig.patch.set_facecolor(_Theme.PlotBackground)
        self._music_ax.set_facecolor(_Theme.PlotBackground)
        self._music_ax.tick_params(colors=_Theme.PlotForeground, which='both')
        self._music_ax.xaxis.label.set_color(_Theme.PlotForeground)
        self._music_ax.yaxis.label.set_color(_Theme.PlotForeground)
        self._music_ax.title.set_color(_Theme.PlotForeground)
        for spine in self._music_ax.spines.values():
            spine.set_edgecolor(_Theme.Border)
        self._music_ax.grid(True, color=_Theme.PlotGridColor)

    def _build_music_tab(self, tab_frame: ttk.Frame):
        self._music_fig = Figure(figsize=(8, 5), dpi=100)
        self._music_ax = self._music_fig.add_subplot(111)
        self._music_ax.set_xlabel('Delay (ns)')
        self._music_ax.set_ylabel('Pseudo-spectrum')
        self._music_ax.set_title('MUSIC Pseudo-spectrum')

        self._apply_music_plot_theme()
        self._music_fig.tight_layout(h_pad=4.5)

        self._music_canvas = FigureCanvasTkAgg(self._music_fig, master=tab_frame)
        tk_widget = self._music_canvas.get_tk_widget()
        tk_widget.configure(bg=_Theme.PlotBackground)
        tk_widget.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self._music_distance_label = ttk.Label(tab_frame, text="Distance: N/A", font=("TkDefaultFont", 16))
        self._music_distance_label.grid(row=1, column=0, pady=(6, 0))

        self._initialize_music_artists()
        self._music_canvas.mpl_connect('draw_event', self._on_music_canvas_draw)

        tab_frame.rowconfigure(0, weight=1)
        tab_frame.columnconfigure(0, weight=1)

    def _initialize_music_artists(self):
        (self._music_line,) = self._music_ax.plot(
            [], [], color=_Theme.PlotPhaseBarColor, linewidth=1.2, animated=True
        )
        (self._music_peak_vline,) = self._music_ax.plot(
            [0, 0], [0, 1],
            transform=self._music_ax.get_xaxis_transform(),
            color=_Theme.PlotIniBarColor, linewidth=1.5, linestyle='--',
            animated=True, visible=False,
        )
        self._music_blit_background = None
        self._music_force_full_redraw = True
        self._music_bg_refresh_pending = False
        self._music_xlim = (0.0, 1.0)
        self._music_ylim = (0.0, 1.0)

    def _on_music_canvas_draw(self, _event):
        if not hasattr(self._music_canvas, 'copy_from_bbox'):
            return
        self._music_blit_background = self._music_canvas.copy_from_bbox(self._music_fig.bbox)
        self._music_force_full_redraw = False

    def _update_music_tab(self):
        delays_ns, pseudo_spectrum = None, None
        if self._current_phase_slope_data and self._current_amplitude_response_data:
            delays_ns, pseudo_spectrum = compute_music_spectrum(
                self._current_phase_slope_data,
                self._current_amplitude_response_data,
            )
        distance = calculate_distance_from_music(delays_ns, pseudo_spectrum) if delays_ns is not None else None

        if delays_ns is not None and len(delays_ns) > 0:
            x = delays_ns
            y = pseudo_spectrum
            self._music_line.set_data(x, y)
            ns_peak = float(x[np.argmax(y)]) if len(y) else 0.0
            self._music_peak_vline.set_xdata([ns_peak, ns_peak])
            self._music_peak_vline.set_visible(True)
            new_xlim = (0.0, float(x[-1]))
            y_max = float(np.max(y)) if len(y) else 1.0
            new_ylim = (0.0, y_max * 1.1 if y_max > 0 else 1.0)
        else:
            self._music_line.set_data([], [])
            self._music_peak_vline.set_visible(False)
            new_xlim = (0.0, 1.0)
            new_ylim = (0.0, 1.0)

        self._music_distance_label.config(
            text=f"Distance: {distance:.2f} m" if distance is not None else "Distance: N/A"
        )

        if self._music_xlim != new_xlim:
            self._music_ax.set_xlim(*new_xlim)
            self._music_xlim = new_xlim
            self._music_force_full_redraw = True
        if self._music_ylim != new_ylim:
            self._music_ax.set_ylim(*new_ylim)
            self._music_ylim = new_ylim
            self._music_force_full_redraw = True

        self._render_music_plot()

    def _render_music_plot(self):
        def _draw_music_artists():
            self._music_ax.draw_artist(self._music_line)
            self._music_ax.draw_artist(self._music_peak_vline)

        blit_ready = (
            hasattr(self._music_canvas, 'copy_from_bbox')
            and self._music_blit_background is not None
        )

        if not blit_ready:
            self._music_canvas.draw()
            self._music_force_full_redraw = False
            if self._music_blit_background is not None:
                self._music_canvas.restore_region(self._music_blit_background)
                _draw_music_artists()
                self._music_canvas.blit(self._music_fig.bbox)
        else:
            self._music_canvas.restore_region(self._music_blit_background)
            _draw_music_artists()
            self._music_canvas.blit(self._music_fig.bbox)
            if self._music_force_full_redraw and not self._music_bg_refresh_pending:
                self._music_bg_refresh_pending = True
                self.root.after_idle(self._music_deferred_bg_refresh)

    def _music_deferred_bg_refresh(self):
        self._music_bg_refresh_pending = False
        self._music_force_full_redraw = False
        self._music_canvas.draw()
        if self._music_blit_background is not None:
            self._music_canvas.restore_region(self._music_blit_background)
            self._music_ax.draw_artist(self._music_line)
            self._music_ax.draw_artist(self._music_peak_vline)
            self._music_canvas.blit(self._music_fig.bbox)
