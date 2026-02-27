import tkinter as tk
from tkinter import ttk
from typing import List, Optional, Callable, Dict
from toolset.cs_utils.cs_subevent import SubeventResults
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.container import BarContainer


class CSViewer:
    """GUI for viewing Channel Sounding data"""

    def __init__(self, initiator_subevents: List = None, reflector_subevents: List = None):
        self.initiator_subevents = initiator_subevents or []
        self.reflector_subevents = reflector_subevents or []

        self.initiator_map = {se.procedure_counter: se for se in self.initiator_subevents if se is not None}
        self.reflector_map = {se.procedure_counter: se for se in self.reflector_subevents if se is not None}

        self.phase_slope_map: Dict[int, Dict[int, float]] = {}
        self.rssi_ini_map: Dict[int, Dict[int, float]] = {}
        self.rssi_ref_map: Dict[int, Dict[int, float]] = {}

        self.live_mode = True
        self.live_initiator: Optional[SubeventResults] = None
        self.live_reflector: Optional[SubeventResults] = None
        self.live_phase_slope: Optional[Dict[int, float]] = None
        self.live_rssi_ini: Optional[Dict[int, float]] = None
        self.live_rssi_ref: Optional[Dict[int, float]] = None
        self.gui_refresh_interval_ms = 100
        self._live_render_scheduled = False
        self._pending_live_counter: Optional[int] = None
        self._all_counters_cache = set()
        self._phase_channels: tuple[int, ...] = ()
        self._rssi_ini_channels: tuple[int, ...] = ()
        self._rssi_ref_channels: tuple[int, ...] = ()
        self._phase_bars: Optional[BarContainer] = None
        self._rssi_ini_bars: Optional[BarContainer] = None
        self._rssi_ref_bars: Optional[BarContainer] = None
        self._blit_background_phase = None
        self._blit_background_rssi = None
        self._force_full_redraw = True
        self._phase_ylim = (-1.0, 1.0)
        self._rssi_ylim = (-1.0, 1.0)
        self._bar_width = 0.35

        all_counters = sorted(set(self.initiator_map.keys()) | set(self.reflector_map.keys()))

        self.root = tk.Tk()
        self.root.title("Channel Sounding Viewer")
        self.root.geometry("1200x900")

        self._create_widgets(all_counters)

    def _create_widgets(self, procedure_counters: List[int]):
        """Create GUI widgets"""

        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.live_var = tk.BooleanVar(value=True)
        live_checkbox = ttk.Checkbutton(
            main_frame,
            text="Live",
            variable=self.live_var,
            command=self._on_live_toggled
        )
        live_checkbox.grid(row=0, column=0, sticky=tk.W, pady=5)

        ttk.Label(main_frame, text="Procedure Counter:").grid(row=0, column=1, sticky=tk.W, pady=5, padx=(20, 0))

        self.counter_var = tk.IntVar(value=procedure_counters[0] if procedure_counters else 0)
        self.all_procedure_counters = procedure_counters if procedure_counters else [0]

        self.counter_spinbox = ttk.Spinbox(
            main_frame,
            from_=min(procedure_counters) if procedure_counters else 0,
            to=max(procedure_counters) if procedure_counters else 0,
            textvariable=self.counter_var,
            width=15,
            command=self._on_counter_changed
        )
        self.counter_spinbox.grid(row=0, column=2, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))

        ttk.Separator(main_frame, orient='horizontal').grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=15)

        ttk.Label(main_frame, text="Initiator Steps:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.initiator_steps_label = ttk.Label(main_frame, text="")
        self.initiator_steps_label.grid(row=2, column=1, columnspan=2, sticky=tk.W, pady=5, padx=(10, 0))

        ttk.Label(main_frame, text="Reflector Steps:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.reflector_steps_label = ttk.Label(main_frame, text="")
        self.reflector_steps_label.grid(row=3, column=1, columnspan=2, sticky=tk.W, pady=5, padx=(10, 0))

        ttk.Separator(main_frame, orient='horizontal').grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=15)

        self.fig = Figure(figsize=(8, 8), dpi=100)
        self.ax_phase = self.fig.add_subplot(211)
        self.ax_phase.set_xlabel('Channel Index')
        self.ax_phase.set_ylabel('Sum of Phases')
        self.ax_phase.set_title('Phase Slope')
        self.ax_phase.grid(True)

        self.ax_rssi = self.fig.add_subplot(212)
        self.ax_rssi.set_xlabel('Channel Index')
        self.ax_rssi.set_ylabel('RSSI Magnitude')
        self.ax_rssi.set_title('RSSI Values')
        self.ax_rssi.grid(True)

        self.fig.tight_layout()

        self.canvas = FigureCanvasTkAgg(self.fig, master=main_frame)
        self.canvas.get_tk_widget().grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        self._initialize_plot_artists()
        self.canvas.mpl_connect('draw_event', self._on_canvas_draw)

        main_frame.rowconfigure(5, weight=1)
        main_frame.columnconfigure(2, weight=1)

        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        self._update_display()

    def _initialize_plot_artists(self):
        self._phase_bars = self.ax_phase.bar([], [], color='steelblue', width=0.6, animated=True)
        self._rssi_ini_bars = self.ax_rssi.bar([], [], width=self._bar_width,
                                              color='blue', label='Initiator', alpha=0.8, animated=True)
        self._rssi_ref_bars = self.ax_rssi.bar([], [], width=self._bar_width,
                                              color='red', label='Reflector', alpha=0.8, animated=True)
        self.ax_rssi.legend()
        self._force_full_redraw = True

    def _on_canvas_draw(self, _event):
        if not self._supports_blit():
            return
        self._blit_background_phase = self.canvas.copy_from_bbox(self.ax_phase.bbox)
        self._blit_background_rssi = self.canvas.copy_from_bbox(self.ax_rssi.bbox)
        self._force_full_redraw = False

    def _supports_blit(self) -> bool:
        return bool(getattr(self.canvas, 'supports_blit', False))

    def _on_live_toggled(self):
        """Handle live mode checkbox toggle"""
        self.live_mode = self.live_var.get()
        self._update_display()

    def _on_counter_changed(self):
        """Handle spinbox counter change."""
        self._update_display()

    def _update_display(self):
        """Update display based on current mode"""
        try:
            counter_value = self.counter_var.get()

            if self.live_mode:
                if self.live_initiator:
                    info = self._get_subevent_info(self.live_initiator)
                    self.initiator_steps_label.config(text=info)
                else:
                    self.initiator_steps_label.config(text="waiting for data...")

                if self.live_reflector:
                    info = self._get_subevent_info(self.live_reflector)
                    self.reflector_steps_label.config(text=info)
                else:
                    self.reflector_steps_label.config(text="waiting for data...")

                phase_slope_data = self.live_phase_slope
                rssi_ini_data = self.live_rssi_ini
                rssi_ref_data = self.live_rssi_ref
            else:
                if counter_value in self.initiator_map:
                    info = self._get_subevent_info(self.initiator_map[counter_value])
                    self.initiator_steps_label.config(text=info)
                else:
                    self.initiator_steps_label.config(text="none")

                if counter_value in self.reflector_map:
                    info = self._get_subevent_info(self.reflector_map[counter_value])
                    self.reflector_steps_label.config(text=info)
                else:
                    self.reflector_steps_label.config(text="none")

                phase_slope_data = self.phase_slope_map.get(counter_value)
                rssi_ini_data = self.rssi_ini_map.get(counter_value)
                rssi_ref_data = self.rssi_ref_map.get(counter_value)

            self._update_phase_plot(phase_slope_data)
            self._update_rssi_plot(rssi_ini_data, rssi_ref_data)
            self._render_plots()

        except Exception as e:
            print(f"[ERROR] Exception in _update_display: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    def update_live_data(self, initiator: SubeventResults, reflector: SubeventResults, phase_slope_data: Dict[int, float], rssi_data_ini: Dict[int, float], rssi_data_ref: Dict[int, float]):
        """Update live data from consumer thread - thread-safe"""
        def _update():
            self.live_initiator = initiator
            self.live_reflector = reflector
            self.live_phase_slope = phase_slope_data
            self.live_rssi_ini = rssi_data_ini
            self.live_rssi_ref = rssi_data_ref

            self.initiator_map[initiator.procedure_counter] = initiator
            self.reflector_map[reflector.procedure_counter] = reflector
            self.phase_slope_map[initiator.procedure_counter] = phase_slope_data
            self.rssi_ini_map[initiator.procedure_counter] = rssi_data_ini
            self.rssi_ref_map[initiator.procedure_counter] = rssi_data_ref

            all_counters = sorted(set(self.initiator_map.keys()) | set(self.reflector_map.keys()))
            if all_counters:
                self.counter_spinbox.config(from_=min(all_counters), to=max(all_counters))

            if self.live_mode:
                self._pending_live_counter = initiator.procedure_counter
                if not self._live_render_scheduled:
                    self._live_render_scheduled = True
                    self.root.after(self.gui_refresh_interval_ms, self._flush_live_render)

        self.root.after(0, _update)

    def _flush_live_render(self):
        """Render latest live data at most once per refresh interval."""
        self._live_render_scheduled = False

        if not self.live_mode:
            return

        counter = self._pending_live_counter
        if counter is None:
            return

        self.counter_var.set(counter)
        self._update_display()

    def _get_subevent_info(self, subevent):
        """Generate info string for a subevent"""
        steps = subevent.steps
        num_steps = len(steps)

        channels = set(step.channel for step in steps)
        num_channels = len(channels)

        info = f"{num_steps} steps, {num_channels} channels"

        return info

    def _update_phase_plot(self, phase_slope_data: Optional[Dict[int, float]]):
        """Update the phase slope plot"""
        if phase_slope_data and len(phase_slope_data) > 0:
            sorted_channels = tuple(sorted(phase_slope_data.keys()))
            phases = [phase_slope_data[ch] for ch in sorted_channels]
        else:
            sorted_channels = ()
            phases = []

        if sorted_channels != self._phase_channels:
            if self._phase_bars is not None:
                self._phase_bars.remove()
            self._phase_bars = self.ax_phase.bar(sorted_channels, phases, color='steelblue', width=0.6, animated=True)
            self._phase_channels = sorted_channels
            self._force_full_redraw = True
        else:
            if self._phase_bars is not None:
                for bar, value in zip(self._phase_bars.patches, phases):
                    bar.set_height(value)

        self._update_phase_limits(sorted_channels, phases)

    def _update_rssi_plot(self, rssi_ini_data: Optional[Dict[int, float]], rssi_ref_data: Optional[Dict[int, float]]):
        """Update the RSSI plot"""
        ini_channels = tuple(sorted(rssi_ini_data.keys())) if rssi_ini_data else ()
        ref_channels = tuple(sorted(rssi_ref_data.keys())) if rssi_ref_data else ()
        ini_values = [rssi_ini_data[ch] for ch in ini_channels] if rssi_ini_data else []
        ref_values = [rssi_ref_data[ch] for ch in ref_channels] if rssi_ref_data else []

        if ini_channels != self._rssi_ini_channels:
            if self._rssi_ini_bars is not None:
                self._rssi_ini_bars.remove()
            ini_positions = [ch - self._bar_width / 2 for ch in ini_channels]
            self._rssi_ini_bars = self.ax_rssi.bar(ini_positions, ini_values, width=self._bar_width,
                                                   color='blue', label='Initiator', alpha=0.8, animated=True)
            self._rssi_ini_channels = ini_channels
            self._force_full_redraw = True
        else:
            if self._rssi_ini_bars is not None:
                for bar, value in zip(self._rssi_ini_bars.patches, ini_values):
                    bar.set_height(value)

        if ref_channels != self._rssi_ref_channels:
            if self._rssi_ref_bars is not None:
                self._rssi_ref_bars.remove()
            ref_positions = [ch + self._bar_width / 2 for ch in ref_channels]
            self._rssi_ref_bars = self.ax_rssi.bar(ref_positions, ref_values, width=self._bar_width,
                                                   color='red', label='Reflector', alpha=0.8, animated=True)
            self._rssi_ref_channels = ref_channels
            self._force_full_redraw = True
        else:
            if self._rssi_ref_bars is not None:
                for bar, value in zip(self._rssi_ref_bars.patches, ref_values):
                    bar.set_height(value)

        self._update_rssi_limits(ini_channels, ini_values, ref_channels, ref_values)

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
        ini_channels: tuple[int, ...],
        ini_values: List[float],
        ref_channels: tuple[int, ...],
        ref_values: List[float]
    ):
        channels = [*ini_channels, *ref_channels]
        values = [*ini_values, *ref_values]
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
        else:
            x_min, x_max = -1.0, 1.0
            y_min, y_max = -1.0, 1.0

        new_ylim = (y_min, y_max)
        if self.ax_rssi.get_xlim() != (x_min, x_max):
            self.ax_rssi.set_xlim(x_min, x_max)
            self._force_full_redraw = True
        if self._rssi_ylim != new_ylim:
            self.ax_rssi.set_ylim(*new_ylim)
            self._rssi_ylim = new_ylim
            self._force_full_redraw = True

    def _render_plots(self):
        if self._force_full_redraw or not self._supports_blit() or self._blit_background_phase is None or self._blit_background_rssi is None:
            self.canvas.draw()
            if self._supports_blit() and self._blit_background_phase is not None and self._blit_background_rssi is not None:
                self.canvas.restore_region(self._blit_background_phase)
                self.canvas.restore_region(self._blit_background_rssi)

                if self._phase_bars is not None:
                    for patch in self._phase_bars.patches:
                        self.ax_phase.draw_artist(patch)

                if self._rssi_ini_bars is not None:
                    for patch in self._rssi_ini_bars.patches:
                        self.ax_rssi.draw_artist(patch)

                if self._rssi_ref_bars is not None:
                    for patch in self._rssi_ref_bars.patches:
                        self.ax_rssi.draw_artist(patch)

                self.canvas.blit(self.ax_phase.bbox)
                self.canvas.blit(self.ax_rssi.bbox)
            return

        self.canvas.restore_region(self._blit_background_phase)
        self.canvas.restore_region(self._blit_background_rssi)

        if self._phase_bars is not None:
            for patch in self._phase_bars.patches:
                self.ax_phase.draw_artist(patch)

        if self._rssi_ini_bars is not None:
            for patch in self._rssi_ini_bars.patches:
                self.ax_rssi.draw_artist(patch)

        if self._rssi_ref_bars is not None:
            for patch in self._rssi_ref_bars.patches:
                self.ax_rssi.draw_artist(patch)

        self.canvas.blit(self.ax_phase.bbox)
        self.canvas.blit(self.ax_rssi.bbox)

    def run(self):
        """Start the GUI event loop"""
        self.root.mainloop()


def launch_viewer(initiator_subevents: List = None, reflector_subevents: List = None):
    """Launch the CS Viewer GUI"""
    viewer = CSViewer(initiator_subevents, reflector_subevents)
    return viewer
