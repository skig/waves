import tkinter as tk
from tkinter import ttk
from typing import List, Optional, Callable, Dict
from toolset.cs_utils.cs_subevent import SubeventResults
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


class CSViewer:
    """GUI for viewing Channel Sounding data"""

    def __init__(self, initiator_subevents: List = None, reflector_subevents: List = None):
        self.initiator_subevents = initiator_subevents or []
        self.reflector_subevents = reflector_subevents or []

        self.initiator_map = {se.procedure_counter: se for se in self.initiator_subevents if se is not None}
        self.reflector_map = {se.procedure_counter: se for se in self.reflector_subevents if se is not None}

        self.phase_slope_map: Dict[int, Dict[int, float]] = {}

        self.live_mode = False
        self.live_initiator: Optional[SubeventResults] = None
        self.live_reflector: Optional[SubeventResults] = None
        self.live_phase_slope: Optional[Dict[int, float]] = None
        self._all_counters_cache = set()

        all_counters = sorted(set(self.initiator_map.keys()) | set(self.reflector_map.keys()))

        self.root = tk.Tk()
        self.root.title("Channel Sounding Viewer")
        self.root.geometry("900x600")

        self._create_widgets(all_counters)

    def _create_widgets(self, procedure_counters: List[int]):
        """Create GUI widgets"""

        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.live_var = tk.BooleanVar(value=False)
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

        self.fig = Figure(figsize=(8, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlabel('Channel Index')
        self.ax.set_ylabel('Sum of Phases')
        self.ax.set_title('Phase Slope')
        self.ax.grid(True)

        self.canvas = FigureCanvasTkAgg(self.fig, master=main_frame)
        self.canvas.get_tk_widget().grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        main_frame.rowconfigure(5, weight=1)
        main_frame.columnconfigure(2, weight=1)

        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        self._update_display()

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

            self._update_plot(phase_slope_data)

        except Exception as e:
            print(f"[ERROR] Exception in _update_display: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    def update_live_data(self, initiator: SubeventResults, reflector: SubeventResults, phase_slope_data: Dict[int, float]):
        """Update live data from consumer thread - thread-safe"""
        def _update():
            self.live_initiator = initiator
            self.live_reflector = reflector
            self.live_phase_slope = phase_slope_data

            self.initiator_map[initiator.procedure_counter] = initiator
            self.reflector_map[reflector.procedure_counter] = reflector
            self.phase_slope_map[initiator.procedure_counter] = phase_slope_data

            all_counters = sorted(set(self.initiator_map.keys()) | set(self.reflector_map.keys()))
            if all_counters:
                self.counter_spinbox.config(from_=min(all_counters), to=max(all_counters))

            if self.live_mode:
                self.counter_var.set(initiator.procedure_counter)
                self._update_display()

        self.root.after(0, _update)

    def _get_subevent_info(self, subevent):
        """Generate info string for a subevent"""
        steps = subevent.steps
        num_steps = len(steps)

        channels = set(step.channel for step in steps)
        num_channels = len(channels)

        info = f"{num_steps} steps, {num_channels} channels"

        return info

    def _update_plot(self, phase_slope_data: Optional[Dict[int, float]]):
        """Update the phase slope plot"""
        self.ax.clear()
        self.ax.set_xlabel('Channel Index')
        self.ax.set_ylabel('Sum of Phases')
        self.ax.set_title('Phase Slope')
        self.ax.grid(True)

        if phase_slope_data and len(phase_slope_data) > 0:
            sorted_channels = sorted(phase_slope_data.keys())
            phases = [phase_slope_data[ch] for ch in sorted_channels]

            self.ax.bar(sorted_channels, phases, color='steelblue', width=0.6)

        self.canvas.draw()

    def run(self):
        """Start the GUI event loop"""
        self.root.mainloop()


def launch_viewer(initiator_subevents: List = None, reflector_subevents: List = None):
    """Launch the CS Viewer GUI"""
    viewer = CSViewer(initiator_subevents, reflector_subevents)
    return viewer
