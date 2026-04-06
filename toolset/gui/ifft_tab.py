import tkinter as tk
from tkinter import ttk
from typing import Optional
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from toolset.gui.cs_theme import _Theme
from toolset.processing.cs_ifft import compute_ifft_response, calculate_distance_from_ifft

class IFftTabMixin:
    """IFFT (impulse response) plot tab."""

    def _apply_ifft_plot_theme(self):
        self._ifft_fig.patch.set_facecolor(_Theme.PlotBackground)
        self._ifft_ax.set_facecolor(_Theme.PlotBackground)
        self._ifft_ax.tick_params(colors=_Theme.PlotForeground, which='both')
        self._ifft_ax.xaxis.label.set_color(_Theme.PlotForeground)
        self._ifft_ax.yaxis.label.set_color(_Theme.PlotForeground)
        self._ifft_ax.title.set_color(_Theme.PlotForeground)
        for spine in self._ifft_ax.spines.values():
            spine.set_edgecolor(_Theme.Border)
        self._ifft_ax.grid(True, color=_Theme.PlotGridColor)

    def _build_ifft_tab(self, tab_frame: ttk.Frame):
        self._ifft_fig = Figure(figsize=(8, 5), dpi=100)
        self._ifft_ax = self._ifft_fig.add_subplot(111)
        self._ifft_ax.set_xlabel('Delay (ns)')
        self._ifft_ax.set_ylabel('Magnitude')
        self._ifft_ax.set_title('IFFT Impulse Response')

        self._apply_ifft_plot_theme()
        self._ifft_fig.tight_layout(h_pad=4.5)

        self._ifft_canvas = FigureCanvasTkAgg(self._ifft_fig, master=tab_frame)
        tk_widget = self._ifft_canvas.get_tk_widget()
        tk_widget.configure(bg=_Theme.PlotBackground)
        tk_widget.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self._ifft_distance_label = ttk.Label(tab_frame, text="Distance: N/A", font=("TkDefaultFont", 16))
        self._ifft_distance_label.grid(row=1, column=0, pady=(6, 0))

        self._initialize_ifft_artists()
        self._ifft_canvas.mpl_connect('draw_event', self._on_ifft_canvas_draw)

        tab_frame.rowconfigure(0, weight=1)
        tab_frame.columnconfigure(0, weight=1)

    def _initialize_ifft_artists(self):
        (self._ifft_line,) = self._ifft_ax.plot(
            [], [], color=_Theme.PlotPhaseBarColor, linewidth=1.2, animated=True
        )
        # Vertical marker at the peak distance; uses blended transform (data-x, axes-y)
        (self._ifft_peak_vline,) = self._ifft_ax.plot(
            [0, 0], [0, 1],
            transform=self._ifft_ax.get_xaxis_transform(),
            color=_Theme.PlotIniBarColor, linewidth=1.5, linestyle='--',
            animated=True, visible=False,
        )
        self._ifft_blit_background = None
        self._ifft_force_full_redraw = True
        self._ifft_bg_refresh_pending = False
        self._ifft_xlim = (0.0, 1.0)
        self._ifft_ylim = (0.0, 1.0)

    def _on_ifft_canvas_draw(self, _event):
        if not hasattr(self._ifft_canvas, 'copy_from_bbox'):
            return
        self._ifft_blit_background = self._ifft_canvas.copy_from_bbox(self._ifft_fig.bbox)
        self._ifft_force_full_redraw = False

    def _update_ifft_tab(self):
        t_ns, magnitude = None, None
        if self._current_phase_slope_data and self._current_amplitude_response_data:
            t_ns, magnitude = compute_ifft_response(
                self._current_phase_slope_data,
                self._current_amplitude_response_data,
            )
        distance = calculate_distance_from_ifft(t_ns, magnitude) if t_ns is not None else None

        if t_ns is not None and len(t_ns) > 0:
            # Show only first half – covers the unambiguous range (0 to 1/(2*f_step) ≈ 500 ns)
            half = len(t_ns) // 2
            x = t_ns[:half]
            y = magnitude[:half]
            self._ifft_line.set_data(x, y)
            t_ns_peak = float(x[np.argmax(y)]) if len(y) else 0.0
            self._ifft_peak_vline.set_xdata([t_ns_peak, t_ns_peak])
            self._ifft_peak_vline.set_visible(True)
            new_xlim = (0.0, float(x[-1]))
            y_max = float(np.max(y)) if len(y) else 1.0
            new_ylim = (0.0, y_max * 1.1 if y_max > 0 else 1.0)
        else:
            self._ifft_line.set_data([], [])
            self._ifft_peak_vline.set_visible(False)
            new_xlim = (0.0, 1.0)
            new_ylim = (0.0, 1.0)

        self._ifft_distance_label.config(
            text=f"Distance: {distance:.2f} m" if distance is not None else "Distance: N/A"
        )

        if self._ifft_xlim != new_xlim:
            self._ifft_ax.set_xlim(*new_xlim)
            self._ifft_xlim = new_xlim
            self._ifft_force_full_redraw = True
        if self._ifft_ylim != new_ylim:
            self._ifft_ax.set_ylim(*new_ylim)
            self._ifft_ylim = new_ylim
            self._ifft_force_full_redraw = True

        self._render_ifft_plot()

    def _render_ifft_plot(self):
        def _draw_ifft_artists():
            self._ifft_ax.draw_artist(self._ifft_line)
            self._ifft_ax.draw_artist(self._ifft_peak_vline)

        blit_ready = (
            hasattr(self._ifft_canvas, 'copy_from_bbox')
            and self._ifft_blit_background is not None
        )

        if not blit_ready:
            self._ifft_canvas.draw()
            self._ifft_force_full_redraw = False
            if self._ifft_blit_background is not None:
                self._ifft_canvas.restore_region(self._ifft_blit_background)
                _draw_ifft_artists()
                self._ifft_canvas.blit(self._ifft_fig.bbox)
        else:
            self._ifft_canvas.restore_region(self._ifft_blit_background)
            _draw_ifft_artists()
            self._ifft_canvas.blit(self._ifft_fig.bbox)
            if self._ifft_force_full_redraw and not self._ifft_bg_refresh_pending:
                self._ifft_bg_refresh_pending = True
                self.root.after_idle(self._ifft_deferred_bg_refresh)

    def _ifft_deferred_bg_refresh(self):
        self._ifft_bg_refresh_pending = False
        self._ifft_force_full_redraw = False
        self._ifft_canvas.draw()
        if self._ifft_blit_background is not None:
            self._ifft_canvas.restore_region(self._ifft_blit_background)
            self._ifft_ax.draw_artist(self._ifft_line)
            self._ifft_ax.draw_artist(self._ifft_peak_vline)
            self._ifft_canvas.blit(self._ifft_fig.bbox)
