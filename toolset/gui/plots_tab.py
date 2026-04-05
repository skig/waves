import math
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.collections import PolyCollection
from toolset.gui.cs_theme import _Theme
from toolset.processing.cs_phase_slope import calculate_distance_from_phase_slope


class PlotsTabMixin:
    """Amplitude response and phase slope plots tab."""

    def _apply_plot_theme(self):
        """Apply the current theme colors to the matplotlib figure and axes."""
        self.fig.patch.set_facecolor(_Theme.PlotBackground)
        for ax in (self.ax_phase, self.ax_rssi):
            ax.set_facecolor(_Theme.PlotBackground)
            ax.tick_params(colors=_Theme.PlotForeground, which='both')
            ax.xaxis.label.set_color(_Theme.PlotForeground)
            ax.yaxis.label.set_color(_Theme.PlotForeground)
            ax.title.set_color(_Theme.PlotForeground)
            for spine in ax.spines.values():
                spine.set_edgecolor(_Theme.Border)
            ax.grid(True, color=_Theme.PlotGridColor)

    def _build_plots_tab(self, tab_frame: ttk.Frame):
        self.fig = Figure(figsize=(8, 8), dpi=100)
        self.ax_phase = self.fig.add_subplot(211)
        self.ax_phase.set_xlabel('Channel Index')
        self.ax_phase.set_ylabel('Sum of Phases unwrapped, rad')
        self.ax_phase.set_title('Phase Slope')

        self.ax_rssi = self.fig.add_subplot(212)
        self.ax_rssi.set_xlabel('Channel Index')
        self.ax_rssi.set_ylabel('Amplitude Response, dB')
        self.ax_rssi.set_title('Amplitude Response')

        self._apply_plot_theme()
        self.fig.tight_layout(h_pad=4.5)

        self.canvas = FigureCanvasTkAgg(self.fig, master=tab_frame)
        tk_widget = self.canvas.get_tk_widget()
        tk_widget.configure(bg=_Theme.PlotBackground)
        tk_widget.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self._initialize_plot_artists()
        self.canvas.mpl_connect('draw_event', self._on_canvas_draw)

        tab_frame.rowconfigure(0, weight=1)
        tab_frame.columnconfigure(0, weight=1)

    def _initialize_plot_artists(self):
        self._phase_collection = PolyCollection([], facecolors=[_Theme.PlotPhaseBarColor],
                                                edgecolors=['none'], antialiaseds=False, animated=True)
        self.ax_phase.add_collection(self._phase_collection)
        self._amplitude_response_collection = PolyCollection([], facecolors=[_Theme.PlotIniBarColor],
                                                             edgecolors=['none'], antialiaseds=False, alpha=0.8, animated=True)
        self.ax_rssi.add_collection(self._amplitude_response_collection)
        self._distance_text = self.ax_phase.text(
            0.5, -0.22, "Distance: N/A",
            transform=self.ax_phase.transAxes,
            ha='center', va='top',
            fontsize=16, color=_Theme.PlotForeground,
            animated=True, clip_on=False,
        )
        self._force_full_redraw = True

    def _on_canvas_draw(self, _event):
        if not self._supports_blit():
            return
        self._blit_background = self.canvas.copy_from_bbox(self.fig.bbox)
        self._force_full_redraw = False

    def _supports_blit(self) -> bool:
        return hasattr(self.canvas, 'copy_from_bbox')

    def _update_plots_tab(self):
        self._update_phase_plot(self._current_phase_slope_data)
        self._update_amplitude_response_plot(self._current_amplitude_response_data)
        distance = calculate_distance_from_phase_slope(self._current_phase_slope_data) if self._current_phase_slope_data else None
        if self._distance_text is not None:
            self._distance_text.set_text(f"Distance: {distance:.2f} m" if distance is not None else "Distance: N/A")
        self._render_plots()

    def _update_phase_plot(self, phase_slope_data: Optional[Dict[int, float]]):
        """Update the phase slope plot"""
        if phase_slope_data and len(phase_slope_data) > 0:
            sorted_channels = tuple(sorted(phase_slope_data.keys()))
            phases = [phase_slope_data[ch] for ch in sorted_channels]
            offset = phases[0]
            phases = [v - offset for v in phases]
        else:
            sorted_channels = ()
            phases = []

        if sorted_channels != self._phase_channels:
            self._phase_channels = sorted_channels
            self._force_full_redraw = True

        self._phase_collection.set_verts(self._bar_verts(sorted_channels, phases, 0.6))
        self._update_phase_limits(sorted_channels, phases)

    def _rssi_plot_bounds(self, values: List[float]) -> tuple[int, int]:
        if not values:
            return -100, 0

        bottom = math.floor(min(values) / 10) * 10
        top = math.ceil(max(values) / 10) * 10

        return bottom, top

    def _update_amplitude_response_plot(self, amplitude_response_data: Optional[Dict[int, float]]):
        """Update the amplitude response plot"""
        channels = tuple(sorted(amplitude_response_data.keys())) if amplitude_response_data else ()
        values = [amplitude_response_data[ch] for ch in channels] if amplitude_response_data else []
        self._rssi_bottom_dbm, self._rssi_top_dbm = self._rssi_plot_bounds(values)
        bar_bottom = min(self._rssi_bottom_dbm, self._rssi_ylim[0])
        heights = [value - bar_bottom for value in values]

        if channels != self._amplitude_response_channels:
            self._amplitude_response_channels = channels
            self._force_full_redraw = True

        self._amplitude_response_collection.set_verts(self._bar_verts(channels, heights, 0.6, bar_bottom))
        self._update_rssi_limits(channels, self._rssi_bottom_dbm, self._rssi_top_dbm)

    def _update_phase_limits(self, channels: tuple[int, ...], values: List[float]):
        if channels:
            x_min = min(channels) - 0.8
            x_max = max(channels) + 0.8
            min_value = min(values) if values else -1.0
            max_value = max(values) if values else 1.0
            y_pad = max(0.5, (max_value - min_value) * 0.1)
            y_min = min(min_value - y_pad, 0.0)
            y_max = max(max_value + y_pad, 0.0)
            if y_min == y_max:
                y_min -= 1.0
                y_max += 1.0
            # Round to nearest 1.0 so small data changes don't force a full redraw
            y_min = math.floor(y_min)
            y_max = math.ceil(y_max)
        else:
            x_min, x_max = -1.0, 1.0
            y_min, y_max = -1.0, 1.0

        new_ylim = (y_min, y_max)
        if self.ax_phase.get_xlim() != (x_min, x_max):
            self.ax_phase.set_xlim(x_min, x_max)
            self._force_full_redraw = True
        if self._phase_ylim != new_ylim:
            self.ax_phase.set_ylim(*new_ylim)
            self._phase_ylim = new_ylim
            self._force_full_redraw = True

    def _update_rssi_limits(
        self,
        channels: tuple[int, ...],
        y_bottom: float,
        y_top: float,
    ):
        if channels:
            x_min = min(channels) - 0.8
            x_max = max(channels) + 0.8
            y_min, y_max = y_bottom, y_top
        else:
            x_min, x_max = -1.0, 1.0
            y_min, y_max = -50.0, -40.0

        new_ylim = (y_min, y_max)
        if self.ax_rssi.get_xlim() != (x_min, x_max):
            self.ax_rssi.set_xlim(x_min, x_max)
            self._force_full_redraw = True
        if self._rssi_ylim != new_ylim:
            self.ax_rssi.set_ylim(*new_ylim)
            self._rssi_ylim = new_ylim
            self._force_full_redraw = True

    def _render_plots(self):
        def _draw_bar_artists():
            if self._phase_collection is not None:
                self.ax_phase.draw_artist(self._phase_collection)
            if self._distance_text is not None:
                self.ax_phase.draw_artist(self._distance_text)
            if self._amplitude_response_collection is not None:
                self.ax_rssi.draw_artist(self._amplitude_response_collection)

        blit_ready = (
            self._supports_blit()
            and self._blit_background is not None
        )

        if not blit_ready:
            # First render ever - must do synchronous full draw
            self.canvas.draw()
            self._force_full_redraw = False
            if self._blit_background is not None:
                self.canvas.restore_region(self._blit_background)
                _draw_bar_artists()
                self.canvas.blit(self.fig.bbox)
        else:
            # Fast path: always blit bars on existing background
            self.canvas.restore_region(self._blit_background)
            _draw_bar_artists()
            self.canvas.blit(self.fig.bbox)
            # If axes limits changed, schedule deferred background refresh
            if self._force_full_redraw and not self._bg_refresh_pending:
                self._bg_refresh_pending = True
                self.root.after_idle(self._deferred_bg_refresh)

    def _deferred_bg_refresh(self):
        """Redraw axes/ticks/grid in the background, then re-blit bar artists."""
        self._bg_refresh_pending = False
        self._force_full_redraw = False
        self.canvas.draw()
        if self._blit_background is not None:
            self.canvas.restore_region(self._blit_background)
            if self._phase_collection is not None:
                self.ax_phase.draw_artist(self._phase_collection)
            if self._distance_text is not None:
                self.ax_phase.draw_artist(self._distance_text)
            if self._amplitude_response_collection is not None:
                self.ax_rssi.draw_artist(self._amplitude_response_collection)
            self.canvas.blit(self.fig.bbox)

    @staticmethod
    def _bar_verts(positions, heights, width, bottom=0.0):
        n = len(positions)
        if n == 0:
            return np.empty((0, 4, 2))
        hw = width / 2
        x = np.asarray(positions, dtype=np.float64)
        h = np.asarray(heights, dtype=np.float64)
        verts = np.empty((n, 4, 2), dtype=np.float64)
        verts[:, 0, 0] = x - hw;  verts[:, 0, 1] = bottom
        verts[:, 1, 0] = x - hw;  verts[:, 1, 1] = bottom + h
        verts[:, 2, 0] = x + hw;  verts[:, 2, 1] = bottom + h
        verts[:, 3, 0] = x + hw;  verts[:, 3, 1] = bottom
        return verts
